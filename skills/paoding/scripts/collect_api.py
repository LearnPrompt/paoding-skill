#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""庖丁 · 开刃模式(可选 API 采集)

零 API 是庖丁的默认路径;开刃模式是给已经持有 TikHub / SocialData key 的用户的
可选增强——独有增量是「互动数全量 + 评论区」(认知层拆解的重要料)。

用法:
    python3 collect_api.py --platform xhs|douyin|x --user <名字/ID/链接> \
        --count 10 --outdir ./paoding-collect [--yes]

安全与费用纪律:
    · key 只从 ~/.config/paoding/keys.env 读取,绝不打印、绝不写入产物;
    · 采集前先查余额并打印,预估费用需确认(--yes 跳过交互);
    · 累计费用估算硬上限 ¥5(按 $0.002/请求折算),超限立即停止;
    · 每 5 条样本落盘一次断点(实际上逐条落盘,天然断点)。

仅用 Python3 标准库(urllib),不装任何第三方包。
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

KEYS_PATH = os.path.expanduser("~/.config/paoding/keys.env")
USD_PER_REQUEST = 0.002          # 保守估算:每次请求 $0.002
USD_CNY = 7.2                    # 折算汇率(保守)
HARD_CAP_CNY = 5.0               # 本次运行费用硬上限 ¥5
HARD_CAP_USD = HARD_CAP_CNY / USD_CNY
UA = "paoding-skill/1.2 (kaijian mode)"


class BudgetExceeded(RuntimeError):
    pass


def load_keys():
    """读 ~/.config/paoding/keys.env,返回 dict。文件不存在返回空 dict。"""
    keys = {}
    if not os.path.exists(KEYS_PATH):
        return keys
    with open(KEYS_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            keys[k.strip()] = v.strip()
    return keys


class BaseClient:
    """带计费估算的 HTTP 客户端基类。key 绝不出现在任何输出里。"""

    def __init__(self, key):
        self._key = key
        self.requests_made = 0
        self.est_cost_usd = 0.0

    def _charge(self):
        self.requests_made += 1
        self.est_cost_usd += USD_PER_REQUEST
        if self.est_cost_usd > HARD_CAP_USD:
            raise BudgetExceeded(
                "费用估算已超硬上限 ¥%.1f(%d 次请求),停止采集。已落盘的样本可用。"
                % (HARD_CAP_CNY, self.requests_made)
            )

    def _get(self, url, params=None):
        self._charge()
        if params:
            qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            url = url + ("&" if "?" in url else "?") + qs
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": "Bearer " + self._key,
                "Accept": "application/json",
                "User-Agent": UA,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode()[:200]
            except Exception:
                pass
            body = body.replace(self._key, "[REDACTED]")
            raise RuntimeError("HTTP %d @ %s :: %s" % (e.code, url.split("?")[0], body))


class TikHubClient(BaseClient):
    """TikHub(小红书/抖音)。端点路径来自 api.tikhub.io/openapi.json。"""

    BASE = "https://api.tikhub.io"

    def get_balance(self):
        d = self._get(self.BASE + "/api/v1/tikhub/user/get_user_info")
        return d.get("data", d)

    # ---- 小红书(app_v2 系列) ----
    def search_users(self, keyword):
        return self._get(self.BASE + "/api/v1/xiaohongshu/app_v2/search_users",
                         {"keyword": keyword})

    def fetch_user_info(self, user_id):
        return self._get(self.BASE + "/api/v1/xiaohongshu/app_v2/get_user_info",
                         {"user_id": user_id})

    def fetch_user_notes(self, user_id, cursor=None):
        return self._get(self.BASE + "/api/v1/xiaohongshu/app_v2/get_user_posted_notes",
                         {"user_id": user_id, "cursor": cursor})

    def fetch_note_detail(self, note_id, video=False):
        ep = "get_video_note_detail" if video else "get_image_note_detail"
        return self._get(self.BASE + "/api/v1/xiaohongshu/app_v2/" + ep,
                         {"note_id": note_id})

    def fetch_note_comments(self, note_id, cursor=None):
        return self._get(self.BASE + "/api/v1/xiaohongshu/app_v2/get_note_comments",
                         {"note_id": note_id, "cursor": cursor})

    # ---- 抖音(web 系列) ----
    def fetch_dy_user_profile(self, sec_user_id):
        return self._get(self.BASE + "/api/v1/douyin/web/handler_user_profile",
                         {"sec_user_id": sec_user_id})

    def fetch_dy_user_videos(self, sec_user_id, max_cursor=0, count=20):
        return self._get(self.BASE + "/api/v1/douyin/web/fetch_user_post_videos",
                         {"sec_user_id": sec_user_id, "max_cursor": max_cursor, "count": count})

    def fetch_dy_video_detail(self, aweme_id):
        return self._get(self.BASE + "/api/v1/douyin/web/fetch_one_video",
                         {"aweme_id": aweme_id})

    def fetch_dy_video_comments(self, aweme_id, cursor=0, count=20):
        return self._get(self.BASE + "/api/v1/douyin/web/fetch_video_comments",
                         {"aweme_id": aweme_id, "cursor": cursor, "count": count})


class SocialDataClient(BaseClient):
    """SocialData(X/Twitter)。docs.socialdata.tools。"""

    BASE = "https://api.socialdata.tools"

    def get_balance(self):
        return self._get(self.BASE + "/user/balance")  # {"balance_usd": ...}

    def get_user(self, username):
        return self._get(self.BASE + "/twitter/user/" + urllib.parse.quote(username))

    def get_user_tweets(self, user_id, cursor=None):
        return self._get(self.BASE + "/twitter/user/%s/tweets" % user_id,
                         {"cursor": cursor})

    def get_tweet_comments(self, tweet_id, cursor=None):
        return self._get(self.BASE + "/twitter/tweets/%s/comments" % tweet_id,
                         {"cursor": cursor})


# ---------------- 落盘 ----------------

def slugify(text, maxlen=40):
    s = re.sub(r"[^\w一-鿿-]+", "-", (text or "untitled")).strip("-")
    return s[:maxlen] or "untitled"


def write_sample(outdir, idx, meta, content, comments):
    """comments: [(text, like_count), ...] 已脱敏(只留文本与赞数)。"""
    d = os.path.join(outdir, "S%02d-%s" % (idx, slugify(meta.get("title", ""))))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "meta.json"), "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    with open(os.path.join(d, "content.txt"), "w") as f:
        f.write(content or "")
    top = sorted(comments, key=lambda c: -(c[1] or 0))[:20]
    with open(os.path.join(d, "comments.txt"), "w") as f:
        for text, likes in top:
            f.write("[赞%s] %s\n" % (likes or 0, (text or "").replace("\n", " ")))
    return d


