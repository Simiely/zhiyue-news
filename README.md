# 知阅 · zhiyue-news

> iOS 风格移动端新闻阅读页。**构建期把 RSS 数据写进 HTML**，所以对话预览、iframe 沙箱、`file://`、禁用 JavaScript 的环境里也能完整阅读。

- 在线页面：<https://simiely.github.io/zhiyue-news/>
- 交互版：<https://simiely.github.io/zhiyue-news/zaker-news.html>
- 文档维护规范：[Simiely/knowledge-base · 模板库/单项目规范](https://github.com/Simiely/knowledge-base/tree/main/%E6%A8%A1%E6%9D%BF%E5%BA%93/%E5%8D%95%E9%A1%B9%E7%9B%AE%E8%A7%84%E8%8C%83)

---

## 这个项目解决什么

普通单文件 HTML 新闻页放进对话预览器会白屏、点按钮没反应、外链点不开。原因是预览沙箱会剥离脚本、用 CSP 拦掉 `fetch`、静默禁止 `window.open`，而页面把内容和交互都留到运行时才生成。

本项目的做法是把**数据**和**每一种交互结果**都提前写进 HTML：

| 原本靠运行时 | 现在 |
|---|---|
| 脚本解析 CSV 渲染列表 | 构建期把 23 条标题、简介与原文链接写进 DOM |
| JS 处理点击 | `<label>` + `radio/checkbox` + CSS `:has(:checked)`，禁用 JS 也能点 |
| `window.open` 跳原文 | 普通 `<a href>`，按钮上直接显示完整 URL 供长按复制 |
| 运行时抓 RSS | GitHub Actions 每 6 小时构建快照，浏览器端零请求 |
| 数据只在内存 / localStorage | `articles.csv` 每次刷新落盘，`links.csv` 永久归档链接，正文 7 天自动清理 |

## 快速开始

**① 直接看（零配置）**
打开 [`index.html`](./index.html) —— 默认深色，23 条真实订阅（**标题 + 内文简介**），**点标题或蓝色按钮在新窗口打开原文**；频道 / 来源 / 字号 / 深浅色 / 紧凑 / 只看含正文都能点，不需要联网、服务器或账号，禁用 JavaScript 也生效。

**② 完整交互版**
```bash
python3 -m http.server 8000
# 浏览器打开 http://localhost:8000/zaker-news.html
```
可用联网同步、订阅管理、搜索、收藏、原文跳转。**默认点卡片直接在新窗口打开原文**；设置里可切回站内阅读页（看折叠的本地快照）。`zaker-news.html` 内置零脚本兜底，脚本被拦时降级为同一份离线内容。

**③ 更新数据（刷新一次就落盘）**
```bash
python3 build.py            # 联网重抓 → 落盘 CSV → 归档链接 → 7 天清理 → 重建两份页面
python3 build.py --offline  # 不联网，仍刷新落盘与重建
python3 build.py --prune-days 14   # 把正文保留期改成 14 天
python3 build.py --no-prune        # 本次跳过正文清理
python3 build.py --with-fulltext   # 恢复按需抓原文正文（默认关闭）
python3 build_static.py     # 只重建页面（含预生成按钮状态）
```
纯 Python 标准库，无第三方依赖。**每次运行都把结果写回 `articles.csv`**，新出现的原文链接追加进 `links.csv`；抓取失败保留上一版数据，不会清空。

详细步骤见 [docs/使用指南.md](./docs/使用指南.md)。

## 订阅指定内容 · 数据生命周期

`feeds.json` 是订阅清单，**改它就能换成你想看的内容**，页面不用改：

| 类型 | 写法 | 例子 |
|---|---|---|
| `rss` | 站点自带 feed，直接填 `url` | 少数派 `https://sspai.com/feed` |
| `rsshub` | 填 `route`，多实例竞速 | 澎湃 `/thepaper/channel/25950`（时事） |
| `thepaper_hot` | 澎湃官方 JSON 热榜 | `cache.thepaper.cn/contentapi/wwwIndex/rightSidebar` |

已内置的澎湃路由：首页头条 `/thepaper/featured`、时事 `25950`、财经 `25951`、思想 `25952`、国际 `122908`、科技 `119908`，外加官方热榜。想加别的栏目，在 `feeds.json` 里复制一条改 `route` 即可。

## 阅读方式：标题 + 内文简介 + 点卡片打开原文

页面**不再默认抓取全文**。每张卡片只展示标题与内文简介，点标题（静态版）或点卡片（交互版）就在**新窗口打开原文**；已有的 7 篇本地正文快照折叠在卡片里，可选查看。

| 情况 | 行为 |
|---|---|
| 有原文链接 · 真实浏览器 | `window.open(url,"_blank","noopener,noreferrer")`，一键直达 |
| 有原文链接 · 预览沙箱 | 拦下新窗口时自动弹菜单：复制链接 / 按标题搜索 / 本页加载原文 / 再试 |
| 有原文链接 · 零脚本静态版 | 普通 `<a href target="_blank">`，按钮上印完整 URL 可长按复制 |
| 无原文链接（16 条） | 给「⌕ 按标题搜索原文」兜底，**不编造链接**，同步成功后自动补齐 |

想回退到站内阅读页：「我的 → 订阅更新 → 关掉『点卡片直接打开原文』」。构建脚本默认 `MAX_ARTICLE_FETCH=0` 不抓全文，`python3 build.py --with-fulltext` 可恢复。

**三条数据规则**（这轮的重点）：

1. **全量存 CSV**：`articles.csv` 15 列是唯一真相源，每次刷新落盘；页面端在 https / localhost 下还能「绑定本地 articles.csv」，同步完自动写回文件，不再只依赖 localStorage。
2. **原文链接永久保留**：`link` 不会被空值覆盖，另外追加归档到 `links.csv`（字段 `id, title, source, link, first_seen`，只追加、不清理）。即使正文过期、条目不再出现在列表里，链接仍在台账中。
3. **正文 7 天自行清理**：新增 `fetched_at` 记录正文抓取时刻，超过 7 天清空 `content`、`tag` 改为「快照·正文已过期」，标题 / 摘要 / 来源 / 发布时间 / 链接全部保留。口径可用 `--prune-days` 调整；抓不到新正文而沿用旧正文时，会连同旧的 `fetched_at` 一起保留，避免 TTL 被虚假续期。

⚠️ 这里「7 天」按**正文抓取时刻**计时（正文是短期缓存，不是文章年龄）。若你想改成按文章发布时间计时，或想让过期条目整行删除，说一声即可调整。

## 双轨页面

| 文件 | 定位 | 脚本 |
|---|---|---|
| [`zaker-news.html`](./zaker-news.html) | 最开始的完整交互版，已修复；默认深色，内置零脚本兜底 | 内联 JS + 兜底 DOM |
| [`index.html`](./index.html) | 静态快照版，Pages 入口，64 KB | 零 `<script>`、零 fetch、零 localStorage |

两份页面都默认 `data-theme="dark"`，都带同一组**不需要 JS 的按钮**：推荐 / 时政 / 科技 / 财经 / 思想 / 生活 / 国际 / 娱乐 / 健康、按来源筛选、深色 / 浅色 / 小字 / 标准 / 大字 / 紧凑 / 只看含正文。多个状态可同时保持。

交互版「我的 → 数据」新增**绑定本地 articles.csv**：在 https 或 localhost 下选一次文件，之后每次同步 / 刷新自动写回；预览沙箱、`file://` 或不支持该 API 的浏览器会明确提示降级为「导出 CSV」。

## 文件结构

```
zhiyue-news/
├── README.md            本文件：项目是什么、快速开始（门面）
├── AGENTS.md            AI / 未来的你：技术栈、关键坑、约定、文档基线
├── DEVELOPMENT.md       架构说明 + 关键问题索引
├── CHANGELOG.md         版本变更
├── docs/
│   ├── 使用指南.md       本地更新、Pages 部署、CSV 字段、FAQ
│   ├── 架构.md           数据层 / 构建层 / 表现层 / 发布层
│   └── 问题记录/         一坑一篇，格式与 knowledge-base 一致
│       └── 索引.md
├── index.html           零脚本静态页
├── zaker-news.html      交互版
├── articles.csv         真实数据包（15 列，唯一真相源，每次刷新落盘）
├── links.csv            原文链接永久台账（只追加，不清理）
├── news.csv             空模板（15 列）
├── snapshot.csv         抓取溯源快照
├── feeds.json           订阅清单（6 个原有 RSS + 澎湃 7 条）
├── build.py             抓取 + 重建交互版内联数据
├── build_static.py      生成静态页 + 预生成按钮状态 + 注入兜底
├── .github/workflows/update.yml   每 6 小时定时构建
└── .nojekyll            Pages 原样发布
```

## 文档索引

| 给谁看 | 文件 |
|---|---|
| 用户 / 访客 | [README.md](./README.md)、[docs/使用指南.md](./docs/使用指南.md) |
| AI / 未来的自己 | [AGENTS.md](./AGENTS.md) |
| 开发者 | [DEVELOPMENT.md](./DEVELOPMENT.md)、[docs/架构.md](./docs/架构.md)、[docs/问题记录/索引.md](./docs/问题记录/索引.md) |
| 所有人 | [CHANGELOG.md](./CHANGELOG.md) |

文档按 [单项目规范](https://github.com/Simiely/knowledge-base/tree/main/%E6%A8%A1%E6%9D%BF%E5%BA%93/%E5%8D%95%E9%A1%B9%E7%9B%AE%E8%A7%84%E8%8C%83) 的 4 文件分层维护：按「给谁看」分层、超阈值才拆、拆分后主文件 = 门面 + 索引、问题记录与经验库同模板。

## 数据与版权

- 订阅清单 `feeds.json`：6 个原有 RSS 源 + **澎湃新闻 7 条**（首页头条 / 时事 / 财经 / 思想 / 国际 / 科技走 RSSHub 路由，热榜走澎湃官方 JSON 接口）；RSSHub 多实例竞速，首个成功胜出。
- **原文链接永久保留**：`articles.csv` 的 `link` 列不会被空值覆盖，另外追加归档到 `links.csv`（只追加、不清理、记录首次出现日期）。
- **正文快照 7 天自动清理**：`fetched_at` 记录抓取时刻，超过 7 天清空 `content`、把 `tag` 改为「快照·正文已过期」，标题 / 摘要 / 来源 / 时间 / 链接全部保留。可用 `--prune-days` 调整口径。
- 23 条**全部有内文简介**；7 篇正文快照是 2026-11-05 按原文段落抓取整理的快照、非逐字全文，现在默认折叠，不作为主要阅读内容。
- 正文版权归原作者，仅作个人离线阅读，完整版请阅读原文。

## 隐私

公开仓库，禁止写入任何凭据、个人信息或本地绝对路径；构建与推送所需的凭据只通过环境变量 / CI Secrets 传入，不进入仓库文件。
