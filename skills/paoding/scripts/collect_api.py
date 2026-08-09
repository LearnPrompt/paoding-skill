#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""庖丁 · 开刃模式（可选 API 采集 + 本地 Whisper）。

TikHub 路径：博主主页 → 笔记列表 → 逐条详情/评论 → 视频流 → 本地 Whisper。
SocialData 路径：X 用户 → 推文列表 → 逐条评论。

TikHub 不设请求次数或费用硬上限；目标样本量由 ``--count`` 决定。脚本仍会查余额、
显示费用估算、遵守请求间隔、有限重试并逐条落盘，以便中断后继续。

用法：
    python3 collect_api.py --platform xhs --user <名字/ID/链接> --count 50 \
        --outdir ./paoding-collect --transcript --whisper-model small [--yes]

密钥只从环境变量、~/.config/paoding/keys.env 或既有 Blogger Distiller 配置读取，
绝不打印或写入产物。
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

KEYS_PATH = os.path.expanduser("~/.config/paoding/keys.env")
BLOGGER_DISTILLER_CONFIG = os.path.expanduser("~/.xiaohongshu/tikhub_config.json")
USD_PER_REQUEST = 0.002
USD_CNY = 7.2
SOCIALDATA_HARD_CAP_CNY = 5.0
SOCIALDATA_HARD_CAP_USD = SOCIALDATA_HARD_CAP_CNY / USD_CNY
UA = "paoding-skill/1.2+dev (kaijian mode)"
MEDIA_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


class BudgetExceeded(RuntimeError):
    """仅用于仍保留硬上限的非 TikHub 客户端。"""


def load_keys():
    """读取环境变量和本地配置；环境变量优先。"""
    keys = {}
    if os.path.exists(KEYS_PATH):
        with open(KEYS_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                keys[key.strip()] = value.strip()
    for name in ("TIKHUB_API_KEY", "SOCIALDATA_API_KEY"):
        if os.environ.get(name):
            keys[name] = os.environ[name]
    if not keys.get("TIKHUB_API_KEY") and os.path.exists(BLOGGER_DISTILLER_CONFIG):
        try:
            with open(BLOGGER_DISTILLER_CONFIG, encoding="utf-8") as f:
                legacy = json.load(f)
            keys["TIKHUB_API_KEY"] = _pick(
                legacy,
                "tikhub_api_token",
                "tikhub_api_key",
                "api_token",
                "token",
            )
        except (OSError, ValueError):
            pass
    return keys


class BaseClient:
    """带节流、有限重试和费用估算的 HTTP 客户端。"""

    def __init__(self, key, min_interval=0.35, max_retries=3, hard_cap_usd=None):
        self._key = key
        self.min_interval = max(0.0, float(min_interval))
        self.max_retries = max(0, int(max_retries))
        self.hard_cap_usd = hard_cap_usd
        self.requests_made = 0
        self.est_cost_usd = 0.0
        self._last_request_at = 0.0

    def _record_request(self):
        self.requests_made += 1
        self.est_cost_usd += USD_PER_REQUEST
        if self.hard_cap_usd is not None and self.est_cost_usd > self.hard_cap_usd:
            raise BudgetExceeded(
                "费用估算已超硬上限 ¥%.1f（%d 次请求），停止采集。已落盘样本可用。"
                % (self.hard_cap_usd * USD_CNY, self.requests_made)
            )

    def _wait_for_slot(self):
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def _get(self, url, params=None):
        if params:
            query = urllib.parse.urlencode(
                {key: value for key, value in params.items() if value is not None}
            )
            url = url + ("&" if "?" in url else "?") + query
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": "Bearer " + self._key,
                "Accept": "application/json",
                "User-Agent": UA,
            },
        )
        for attempt in range(self.max_retries + 1):
            self._wait_for_slot()
            self._record_request()
            self._last_request_at = time.monotonic()
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                body = ""
                try:
                    body = exc.read().decode("utf-8")[:300]
                except Exception:
                    pass
                body = body.replace(self._key, "[REDACTED]")
                retryable = exc.code == 429 or 500 <= exc.code < 600
                if retryable and attempt < self.max_retries:
                    time.sleep(min(8.0, 1.0 * (2 ** attempt)))
                    continue
                hint = ""
                if exc.code == 402:
                    hint = "；TikHub 余额不足，请充值后从断点继续"
                elif exc.code == 403:
                    hint = "；请检查对应平台 API 权限"
                raise RuntimeError(
                    "HTTP %d @ %s :: %s%s"
                    % (exc.code, url.split("?")[0], body, hint)
                )
            except urllib.error.URLError as exc:
                if attempt < self.max_retries:
                    time.sleep(min(8.0, 1.0 * (2 ** attempt)))
                    continue
                raise RuntimeError("网络请求失败 @ %s :: %s" % (url.split("?")[0], exc))