# ---------------- 各平台采集 ----------------

def collect_x(client, user, count, outdir):
    username = user.rstrip("/").split("/")[-1].lstrip("@")
    u = client.get_user(username)
    uid = u.get("id_str") or u.get("id")
    print("▶ 用户:@%s(粉丝 %s)" % (u.get("screen_name"), u.get("followers_count")))
    collected, cursor, idx = 0, None, 0
    while collected < count:
        page = client.get_user_tweets(uid, cursor)
        tweets = page.get("tweets") or []
        if not tweets:
            break
        for t in tweets:
            if collected >= count:
                break
            idx += 1
            tid = t.get("id_str") or t.get("id")
            meta = {
                "platform": "x",
                "id": str(tid),
                "title": (t.get("full_text") or "")[:50],
                "date": t.get("tweet_created_at") or t.get("created_at"),
                "likes": t.get("favorite_count"),
                "comments_count": t.get("reply_count"),
                "reposts": t.get("retweet_count"),
                "views": t.get("views_count"),
                "bookmarks": t.get("bookmark_count"),
                "url": "https://x.com/%s/status/%s" % (username, tid),
            }
            comments = []
            try:
                cd = client.get_tweet_comments(tid)
                for c in (cd.get("tweets") or []):
                    cid = str(c.get("id_str") or c.get("id"))
                    if cid == str(tid):
                        continue  # 端点会把原推带回来,过滤掉
                    comments.append(((c.get("full_text") or ""), c.get("favorite_count") or 0))
            except (RuntimeError, BudgetExceeded) as e:
                if isinstance(e, BudgetExceeded):
                    raise
                print("  ⚠ S%02d 评论拉取失败:%s" % (idx, e))
            p = write_sample(outdir, idx, meta, t.get("full_text") or "", comments)
            collected += 1
            print("  ✓ S%02d %s(赞%s 评%s)→ %s" % (idx, meta["title"][:24],
                  meta["likes"], meta["comments_count"], os.path.basename(p)))
            if collected % 5 == 0:
                print("  💾 断点:已落盘 %d 条" % collected)
        cursor = page.get("next_cursor")
        if not cursor:
            break
    return collected


