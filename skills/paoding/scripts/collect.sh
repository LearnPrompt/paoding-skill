#!/usr/bin/env bash
# 庖丁 · 全自动免费代收料
# 用法:  bash collect.sh <视频链接> [输出目录] [--browser safari|chrome|edge|firefox]
#
# 它做什么:把一条公开视频链接,用免费开源工具(yt-dlp + ffmpeg + whisper)
#          自动下成音轨并本地转写成逐字稿。零付费API、零Key。
#
# 守三诫:
#   · 不偷牛——只下"链接指向的那一条"内容,不批量遍历账号、不建库。
#   · 不绕登录——登录墙平台(小红书/抖音)用 --browser 走【用户自己浏览器的登录态】,
#                 这是"用你自己的号看你能看到的内容",不是破解风控。没登录就如实失败。
#   · 料归用户——产物落本地文件,交回庖丁案板。
#
# 依赖(都免费):yt-dlp、ffmpeg、whisper(openai-whisper 或 whisper.cpp 任一)
set -euo pipefail

URL="${1:-}"
OUTDIR="${2:-./paoding-collect}"
BROWSER=""

# 解析 --browser
args=("$@")
for ((i=0; i<${#args[@]}; i++)); do
  if [[ "${args[$i]}" == "--browser" ]]; then
    BROWSER="${args[$((i+1))]:-}"
  fi
done

if [[ -z "$URL" || "$URL" == --* ]]; then
  echo "用法: bash collect.sh <视频链接> [输出目录] [--browser safari|chrome]" >&2
  exit 2
fi

# 短链预解析:b23.tv 这类跳转短链,yt-dlp 的 generic 提取器解不开会 412。
# 先用 curl 跟随跳转拿到真实长链,再交给后面的平台识别。
case "$URL" in
  *b23.tv*|*v.douyin.com*)
    resolved="$(curl -sIL "$URL" -o /dev/null -w '%{url_effective}' 2>/dev/null || true)"
    if [[ -n "$resolved" && "$resolved" != "$URL" ]]; then
      echo "▶ 短链解析:$URL"
      echo "          → $resolved"
      URL="$resolved"
    fi ;;
esac

# 平台识别 + 登录墙判定
need_cookies=0   # 1=没登录态根本拿不到(小红书/抖音)
soft_cookies=0   # 1=公开可看但风控常要登录态过(B站 412)
case "$URL" in
  *xiaohongshu.com*|*xhslink*)   plat="小红书"; need_cookies=1 ;;
  *douyin.com*|*iesdouyin*)      plat="抖音";   need_cookies=1 ;;
  *bilibili.com*|*b23.tv*)       plat="B站"; soft_cookies=1 ;;
  *x.com*|*twitter.com*)         plat="X" ;;
  *youtube.com*|*youtu.be*)      plat="YouTube" ;;
  *)                             plat="其他(yt-dlp 自适配)" ;;
esac

echo "▶ 平台:$plat"
if [[ "$need_cookies" == 1 && -z "$BROWSER" ]]; then
  echo "⚠ $plat 需登录态。请加 --browser chrome(或 edge/firefox/safari),庖丁会借用你自己浏览器里已登录的会话。" >&2
  echo "  例:bash collect.sh \"$URL\" $OUTDIR --browser chrome" >&2
  echo "  提示:macOS 上 Safari 的 cookie 受沙箱保护(报 Operation not permitted),优先用 Chrome;非用 Safari 不可则给终端开「完全磁盘访问」。" >&2
  exit 3
fi
if [[ "$soft_cookies" == 1 && -z "$BROWSER" ]]; then
  echo "ℹ $plat 公开可看,但常有风控(412)。如果下面下载失败,加 --browser chrome 借登录态重试即可。" >&2
fi

mkdir -p "$OUTDIR"
cd "$OUTDIR"