class TikHubClient(BaseClient):
    """TikHub（小红书/抖音）；不设置人工请求或费用上限。"""

    BASE = "https://api.tikhub.io"

    def __init__(self, key, min_interval=0.35, max_retries=3):
        super().__init__(key, min_interval, max_retries, hard_cap_usd=None)

    def get_balance(self):
        data = self._get(self.BASE + "/api/v1/tikhub/user/get_user_info")
        return data.get("data", data)

    def search_users(self, keyword):
        return self._get(
            self.BASE + "/api/v1/xiaohongshu/app_v2/search_users",
            {"keyword": keyword},
        )

    def fetch_user_info(self, user_id):
        return self._get(
            self.BASE + "/api/v1/xiaohongshu/app_v2/get_user_info",
            {"user_id": user_id},
        )

    def fetch_user_notes(self, user_id, cursor=None):
        return self._get(
            self.BASE + "/api/v1/xiaohongshu/app_v2/get_user_posted_notes",
            {"user_id": user_id, "cursor": cursor},
        )

    def fetch_note_detail(self, note_id, video=False):
        endpoint = "get_video_note_detail" if video else "get_image_note_detail"
        return self._get(
            self.BASE + "/api/v1/xiaohongshu/app_v2/" + endpoint,
            {"note_id": note_id},
        )

    def fetch_note_comments(self, note_id, cursor=None):
        return self._get(
            self.BASE + "/api/v1/xiaohongshu/app_v2/get_note_comments",
            {"note_id": note_id, "cursor": cursor},
        )

    def fetch_dy_user_profile(self, sec_user_id):
        return self._get(
            self.BASE + "/api/v1/douyin/web/handler_user_profile",
            {"sec_user_id": sec_user_id},
        )

    def fetch_dy_user_videos(self, sec_user_id, max_cursor=0, count=20):
        return self._get(
            self.BASE + "/api/v1/douyin/web/fetch_user_post_videos",
            {"sec_user_id": sec_user_id, "max_cursor": max_cursor, "count": count},
        )

    def fetch_dy_video_detail(self, aweme_id):
        return self._get(
            self.BASE + "/api/v1/douyin/web/fetch_one_video",
            {"aweme_id": aweme_id},
        )

    def fetch_dy_video_comments(self, aweme_id, cursor=0, count=20):
        return self._get(
            self.BASE + "/api/v1/douyin/web/fetch_video_comments",
            {"aweme_id": aweme_id, "cursor": cursor, "count": count},
        )


class SocialDataClient(BaseClient):
    """SocialData（X/Twitter）；保留原有单次费用保护。"""

    BASE = "https://api.socialdata.tools"

    def __init__(self, key, min_interval=0.35, max_retries=3):
        super().__init__(
            key,
            min_interval,
            max_retries,
            hard_cap_usd=SOCIALDATA_HARD_CAP_USD,
        )

    def get_balance(self):
        return self._get(self.BASE + "/user/balance")

    def get_user(self, username):
        return self._get(self.BASE + "/twitter/user/" + urllib.parse.quote(username))

    def get_user_tweets(self, user_id, cursor=None):
        return self._get(
            self.BASE + "/twitter/user/%s/tweets" % user_id,
            {"cursor": cursor},
        )

    def get_tweet_comments(self, tweet_id, cursor=None):
        return self._get(
            self.BASE + "/twitter/tweets/%s/comments" % tweet_id,
            {"cursor": cursor},
        )


def _pick(data, *keys, default=None):
    if not isinstance(data, dict):
        return default
    for key in keys:
        value = data.get(key)
        if value not in (None, "", []):
            return value
    return default


def _unwrap_data(payload):
    current = payload
    for _ in range(4):
        if isinstance(current, dict) and isinstance(current.get("data"), (dict, list)):
            current = current["data"]
        else:
            break
    return current