def _xhs_note_id(item):
    note = item.get("note") or item
    return note.get("id") or note.get("note_id")


def collect_xhs(client, user, count, outdir):
    # user 可以是 user_id、主页链接或名字(名字走搜索取第一个)
    m = re.search(r"user/profile/([0-9a-f]{24})", user) or re.search(r"^([0-9a-f]{24})$", user)
    if m:
        user_id = m.group(1)
    else:
        sr = client.search_users(user)
        users = (sr.get("data", {}).get("users")
                 or sr.get("data", {}).get("items") or [])
        if not users:
            raise RuntimeError("搜索不到用户:%s" % user)
        u0 = users[0]
        user_id = u0.get("id") or u0.get("user_id")
        print("▶ 搜索命中:%s(id=%s)" % (u0.get("name") or u0.get("nickname"), user_id))
    notes_resp = client.fetch_user_notes(user_id)
    data = notes_resp.get("data", {})
    notes = data.get("notes") or data.get("items") or []
    collected, idx = 0, 0
    cursor = data.get("cursor")
    while collected < count:
        for item in notes:
            if collected >= count:
                break
            idx += 1
            note = item.get("note") or item
            note_id = _xhs_note_id(item)
            is_video = (note.get("type") == "video")
            detail = {}
            try:
                dresp = client.fetch_note_detail(note_id, video=is_video)
                detail = (dresp.get("data") or {}).get("note") or dresp.get("data") or {}
            except (RuntimeError, BudgetExceeded) as e:
                if isinstance(e, BudgetExceeded):
                    raise
                print("  ⚠ S%02d 详情失败:%s" % (idx, e))
            src = detail or note
            meta = {
                "platform": "xhs",
                "id": str(note_id),
                "title": src.get("title") or src.get("display_title") or "",
                "date": src.get("time") or src.get("create_time"),
                "likes": src.get("liked_count") or src.get("likes"),
                "collects": src.get("collected_count") or src.get("collects"),
                "comments_count": src.get("comments_count") or src.get("comment_count"),
                "shares": src.get("shared_count"),
                "type": "video" if is_video else "image",
            }
            content = src.get("desc") or ""
            comments = []
            try:
                cresp = client.fetch_note_comments(note_id)
                clist = ((cresp.get("data") or {}).get("comments")
                         or (cresp.get("data") or {}).get("items") or [])
                for c in clist:
                    comments.append((c.get("content") or "",
                                     int(c.get("like_count") or c.get("liked_count") or 0)))
            except (RuntimeError, BudgetExceeded) as e:
                if isinstance(e, BudgetExceeded):
                    raise
                print("  ⚠ S%02d 评论失败:%s" % (idx, e))
            write_sample(outdir, idx, meta, content, comments)
            collected += 1
            print("  ✓ S%02d %s(赞%s 评%s)" % (idx, (meta["title"] or "")[:24],
                  meta["likes"], meta["comments_count"]))
            if collected % 5 == 0:
                print("  💾 断点:已落盘 %d 条" % collected)
        if collected >= count or not cursor:
            break
        nresp = client.fetch_user_notes(user_id, cursor)
        data = nresp.get("data", {})
        notes = data.get("notes") or data.get("items") or []
        cursor = data.get("cursor")
        if not notes:
            break
    return collected