# 组装 yt-dlp 参数(--write-info-json 顺手存元数据,里面常带赞/评/转/藏)
yt_args=(-x --audio-format mp3 --no-playlist --write-info-json -o "S%(autonumber)02d-%(title).60s.%(ext)s")
[[ -n "$BROWSER" ]] && yt_args+=(--cookies-from-browser "$BROWSER")

echo "▶ 下载音轨(仅此一条)…"
if ! yt-dlp "${yt_args[@]}" "$URL"; then
  echo "✗ 下载失败。常见原因与对策:" >&2
  echo "  · HTTP 412 / 风控(B站常见):加 --browser chrome 借登录态重试;并确保 yt-dlp 是新版(pip install -U yt-dlp)。" >&2
  echo "  · 需登录(小红书/抖音):加 --browser chrome。" >&2
  echo "  · 内容已删 / 平台不支持:庖丁不硬抓——请用浏览器把视频另存到本地,再喂文件进来。" >&2
  exit 4
fi

# 找到刚下的 mp3
mp3="$(ls -t *.mp3 2>/dev/null | head -1)"
if [[ -z "$mp3" ]]; then echo "✗ 没拿到音轨文件" >&2; exit 4; fi
echo "▶ 已下:$mp3"

# 本地转写:优先 whisper.cpp,退而用 openai-whisper
echo "▶ 本地转写(零API,可能要几分钟)…"
txt="${mp3%.mp3}.txt"
if command -v whisper-cpp >/dev/null 2>&1; then
  whisper-cpp -f "$mp3" -l zh -otxt -of "${mp3%.mp3}" >/dev/null 2>&1 || true
elif command -v whisper >/dev/null 2>&1; then
  whisper "$mp3" --language zh --model base --output_format txt --output_dir . >/dev/null 2>&1 || true
else
  echo "✗ 没装转写工具。装一个(都免费):pip install -U openai-whisper  或  brew install whisper-cpp" >&2
  echo "  音轨已存:$OUTDIR/$mp3,装好后重跑即可。" >&2
  exit 5
fi

if [[ ! -s "$txt" ]]; then echo "✗ 转写没出文字,可能纯音乐/口音重。音轨在 $OUTDIR/$mp3,可换 --model small 重试或人工校。" >&2; exit 5; fi

# 互动数:从 info.json 抽赞/评/转/藏(抖音/B站常有;小红书提取器拿不到,会显示"—")
info="${mp3%.mp3}.info.json"
stat_line=""
if [[ -s "$info" ]] && command -v python3 >/dev/null 2>&1; then
  stat_line="$(python3 - "$info" <<'PY' 2>/dev/null
import json,sys
d=json.load(open(sys.argv[1]))
g=lambda k:d.get(k)
def f(v):return '—' if v in (None,0) else v
print('赞:%s 评:%s 转:%s 藏:%s 发布:%s 作者:%s'%(
 f(g('like_count')),f(g('comment_count')),f(g('repost_count')),
 f(g('save_count')),f(g('upload_date')),f(g('uploader') or g('uploader_id'))))
PY
)"
fi

echo ""
echo "✅ 收料完成:"
echo "   音轨:$OUTDIR/$mp3"
echo "   逐字稿:$OUTDIR/$txt"
[[ -n "$stat_line" ]] && echo "   互动数:$stat_line"
echo ""
echo "把逐字稿喂回庖丁案板,标注「口播转写,可能有误」,继续观全牛→解牛。"
echo "提醒:whisper/base 对口音、专有名词会出错——关键术语以截图/标题为准。"
if [[ "$stat_line" == *"评:—"* || -z "$stat_line" ]]; then
  echo "⚠ 这条没抓到互动数/评论数(小红书 yt-dlp 给不了)。要做高赞↔翻车对照、读评论区需求,请补:笔记页截图(含赞/藏/评)+ 评论区截图——庖丁用视觉读,零API、不硬抓。"
fi