def _list_from(payload, *keys):
    current = _unwrap_data(payload)
    if isinstance(current, list):
        return current
    if not isinstance(current, dict):
        return []
    for key in keys:
        value = current.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for nested_key in ("list", "items", "comments"):
                nested = value.get(nested_key)
                if isinstance(nested, list):
                    return nested
    return []


def _to_int(value):
    if value in (None, ""):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace(",", "")
    multiplier = 1
    if text.endswith("万"):
        text, multiplier = text[:-1], 10000
    elif text.endswith("亿"):
        text, multiplier = text[:-1], 100000000
    try:
        return int(float(text) * multiplier)
    except (TypeError, ValueError):
        return 0


def _extract_xhs_users(payload):
    users = []
    for item in _list_from(payload, "users", "items", "user_list"):
        if isinstance(item, dict):
            users.append(_pick(item, "user_info", "userInfo", "user") or item)
    return users


def _extract_xhs_page(payload):
    current = _unwrap_data(payload)
    if not isinstance(current, dict):
        return (current if isinstance(current, list) else []), None, False
    notes = _list_from(current, "notes", "items", "feeds")
    cursor = _pick(current, "cursor", "last_cursor", "lastCursor")
    has_more = bool(_pick(current, "has_more", "hasMore", default=False))
    return notes, cursor, has_more


def _extract_xhs_detail(payload):
    current = _unwrap_data(payload)
    if isinstance(current, list):
        current = current[0] if current else {}
    if not isinstance(current, dict):
        return {}
    items = current.get("items")
    if isinstance(items, list) and items:
        item = items[0] if isinstance(items[0], dict) else {}
        return _pick(item, "noteCard", "note_card", "note") or item
    return _pick(current, "note", "noteData", "note_card", "noteCard") or current


def extract_xhs_video_url(payload):
    """兼容 App V2 的 video_info_v2.media.stream.h264[].master_url。"""
    note = _extract_xhs_detail(payload)
    direct = _pick(note, "videoUrl", "video_url")
    if direct:
        return direct
    video = _pick(note, "video", "video_info_v2", "videoInfoV2") or {}
    stream = ((video.get("media") or {}).get("stream") or video.get("stream") or {})
    variants = stream.get("h264") or stream.get("h265") or []
    if isinstance(variants, list) and variants and isinstance(variants[0], dict):
        return _pick(variants[0], "masterUrl", "master_url", "url") or ""
    return ""


def _extract_douyin_detail(payload):
    current = _unwrap_data(payload)
    if not isinstance(current, dict):
        return {}
    items = current.get("aweme_list") or current.get("item_list") or []
    if isinstance(items, list) and items:
        return items[0] if isinstance(items[0], dict) else {}
    return _pick(current, "aweme_detail", "awemeDetail", "aweme") or current


def extract_douyin_video_url(payload):
    item = _extract_douyin_detail(payload)
    video = item.get("video") or {}
    play = _pick(video, "play_addr", "playAddr", "play_addr_h264") or {}
    urls = _pick(play, "url_list", "urlList") or []
    if isinstance(urls, list) and urls:
        return urls[0]
    return _pick(play, "url", "uri") or ""


def _extract_comments(payload, text_keys, like_keys):
    comments = []
    for item in _list_from(payload, "comments", "items", "comment_list", "list"):
        if not isinstance(item, dict):
            continue
        text = _pick(item, *text_keys) or ""
        if text:
            comments.append((text, _to_int(_pick(item, *like_keys))))
    return comments


def slugify(text, maxlen=40):
    value = re.sub(r"[^\w一-鿿-]+", "-", (text or "untitled")).strip("-")
    return value[:maxlen] or "untitled"


def _fingerprint(meta):
    identity = "|".join(
        str(meta.get(key) or "").strip().lower()
        for key in ("platform", "title", "date")
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]


def _load_checkpoint(outdir, platform):
    ids, fingerprints = set(), set()
    max_index = 0
    if not os.path.isdir(outdir):
        return ids, fingerprints, max_index
    for name in os.listdir(outdir):
        match = re.match(r"S(\d+)-", name)
        if not match:
            continue
        max_index = max(max_index, int(match.group(1)))
        meta_path = os.path.join(outdir, name, "meta.json")
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            continue
        if meta.get("platform") != platform:
            continue
        if meta.get("id"):
            ids.add(str(meta["id"]))
        fingerprints.add(meta.get("fingerprint") or _fingerprint(meta))
    return ids, fingerprints, max_index