def collect_douyin(client, user, count, outdir):
    m = re.search(r"(MS4wLjABAAAA[\w-]+)", user)
    if not m:
        raise RuntimeError("抖音请提供含 sec_user_id 的主页链接(MS4wLjABAAAA 开头)")
    sec_uid = m.group(1)
    collected, idx, max_cursor = 0, 0, 0
    while collected < count:
        vresp = client.fetch_dy_user_videos(sec_uid, max_cursor=max_cursor,
                                            count=min(20, count))
        data = vresp.get("data", {})
        videos = data.get("aweme_list") or []
        if not videos:
            break
        for v in videos:
            if collected >= count:
                break
            idx += 1
            aweme_id = v.get("aweme_id")
            stats = v.get("statistics") or {}
            meta = {
                "platform": "douyin",
                "id": str(aweme_id),
                "title": (v.get("desc") or "")[:50],
                "date": v.get("create_time"),
                "likes": stats.get("digg_count"),
                "comments_count": stats.get("comment_count"),
                "shares": stats.get("share_count"),
                "collects": stats.get("collect_count"),
            }
            comments = []
            try:
                cresp = client.fetch_dy_video_comments(aweme_id)
                for c in ((cresp.get("data") or {}).get("comments") or []):
                    comments.append((c.get("text") or "", int(c.get("digg_count") or 0)))
            except (RuntimeError, BudgetExceeded) as e:
                if isinstance(e, BudgetExceeded):
                    raise
                print("  ⚠ S%02d 评论失败:%s" % (idx, e))
            write_sample(outdir, idx, meta, v.get("desc") or "", comments)
            collected += 1
            print("  ✓ S%02d %s(赞%s 评%s)" % (idx, meta["title"][:24],
                  meta["likes"], meta["comments_count"]))
            if collected % 5 == 0:
                print("  💾 断点:已落盘 %d 条" % collected)
        if not data.get("has_more"):
            break
        max_cursor = data.get("max_cursor") or 0
    return collected


# ---------------- main ----------------

def main():
    ap = argparse.ArgumentParser(description="庖丁开刃模式:可选 API 采集(TikHub/SocialData)")
    ap.add_argument("--platform", required=True, choices=["xhs", "douyin", "x"])
    ap.add_argument("--user", required=True, help="用户名/ID/主页链接")
    ap.add_argument("--count", type=int, default=10)
    ap.add_argument("--outdir", default="./paoding-collect")
    ap.add_argument("--yes", action="store_true", help="跳过交互确认")
    args = ap.parse_args()

    keys = load_keys()
    if args.platform in ("xhs", "douyin"):
        key = keys.get("TIKHUB_API_KEY")
        if not key:
            sys.exit("✗ 未配置 TIKHUB_API_KEY(%s)。回到零 API 路径:collect.sh 或手动喂料。" % KEYS_PATH)
        client = TikHubClient(key)
    else:
        key = keys.get("SOCIALDATA_API_KEY")
        if not key:
            sys.exit("✗ 未配置 SOCIALDATA_API_KEY(%s)。回到零 API 路径。" % KEYS_PATH)
        client = SocialDataClient(key)

    # 1. 查余额
    try:
        bal = client.get_balance()
    except RuntimeError as e:
        sys.exit("✗ 余额查询失败(key 无效或网络问题):%s" % e)
    if isinstance(bal, dict):
        bal_usd = bal.get("balance_usd") or bal.get("balance") or bal.get("remaining_credits")
        print("▶ 账户余额:%s" % (("$%.4f" % bal_usd) if isinstance(bal_usd, (int, float)) else json.dumps(
            {k: v for k, v in bal.items() if "key" not in k.lower() and "token" not in k.lower()},
            ensure_ascii=False)))

    # 2. 预估费用(每条样本约 2 次请求:详情+评论;另加列表/翻页开销)
    est_requests = args.count * 2 + max(2, args.count // 15 + 1)
    est_usd = est_requests * USD_PER_REQUEST
    print("▶ 预估:约 %d 次请求 ≈ $%.3f(¥%.2f);硬上限 ¥%.1f" %
          (est_requests, est_usd, est_usd * USD_CNY, HARD_CAP_CNY))
    if not args.yes:
        ans = input("确认开始采集?[y/N] ").strip().lower()
        if ans != "y":
            sys.exit("已取消。")

    os.makedirs(args.outdir, exist_ok=True)
    t0 = time.time()
    try:
        if args.platform == "x":
            n = collect_x(client, args.user, args.count, args.outdir)
        elif args.platform == "xhs":
            n = collect_xhs(client, args.user, args.count, args.outdir)
        else:
            n = collect_douyin(client, args.user, args.count, args.outdir)
    except BudgetExceeded as e:
        print("⛔ %s" % e)
        n = -1
    print("\n✅ 完成:%s 条样本 → %s(%d 次请求,估算 $%.4f ≈ ¥%.2f,用时 %.0fs)" %
          ("部分" if n < 0 else n, os.path.abspath(args.outdir),
           client.requests_made, client.est_cost_usd,
           client.est_cost_usd * USD_CNY, time.time() - t0))
    print("把样本目录喂回庖丁案板,继续观全牛→解牛。")


if __name__ == "__main__":
    main()
