<div align="center">

# 庖丁 | Paoding

> *「你研究了 10 个对标博主,还是说不清任何一个为什么爆——问题不在你,在你手里没有一把解牛刀。」*

[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-paoding-blueviolet)](skills/paoding/SKILL.md)
[![skills.sh](https://skills.sh/b/LearnPrompt/paoding-skill)](https://skills.sh/LearnPrompt/paoding-skill)
[![零API](https://img.shields.io/badge/%E9%9B%B6API-%E9%9B%B6Key%C2%B7%E9%9B%B6%E6%88%90%E6%9C%AC-green)](#为什么是零api)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**把任何博主(包括你自己)的爆款打法,解牛成四层结构,蒸馏成可装进你 AI 的内容教练。默认零 API;需要自动化时可开刃接 TikHub + 本地 Whisper。**

[它解决什么问题](#它解决什么问题) · [安装](#快速开始) · [怎么喂料](#怎么喂料) · [它和同类有什么不同](#它和同类有什么不同) · [安全边界](#安全边界)

</div>

---

## 快速开始

```bash
npx skills add LearnPrompt/paoding-skill -g
```

装完对 Agent 说:

```text
用庖丁拆解这个博主。这是他近期的 12 条笔记:[粘贴/截图/公开链接]
```

没有现成材料?直接说"用庖丁拆解博主XX",它会先给你一张**料单**——告诉你去复制哪几类笔记、各要几条,贴回来就开工。

## 它解决什么问题

事情是这样的。

你翻了对标博主 50 条笔记,感觉"他是挺会写的",但要你说清楚他**为什么**爆——开头是什么型、人设是什么声音、底层是哪套心智模型——你说不出来。

你让 AI 模仿他写一篇,出来的东西泛泛的,因为 AI 也没见过他的内容,只是在演"一个博主"。

市面上的蒸馏工具能自动采集,但要配付费 API、按条数算钱,而且只覆盖一两个平台。

庖丁换了个思路:**料先落到本地,牛再沿证据解。** 你可以复制/截图/贴链接(8 条起),也可以用自己的 TikHub key 自动采集公开笔记、互动数和评论,再把视频交给本地 Whisper。庖丁沿四层肌理拆开——选题层、结构层、表达层、认知层——每个结论都挂着样本原文做证据,最后交两件东西:一份可截图的《打法谱》,和一个可安装的 `<博主名>-coach` Skill。

## 怎么喂料

| 料的形式 | 质量 | 说明 |
|---|---|---|
| 粘贴的正文全文 | ★★★ | 带发布时间和互动数更佳 |
| 截图 | ★★☆ | Agent 用视觉读取,读不清会标注 |
| 公开链接(博客/公众号/RSS) | ★★☆ | curl 可达才算数;需登录的平台请改喂截图 |
| 你的口述记忆 | ★☆☆ | 只能当线索,不能当证据 |

门槛:**8 条样本起**,理想配比"高赞 6 + 常规 4 + 翻车 2"——有对照组才看得出肌理。

样本按独立内容去重。8-9 条可以开始拆解,但不能声称做过独立留出检验;至少 10 条且正文能隔离时,先留出 2-5 条,保证拆解组仍有 8 条。已经一起贴进对话的材料只能回看核对,不能假装没见过。没有互动数也能分析结构与表达,但不能据此解释为什么爆。

视频博主也能解:`yt-dlp` 下载公开视频 + `whisper.cpp`/`faster-whisper` 本地转写,全程零API零云端;小红书下载不稳时,你自己存到本地喂进来即可。

## 它会交付什么

1. **《打法谱》**——当前样本支持的打法 + 四层证据卡(支持样本、反例、置信度理由、验证状态)+ 最多 5 个可尝试动作 + 诚实的"不可复制项"。证据不足的层标待验证,不凑结论
2. **内容教练 Skill**——把有依据的策略编码成 `<博主名>-coach`,附来源证据和适用条件;低置信度项不写成默认规则,证据不足时交待补料草案
3. **差距对比表**——你喂了自己的内容时,指出最该先补的那一层(只指一层)
4. **试刀验证**——先用未参与蒸馏的留出材料检验结论,再做同题普通稿/教练稿对照,按结构、表达、可用性分别评分。无法隔离则标非独立演示,用户未评分则标待评,允许平局或教练更差
5. **回锅更新**——博主出了新内容,丢给庖丁,逐层 diff 旧谱:加强/推翻/新打法,《回锅记》附谱、教练 Skill 升版本(盯更新不是庖丁的活,料永远由你喂)

## 为什么是零API

- **默认零成本**:不开刃时不接 TikHub 等付费采集接口,蒸馏一个博主 0 元;
- **零风控风险**:不模拟登录、不爬需登录内容、不碰平台加密接口;
- **全平台**:料是你喂的,所以公众号、博客、X、小红书截图、B站文稿……什么平台都解;
- **选择权说清楚**:默认路径需要自己整理材料;想换取自动采集的便利,再由用户显式启用开刃模式并承担 API 成本。

## 它和同类有什么不同

| | API 采集式蒸馏工具 | **庖丁** |
|---|---|---|
| 数据来源 | 付费 API 自动采集 | 默认用户喂料(粘贴/截图/公开链接);**开刃模式**可选接 TikHub(小红书/抖音)+ SocialData(X)自动采集 |
| 成本 | API 按量计费 + 配置 | 默认零;开刃模式按量。TikHub 不设人工请求/费用硬上限,以目标样本数、账户余额和平台限速为边界 |
| 平台覆盖 | 接了哪个平台算哪个 | 料能喂进来的都行 |
| 证据链 | 统计为主 | 每条结论挂支持证据、反例检查、置信度及验证状态 |
| 产出 | 拆解报告 | 打法谱 + **内容教练 Skill** + 留出检验与同题对照 |
| 合规面 | 依赖采集方条款 | 默认只研究你提供的公开内容;开刃模式只采用户指定账号的公开内容并遵守供应商条款 |

## 开刃模式(可选)

默认路径永远零 API。但如果你本来就持有 TikHub 或 SocialData 的 key,可以给庖丁「开刃」——自动采集正文、互动数、评论区,并可为视频生成本地 Whisper 逐字稿:

```bash
mkdir -p ~/.config/paoding
cat > ~/.config/paoding/keys.env <<'EOF'
TIKHUB_API_KEY=你的key
SOCIALDATA_API_KEY=你的key
EOF
chmod 600 ~/.config/paoding/keys.env
```

TikHub(api.tikhub.io)管小红书/抖音,SocialData(socialdata.tools)管 X,两个 key 配一个也行。配好后庖丁收料时会自动检测并询问是否用 API 采集;也可手动跑:

```bash
# 元数据 + 正文 + 互动数 + 高赞评论
python3 skills/paoding/scripts/collect_api.py \
  --platform xhs --user "博主名" --count 50 --outdir ./paoding-collect

# 视频再补本地 Whisper 逐字稿(已验证的完整链路)
python3 skills/paoding/scripts/collect_api.py \
  --platform xhs --user "博主名" --count 50 --outdir ./paoding-collect \
  --transcript --whisper-model small
```

- TikHub 按目标样本量持续调用,不设固定请求次数或费用硬上限;`--count` 可取任意正整数,它限制的是收料范围,不是 API 调用预算;
- 小红书视频详情兼容 App V2 的 `video_info_v2.media.stream.h264[].master_url`,拿到视频后用本地 Whisper 转写,不调用云端转写 API;
- 每次运行先查余额并打印费用估算;默认要求确认,`--yes` 可跳过。请求自动限速、429/5xx 有限重试,但不会无限重试;
- 每条样本立即落盘,同目录重跑会按笔记 ID + 内容指纹断点去重;余额耗尽或网络中断后可原命令继续;
- 每条目录包含 `meta.json`、`content.txt`、`comments.txt`,视频转写成功时再有 `transcript.txt`;根目录有 `profile.json` 和 `collection.json`;
- key 只住在环境变量或本地 `keys.env`(600 权限),不进产物、不进日志。没配 key 时零 API 路径不受影响。
- 已经用过 Blogger Distiller 时,庖丁也会兼容读取 `~/.xiaohongshu/tikhub_config.json` 中现有的 TikHub token,无需复制密钥。

## 触发方式

- "用庖丁拆解这个博主"
- "蒸馏一下博主XX的打法"
- "他为什么爆?这是他最近的笔记"
- "把这个博主的打法装进我的 AI"
- "帮我看看我自己的内容为什么不爆"(自我解牛)

## 安全边界

- 默认路径不爬需要登录的内容、不绕平台风控;开刃模式只在用户提供 key 并确认后调用 TikHub/SocialData,不模拟登录、不绕过供应商限速;
- 蒸馏的是打法不是身份——生成的教练 Skill 写明不冒充博主本人,产出不复制原文整段(引用 ≤30 字);
- 拆在世真人且产出要公开传播时,会提醒姓名权/形象权风险并建议匿名化;
- 生成的教练 Skill 要发布到公开渠道前,会停手等你授权。

## 文件结构

```text
paoding-skill/
├── skills/paoding/
│   ├── SKILL.md          # 解牛工作流:收料→观全牛→解牛(四层)→成谱→试刀→回锅
│   ├── scripts/          # collect.sh(零API代收)+ collect_api.py(开刃模式,可选)
│   └── examples/         # 实战案例(蒸馏过程与产出样例)
├── assets/               # demo 与可复现录制脚本
├── .claude-plugin/       # Claude Code plugin marketplace 清单
└── LICENSE
```

## 验证与测试

```text
用庖丁拆解博主XX(不提供任何材料)
```

合格表现:它先给你开**料单**,而不是凭模型记忆开始"拆解"——无料不解是第一诫。

证据和试刀的完整规则见 [证据与验证](skills/paoding/references/证据与验证.md)。[行为回归用例](tests/证据与验证用例.md)覆盖少样本、重复材料、反例、留出泄漏、同题对照和评分边界;这些是人工测试材料,不是效果背书。

采集器单元测试(不调用真实 API):

```bash
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

## 致谢

- [otter1101/blogger-distiller](https://github.com/otter1101/blogger-distiller) — "把博主装进你的AI"这个问题定义的先行者;庖丁选择了零API的另一条路
- [alchaincyf/nuwa-skill](https://github.com/alchaincyf/nuwa-skill) — 人格提取→可安装Skill的产出形态
- 庖丁解牛,《庄子·养生主》——"依乎天理,批大郤,导大窾"

## License

[MIT](LICENSE)

---

<div align="center">

*收料 · 观全牛 · 解牛 · 成谱 · 试刀 · 回锅*

**无料不解,依乎天理,刀刃若新。**

</div>

---

<div align="center">

**更多好用 Skill · More Skills** → [learnprompt.pro/skills](https://learnprompt.pro/skills/)

[鲁班·Skill打磨](https://github.com/LearnPrompt/luban-skill) · [庖丁·博主蒸馏](https://github.com/LearnPrompt/paoding-skill) · [蔡伦·对话造纸](https://github.com/LearnPrompt/cailun-skill) · [阿福·LLM Todo](https://github.com/LearnPrompt/afu-llm-todo) · [愚公·Loop工程](https://github.com/LearnPrompt/loop-engineering) · [搭子·结对开发](https://github.com/LearnPrompt/partner-skill) · [AI雷达·零API资讯](https://github.com/LearnPrompt/ai-news-radar)

[淘金小镇·ClawHub日榜](https://github.com/LearnPrompt/skillrush-town) · [Irasutoya·正文配图](https://github.com/LearnPrompt/carl-irasutoya-illustrations) · [Humanize PPT·演讲系统](https://github.com/LearnPrompt/humanize-ppt) · [CC Harness·六件套](https://github.com/LearnPrompt/cc-harness-skills) · [微信读书教练](https://github.com/LearnPrompt/carl-weread) · [X Article发布](https://github.com/LearnPrompt/x-article-publisher-skill)

<sub>**[LearnPrompt](https://github.com/LearnPrompt) 出品** · 公众号「卡尔的AI沃茨」 · [X @aiwarts](https://x.com/aiwarts)</sub>

</div>