def _iter_sample_dirs(outdir, platform):
    if not os.path.isdir(outdir):
        return
    names = sorted(name for name in os.listdir(outdir) if re.match(r"S\d+-", name))
    for name in names:
        sample_dir = os.path.join(outdir, name)
        meta_path = os.path.join(sample_dir, "meta.json")
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            continue
        if meta.get("platform") == platform:
            yield sample_dir, meta


def _write_json(path, value):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def _sanitize_public(value):
    """递归移除响应中可能出现的 token/key/secret 字段。"""
    if isinstance(value, dict):
        return {
            key: _sanitize_public(item)
            for key, item in value.items()
            if not any(marker in key.lower() for marker in ("token", "key", "secret", "authorization"))
        }
    if isinstance(value, list):
        return [_sanitize_public(item) for item in value]
    return value


def write_sample(outdir, idx, meta, content, comments):
    """逐条落盘；comments 已脱敏，只保留文本和赞数。"""
    meta = dict(meta)
    meta["fingerprint"] = _fingerprint(meta)
    sample_dir = os.path.join(outdir, "S%02d-%s" % (idx, slugify(meta.get("title", ""))))
    os.makedirs(sample_dir, exist_ok=True)
    _write_json(os.path.join(sample_dir, "meta.json"), meta)
    with open(os.path.join(sample_dir, "content.txt"), "w", encoding="utf-8") as f:
        f.write(content or "")
    top = sorted(comments, key=lambda comment: -(comment[1] or 0))[:20]
    with open(os.path.join(sample_dir, "comments.txt"), "w", encoding="utf-8") as f:
        for text, likes in top:
            f.write("[赞%s] %s\n" % (likes or 0, (text or "").replace("\n", " ")))
    return sample_dir


def _ensure_transcript_tools():
    missing = [name for name in ("ffmpeg", "whisper") if not shutil.which(name)]
    if missing:
        raise RuntimeError(
            "开启 --transcript 需要本地工具：%s。安装：brew install ffmpeg && "
            "python3 -m pip install -U openai-whisper" % ", ".join(missing)
        )


