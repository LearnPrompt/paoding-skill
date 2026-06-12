<div align="center">

# 庖丁 | Paoding

> *「你研究了 10 个对标博主,还是说不清任何一个为什么爆——问题不在你,在你手里没有一把解牛刀。」*

[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-paoding-blueviolet)](skills/paoding/SKILL.md)
[![skills.sh](https://skills.sh/b/LearnPrompt/paoding-skill)](https://skills.sh/LearnPrompt/paoding-skill)
[![零API](https://img.shields.io/badge/%E9%9B%B6API-%E9%9B%B6Key%C2%B7%E9%9B%B6%E6%88%90%E6%9C%AC-green)](#为什么是零api)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**把任何博主(包括你自己)的爆款打法,解牛成四层结构,蒸馏成可装进你 AI 的内容教练。零API、零Key、零采集成本。**

[它解决什么问题](#它解决什么问题) · [安装](#快速开始) · [怎么喂料](#怎么喂料) · [它和同类有什么不同](#它和同类有什么不同) · [安全边界](#安全边界)

</div>

---

## 它解决什么问题

事情是这样的。

你翻了对标博主 50 条笔记,感觉"他是挺会写的",但要你说清楚他**为什么**爆——开头是什么型、人设是什么声音、底层是哪套心智模型——你说不出来。

你让 AI 模仿他写一篇,出来的东西泛泛的,因为 AI 也没见过他的内容,只是在演"一个博主"。

市面上的蒸馏工具能自动采集,但要配付费 API、按条数算钱,而且只覆盖一两个平台。

庖丁换了个思路:**料你来喂,牛它来解。** 你把博主的笔记复制/截图/贴链接给它(8 条起),它沿四层肌理拆开——选题层、结构层、表达层、认知层——每个结论都挂着样本原文做证据,最后交两件东西:一份可截图的《打法谱》,和一个可安装的 `<博主名>-coach` Skill,从此你写东西时它就在场边按那套打法盯你。

## 快速开始

```bash
npx skills add LearnPrompt/paoding-skill -g
```

装完对 Agent 说:

```text
用庖丁拆解这个博主。这是他近期的 12 条笔记:[粘贴/截图/公开链接]
```

没有现成材料?直接说"用庖丁拆解博主XX",它会先给你一张**料单**——告诉你去复制哪几类笔记、各要几条,贴回来就开工。

## 怎么喂料

| 料的形式 | 质量 | 说明 |
|---|---|---|
| 粘贴的正文全文 | ★★★ | 带发布时间和互动数更佳 |
| 截图 | ★★☆ | Agent 用视觉读取,读不清会标注 |
| 公开链接(博客/公众号/RSS) | ★★☆ | curl 可达才算数;需登录的平台请改喂截图 |
| 你的口述记忆 | ★☆☆ | 只能当线索,不能当证据 |

门槛:**8 条样本起**,理想配比"高赞 6 + 常规 4 + 翻车 2"——有对照组才看得出肌理。

## 它会交付什么

1. **《打法谱》**——一句话本质 + 四层拆解(每条结论挂样本证据)+ 你明天就能用的 5 个动作 + 诚实的"不可复制项"
2. **内容教练 Skill**——把打法编码成 `<博主名>-coach`,装进你的 Agent 常驻陪写
3. **差距对比表**——你喂了自己的内容时,指出最该先补的那一层(只指一层)
4. **试刀盲评**——用蒸馏出的打法现场仿写一条,和真品并排让你盲评,不像就回炉

## 为什么是零API

- **零成本**:不接 TikHub 等付费采集接口,蒸馏一个博主 0 元;
- **零风控风险**:不模拟登录、不爬需登录内容、不碰平台加密接口;
- **全平台**:料是你喂的,所以公众号、博客、X、小红书截图、B站文稿……什么平台都解;
- **代价也说清楚**:你要自己花 10 分钟复制材料。自动采集的便利,换来的是成本、配置和合规风险——庖丁选了另一边。

## 它和同类有什么不同

| | API 采集式蒸馏工具 | **庖丁** |
|---|---|---|
| 数据来源 | 付费 API 自动采集 | 用户喂料(粘贴/截图/公开链接) |
| 成本 | API 按量计费 + 配置 | 零 |
| 平台覆盖 | 接了哪个平台算哪个 | 料能喂进来的都行 |
| 证据链 | 统计为主 | 每条结论挂样本编号+原文引用 |
| 产出 | 拆解报告 | 打法谱 + **可安装的教练 Skill** + 试刀盲评 |
| 合规面 | 依赖采集方条款 | 不采集,只研究你提供的公开内容 |

## 触发方式

- "用庖丁拆解这个博主"
- "蒸馏一下博主XX的打法"
- "他为什么爆?这是他最近的笔记"
- "把这个博主的打法装进我的 AI"
- "帮我看看我自己的内容为什么不爆"(自我解牛)

## 安全边界

- 不爬需要登录的内容,不绕平台风控,不调用任何采集 API;
- 蒸馏的是打法不是身份——生成的教练 Skill 写明不冒充博主本人,产出不复制原文整段(引用 ≤30 字);
- 拆在世真人且产出要公开传播时,会提醒姓名权/形象权风险并建议匿名化;
- 生成的教练 Skill 要发布到公开渠道前,会停手等你授权。

## 文件结构

```text
paoding-skill/
├── skills/paoding/
│   ├── SKILL.md          # 解牛工作流:收料→观全牛→解牛(四层)→成谱→试刀
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

## 致谢

- [otter1101/blogger-distiller](https://github.com/otter1101/blogger-distiller) — "把博主装进你的AI"这个问题定义的先行者;庖丁选择了零API的另一条路
- [alchaincyf/nuwa-skill](https://github.com/alchaincyf/nuwa-skill) — 人格提取→可安装Skill的产出形态
- 庖丁解牛,《庄子·养生主》——"依乎天理,批大郤,导大窾"

## License

[MIT](LICENSE)

---

<div align="center">

*收料 · 观全牛 · 解牛 · 成谱 · 试刀*

**无料不解,依乎天理,刀刃若新。**

</div>

---

<div align="center">

**[LearnPrompt](https://github.com/LearnPrompt) 出品** · 同门手艺

[鲁班·Skill打磨](https://github.com/LearnPrompt/luban-skill) · [庖丁·博主蒸馏](https://github.com/LearnPrompt/paoding-skill) · [蔡伦·对话造纸](https://github.com/LearnPrompt/cailun-skill) · [阿福·LLM Todo](https://github.com/LearnPrompt/afu-llm-todo) · [AI雷达·零API资讯](https://github.com/LearnPrompt/ai-news-radar) · [淘金小镇·ClawHub日榜](https://github.com/LearnPrompt/skillrush-town) · [Irasutoya·正文配图](https://github.com/LearnPrompt/carl-irasutoya-illustrations) · [Humanize PPT·简报编排](https://github.com/LearnPrompt/humanize-ppt) · [CC Harness·六件套](https://github.com/LearnPrompt/cc-harness-skills)

<sub>公众号「卡尔的AI沃茨」 · [X @aiwarts](https://x.com/aiwarts) · [learnprompt.pro](https://www.learnprompt.pro)</sub>

</div>