def transcribe_video(video_url, sample_dir, model="small", keep_media=False):
    """下载 TikHub 返回的视频流并用本地 Whisper 写入 transcript.txt。"""
    transcript_path = os.path.join(sample_dir, "transcript.txt")
    if os.path.exists(transcript_path) and os.path.getsize(transcript_path) > 0:
        return "cached"
    if not video_url:
        return "no_video_url"
    media_path = os.path.join(sample_dir, "source.mp4")
    partial_path = media_path + ".part"
    request = urllib.request.Request(
        video_url,
        headers={"User-Agent": MEDIA_UA, "Referer": "https://www.xiaohongshu.com/"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            with open(partial_path, "wb") as target:
                shutil.copyfileobj(response, target)
        os.replace(partial_path, media_path)
        result = subprocess.run(
            [
                "whisper",
                media_path,
                "--language",
                "zh",
                "--model",
                model,
                "--output_format",
                "txt",
                "--output_dir",
                sample_dir,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=1800,
            check=False,
        )
        generated = os.path.join(sample_dir, "source.txt")
        if result.returncode != 0 or not os.path.exists(generated):
            detail = (result.stdout or "")[-300:].replace("\n", " ")
            raise RuntimeError("Whisper 转写失败：%s" % detail)
        os.replace(generated, transcript_path)
        return "ok"
    except Exception:
        if os.path.exists(partial_path):
            os.unlink(partial_path)
        raise
    finally:
        if not keep_media and os.path.exists(media_path):
            os.unlink(media_path)


def _maybe_transcribe(video_url, sample_dir, enabled, model, keep_media):
    if not enabled:
        return "disabled"
    try:
        return transcribe_video(video_url, sample_dir, model=model, keep_media=keep_media)
    except Exception as exc:
        print("  ⚠ 转写失败：%s" % exc)
        return "failed"


def _backfill_transcripts(client, outdir, platform, model, keep_media):
    """为已落盘但还没有逐字稿的视频补转写，支持原命令断点续跑。"""
    completed = 0
    for sample_dir, meta in _iter_sample_dirs(outdir, platform):
        transcript_path = os.path.join(sample_dir, "transcript.txt")
        if meta.get("type") != "video" or (
            os.path.exists(transcript_path) and os.path.getsize(transcript_path) > 0
        ):
            continue
        item_id = str(meta.get("id") or "")
        if not item_id:
            continue
        try:
            if platform == "xhs":
                detail = client.fetch_note_detail(item_id, video=True)
                video_url = extract_xhs_video_url(detail)
            else:
                detail = client.fetch_dy_video_detail(item_id)
                video_url = extract_douyin_video_url(detail)
            status = _maybe_transcribe(video_url, sample_dir, True, model, keep_media)
        except RuntimeError as exc:
            print("  ⚠ %s 补转写详情失败：%s" % (item_id, exc))
            status = "failed"
        meta["transcript_status"] = status
        _write_json(os.path.join(sample_dir, "meta.json"), meta)
        if status in ("ok", "cached"):
            completed += 1
        print("  🎙 补转写 %s：%s" % (os.path.basename(sample_dir), status))
    return completed


def collect_x(client, user, count, outdir, **_):
    username = user.rstrip("/").split("/")[-1].lstrip("@")
    account = client.get_user(username)
    user_id = account.get("id_str") or account.get("id")
    print("▶ 用户：@%s（粉丝 %s）" % (account.get("screen_name"), account.get("followers_count")))
    existing_ids, existing_fingerprints, idx = _load_checkpoint(outdir, "x")
    total, cursor = max(len(existing_ids), len(existing_fingerprints)), None
    seen_cursors = set()
    while total < count:
        page = client.get_user_tweets(user_id, cursor)
        tweets = page.get("tweets") or []
        if not tweets:
            break
        for tweet in tweets:
            if total >= count:
                break
            tweet_id = str(tweet.get("id_str") or tweet.get("id") or "")
            meta = {
                "platform": "x",
                "id": tweet_id,
                "title": (tweet.get("full_text") or "")[:50],
                "date": tweet.get("tweet_created_at") or tweet.get("created_at"),
                "likes": tweet.get("favorite_count"),
                "comments_count": tweet.get("reply_count"),
                "reposts": tweet.get("retweet_count"),
                "views": tweet.get("views_count"),
                "bookmarks": tweet.get("bookmark_count"),
                "url": "https://x.com/%s/status/%s" % (username, tweet_id),
            }
            if tweet_id in existing_ids or _fingerprint(meta) in existing_fingerprints:
                continue
            comments = []
            try:
                response = client.get_tweet_comments(tweet_id)
                for comment in response.get("tweets") or []:
                    if str(comment.get("id_str") or comment.get("id")) == tweet_id:
                        continue
                    comments.append((comment.get("full_text") or "", comment.get("favorite_count") or 0))
            except BudgetExceeded:
                raise
            except RuntimeError as exc:
                print("  ⚠ 评论拉取失败：%s" % exc)
            idx += 1
            sample_dir = write_sample(outdir, idx, meta, tweet.get("full_text") or "", comments)
            existing_ids.add(tweet_id)
            existing_fingerprints.add(_fingerprint(meta))
            total += 1
            print("  ✓ S%02d %s → %s" % (idx, meta["title"][:24], os.path.basename(sample_dir)))
        cursor = page.get("next_cursor")
        if not cursor or cursor in seen_cursors:
            break
        seen_cursors.add(cursor)
    return total


def _xhs_note(item):
    return _pick(item, "note", "note_card", "noteCard") or item


def _xhs_note_id(item):
    note = _xhs_note(item)
    return str(_pick(item, "id", "note_id", "noteId") or _pick(note, "id", "note_id", "noteId") or "")


def _xhs_meta(note_id, source, fallback, is_video):
    source = source or fallback
    interact = _pick(source, "interact_info", "interactInfo") or {}
    return {
        "platform": "xhs",
        "id": note_id,
        "title": _pick(source, "title", "display_title", "displayTitle") or "",
        "date": _pick(source, "time", "create_time", "createTime", "timestamp"),
        "likes": _to_int(
            _pick(source, "liked_count", "likedCount", "likes")
            or _pick(interact, "liked_count", "likedCount")
        ),
        "collects": _to_int(
            _pick(source, "collected_count", "collectedCount", "collects")
            or _pick(interact, "collected_count", "collectedCount")
        ),
        "comments_count": _to_int(
            _pick(source, "comments_count", "comment_count", "commentCount")
            or _pick(interact, "comment_count", "commentCount")
        ),
        "shares": _to_int(
            _pick(source, "shared_count", "share_count", "shareCount")
            or _pick(interact, "shared_count", "shareCount")
        ),
        "type": "video" if is_video else "image",
    }


def collect_xhs(client, user, count, outdir, transcript=False, whisper_model="small", keep_media=False):
    match = re.search(r"user/profile/([0-9a-f]{24})", user) or re.search(r"^([0-9a-f]{24})$", user)
    if match:
        user_id = match.group(1)
    else:
        users = _extract_xhs_users(client.search_users(user))
        if not users:
            raise RuntimeError("搜索不到用户：%s" % user)
        matched = next(
            (item for item in users if (_pick(item, "name", "nickname", "nick_name") or "").strip() == user.strip()),
            users[0],
        )
        user_id = str(_pick(matched, "id", "user_id", "userid", "userId") or "")
        print("▶ 搜索命中：%s（id=%s）" % (_pick(matched, "name", "nickname", "nick_name"), user_id))
    if not user_id:
        raise RuntimeError("TikHub 搜索结果缺少 user_id")

    profile = _sanitize_public(_unwrap_data(client.fetch_user_info(user_id)))
    _write_json(os.path.join(outdir, "profile.json"), profile)
    if transcript:
        _backfill_transcripts(client, outdir, "xhs", whisper_model, keep_media)
    existing_ids, existing_fingerprints, idx = _load_checkpoint(outdir, "xhs")
    total = max(len(existing_ids), len(existing_fingerprints))
    notes, cursor, has_more = _extract_xhs_page(client.fetch_user_notes(user_id))
    seen_page_ids = set()
    seen_cursors = set()
    while total < count:
        for item in notes:
            if total >= count:
                break
            note = _xhs_note(item)
            note_id = _xhs_note_id(item)
            if not note_id or note_id in seen_page_ids or note_id in existing_ids:
                continue
            seen_page_ids.add(note_id)
            note_type = str(_pick(note, "type", "note_type") or "").lower()
            is_video = note_type == "video" or bool(_pick(note, "video", "video_info_v2", "videoInfoV2"))
            detail_response = {}
            detail = {}
            try:
                detail_response = client.fetch_note_detail(note_id, video=is_video)
                detail = _extract_xhs_detail(detail_response)
            except RuntimeError as exc:
                print("  ⚠ %s 详情失败：%s" % (note_id, exc))
            meta = _xhs_meta(note_id, detail, note, is_video)
            if _fingerprint(meta) in existing_fingerprints:
                existing_ids.add(note_id)
                continue
            comments = []
            try:
                comments = _extract_comments(
                    client.fetch_note_comments(note_id),
                    ("content", "text"),
                    ("like_count", "liked_count", "likeCount"),
                )
            except RuntimeError as exc:
                print("  ⚠ %s 评论失败：%s" % (note_id, exc))
            idx += 1
            sample_dir = write_sample(
                outdir,
                idx,
                meta,
                _pick(detail, "desc", "description", "content") or _pick(note, "desc", "description") or "",
                comments,
            )
            status = _maybe_transcribe(
                extract_xhs_video_url(detail_response) if is_video else "",
                sample_dir,
                transcript and is_video,
                whisper_model,
                keep_media,
            )
            if transcript and is_video:
                meta["transcript_status"] = status
                meta["fingerprint"] = _fingerprint(meta)
                _write_json(os.path.join(sample_dir, "meta.json"), meta)
            existing_ids.add(note_id)
            existing_fingerprints.add(_fingerprint(meta))
            total += 1
            tag = " 🎙%s" % status if transcript and is_video else ""
            print("  ✓ S%02d %s（赞%s 评%s）%s" % (idx, meta["title"][:24], meta["likes"], meta["comments_count"], tag))
            if total % 5 == 0:
                print("  💾 断点：已落盘 %d 条" % total)
        if total >= count or not has_more or not cursor or cursor in seen_cursors:
            break
        seen_cursors.add(cursor)
        notes, cursor, has_more = _extract_xhs_page(client.fetch_user_notes(user_id, cursor))
        if not notes:
            break
    return total


def collect_douyin(client, user, count, outdir, transcript=False, whisper_model="small", keep_media=False):
    match = re.search(r"(MS4wLjABAAAA[\w-]+)", user)
    if not match:
        raise RuntimeError("抖音请提供含 sec_user_id 的主页链接（MS4wLjABAAAA 开头）")
    sec_uid = match.group(1)
    _write_json(
        os.path.join(outdir, "profile.json"),
        _sanitize_public(_unwrap_data(client.fetch_dy_user_profile(sec_uid))),
    )
    if transcript:
        _backfill_transcripts(client, outdir, "douyin", whisper_model, keep_media)
    existing_ids, existing_fingerprints, idx = _load_checkpoint(outdir, "douyin")
    total, max_cursor = max(len(existing_ids), len(existing_fingerprints)), 0
    seen_cursors = set()
    while total < count:
        response = client.fetch_dy_user_videos(sec_uid, max_cursor=max_cursor, count=min(20, count - total))
        data = _unwrap_data(response)
        videos = data.get("aweme_list") or [] if isinstance(data, dict) else []
        if not videos:
            break
        for video in videos:
            if total >= count:
                break
            aweme_id = str(video.get("aweme_id") or "")
            if not aweme_id or aweme_id in existing_ids:
                continue
            detail_response = client.fetch_dy_video_detail(aweme_id) if transcript else {}
            detail = _extract_douyin_detail(detail_response) or video
            stats = detail.get("statistics") or video.get("statistics") or {}
            meta = {
                "platform": "douyin",
                "id": aweme_id,
                "title": (detail.get("desc") or video.get("desc") or "")[:50],
                "date": detail.get("create_time") or video.get("create_time"),
                "likes": stats.get("digg_count"),
                "comments_count": stats.get("comment_count"),
                "shares": stats.get("share_count"),
                "collects": stats.get("collect_count"),
                "type": "video",
            }
            if _fingerprint(meta) in existing_fingerprints:
                existing_ids.add(aweme_id)
                continue
            comments = []
            try:
                comments = _extract_comments(
                    client.fetch_dy_video_comments(aweme_id),
                    ("text", "content"),
                    ("digg_count", "like_count"),
                )
            except RuntimeError as exc:
                print("  ⚠ %s 评论失败：%s" % (aweme_id, exc))
            idx += 1
            sample_dir = write_sample(outdir, idx, meta, detail.get("desc") or "", comments)
            status = _maybe_transcribe(
                extract_douyin_video_url(detail_response or video),
                sample_dir,
                transcript,
                whisper_model,
                keep_media,
            )
            if transcript:
                meta["transcript_status"] = status
                meta["fingerprint"] = _fingerprint(meta)
                _write_json(os.path.join(sample_dir, "meta.json"), meta)
            existing_ids.add(aweme_id)
            existing_fingerprints.add(_fingerprint(meta))
            total += 1
            print(
                "  ✓ S%02d %s（赞%s 评%s） 🎙%s"
                % (idx, meta["title"][:24], meta["likes"], meta["comments_count"], status)
            )
        if not isinstance(data, dict) or not data.get("has_more"):
            break
        max_cursor = data.get("max_cursor") or 0
        if max_cursor in seen_cursors:
            break
        seen_cursors.add(max_cursor)
    return total


def _find_balance(value):
    if isinstance(value, dict):
        for key in ("balance_usd", "balance", "remaining_credits", "free_credit"):
            amount = value.get(key)
            if isinstance(amount, (int, float)):
                return amount
        for nested in value.values():
            amount = _find_balance(nested)
            if amount is not None:
                return amount
    elif isinstance(value, list):
        for nested in value:
            amount = _find_balance(nested)
            if amount is not None:
                return amount
    return None


def _display_balance(balance):
    balance_usd = _find_balance(balance)
    if balance_usd is None:
        print("▶ 账户余额：查询成功（响应未提供可识别数值）")
    else:
        print("▶ 账户余额：$%.4f" % balance_usd)


def main():
    parser = argparse.ArgumentParser(description="庖丁开刃模式：API 采集 + 可选本地 Whisper")
    parser.add_argument("--platform", required=True, choices=["xhs", "douyin", "x"])
    parser.add_argument("--user", required=True, help="用户名/ID/主页链接")
    parser.add_argument("--count", type=int, default=10, help="目标样本数；任意正整数，不是 API 调用上限")
    parser.add_argument("--outdir", default="./paoding-collect")
    parser.add_argument("--yes", action="store_true", help="跳过费用估算确认")
    parser.add_argument("--transcript", action="store_true", help="TikHub 视频下载后用本地 Whisper 转写")
    parser.add_argument("--whisper-model", default="small", help="Whisper 模型，默认 small")
    parser.add_argument("--keep-media", action="store_true", help="保留下载的 source.mp4")
    parser.add_argument("--request-interval", type=float, default=0.35, help="API 请求最小间隔秒数，默认 0.35")
    args = parser.parse_args()

    if args.count <= 0:
        parser.error("--count 必须是正整数")
    if args.request_interval < 0:
        parser.error("--request-interval 不能为负数")
    if args.transcript and args.platform == "x":
        parser.error("--transcript 当前仅支持 TikHub 的 xhs/douyin")
    if args.transcript:
        try:
            _ensure_transcript_tools()
        except RuntimeError as exc:
            parser.error(str(exc))

    keys = load_keys()
    if args.platform in ("xhs", "douyin"):
        key = keys.get("TIKHUB_API_KEY")
        if not key:
            sys.exit(
                "✗ 未配置 TIKHUB_API_KEY（环境变量、%s 或 %s）。"
                % (KEYS_PATH, BLOGGER_DISTILLER_CONFIG)
            )
        client = TikHubClient(key, min_interval=args.request_interval)
    else:
        key = keys.get("SOCIALDATA_API_KEY")
        if not key:
            sys.exit("✗ 未配置 SOCIALDATA_API_KEY（%s 或环境变量）。" % KEYS_PATH)
        client = SocialDataClient(key, min_interval=args.request_interval)

    try:
        _display_balance(client.get_balance())
    except RuntimeError as exc:
        sys.exit("✗ 余额查询失败（key 无效、权限或网络问题）：%s" % exc)

    estimated_requests = args.count * 2 + max(3, args.count // 15 + 2)
    estimated_usd = estimated_requests * USD_PER_REQUEST
    cap_note = "；TikHub 不设人工硬上限" if args.platform in ("xhs", "douyin") else "；硬上限 ¥%.1f" % SOCIALDATA_HARD_CAP_CNY
    print(
        "▶ 预估：约 %d 次请求 ≈ $%.3f（¥%.2f）%s"
        % (estimated_requests, estimated_usd, estimated_usd * USD_CNY, cap_note)
    )
    if not args.yes:
        answer = input("确认开始采集？[y/N] ").strip().lower()
        if answer != "y":
            sys.exit("已取消。")

    os.makedirs(args.outdir, exist_ok=True)
    started_at = time.time()
    collector_args = {
        "transcript": args.transcript,
        "whisper_model": args.whisper_model,
        "keep_media": args.keep_media,
    }
    try:
        if args.platform == "x":
            total = collect_x(client, args.user, args.count, args.outdir, **collector_args)
        elif args.platform == "xhs":
            total = collect_xhs(client, args.user, args.count, args.outdir, **collector_args)
        else:
            total = collect_douyin(client, args.user, args.count, args.outdir, **collector_args)
    except BudgetExceeded as exc:
        print("⛔ %s" % exc)
        checkpoint = _load_checkpoint(args.outdir, args.platform)
        total = max(len(checkpoint[0]), len(checkpoint[1]))

    manifest = {
        "platform": args.platform,
        "user": args.user,
        "requested_count": args.count,
        "sample_count": total,
        "transcript_enabled": args.transcript,
        "whisper_model": args.whisper_model if args.transcript else None,
        "requests_made": client.requests_made,
        "estimated_cost_usd": round(client.est_cost_usd, 6),
    }
    _write_json(os.path.join(args.outdir, "collection.json"), manifest)
    print(
        "\n✅ 完成：%d/%d 条样本 → %s（%d 次请求，估算 $%.4f ≈ ¥%.2f，用时 %.0fs）"
        % (
            total,
            args.count,
            os.path.abspath(args.outdir),
            client.requests_made,
            client.est_cost_usd,
            client.est_cost_usd * USD_CNY,
            time.time() - started_at,
        )
    )
    print("把样本目录交给庖丁，继续观全牛 → 四层解牛 → 打法谱/教练 Skill → 试刀。")


if __name__ == "__main__":
    main()
