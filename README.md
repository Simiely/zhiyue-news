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
| 脚本解析 CSV 渲染列表 | 构建期把 23 条新闻、7 篇正文写进 DOM |
| JS 处理点击 | `<label>` + `radio/checkbox` + CSS `:has(:checked)`，禁用 JS 也能点 |
| `window.open` 跳原文 | 普通 `<a href>`，按钮上直接显示完整 URL 供长按复制 |
| 运行时抓 RSS | GitHub Actions 每 6 小时构建快照，浏览器端零请求 |

## 快速开始

**① 直接看（零配置）**
打开 [`index.html`](./index.html) —— 默认深色，23 条真实订阅、7 篇正文，频道 / 来源 / 字号 / 深浅色 / 紧凑 / 只看含正文都能点，不需要联网、服务器或账号。

**② 完整交互版**
```bash
python3 -m http.server 8000
# 浏览器打开 http://localhost:8000/zaker-news.html
```
可用联网同步、订阅管理、全文抓取、搜索、收藏、原文跳转。`zaker-news.html` 内置零脚本兜底，脚本被拦时降级为同一份离线内容。

**③ 更新数据**
```bash
python3 build.py            # 联网重抓 RSS → 更新 articles.csv → 重建两份页面
python3 build.py --offline  # 只改了 CSV，不联网
python3 build_static.py     # 只重建页面（含预生成按钮状态）
```
纯 Python 标准库，无第三方依赖。抓取失败会保留上一版数据，不会清空。

详细步骤见 [docs/使用指南.md](./docs/使用指南.md)。

## 双轨页面

| 文件 | 定位 | 脚本 |
|---|---|---|
| [`zaker-news.html`](./zaker-news.html) | 最开始的完整交互版，已修复；默认深色，内置零脚本兜底 | 内联 JS + 兜底 DOM |
| [`index.html`](./index.html) | 静态快照版，Pages 入口，51 KB | 零 `<script>`、零 fetch、零 localStorage |

两份页面都默认 `data-theme="dark"`，都带同一组**不需要 JS 的按钮**：推荐 / 科技 / 生活 / 国际 / 娱乐 / 健康、6 个来源、深色 / 浅色 / 小字 / 标准 / 大字 / 紧凑 / 只看含正文。多个状态可同时保持。

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
├── articles.csv         真实数据包（14 列）
├── news.csv             空模板
├── snapshot.csv         抓取溯源快照
├── feeds.json           6 个公开 RSS 源
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

- 数据来自 `feeds.json` 的 6 个公开 RSS，快照日期 2026-11-05；23 条为真实标题 / 来源 / 时间 / 链接。
- 7 篇正文是**按原文段落抓取整理的快照，非逐字全文**；未抓到正文的只显示真实摘要，未存链接的不编造链接。
- 正文版权归原作者，仅作个人离线阅读，完整版请阅读原文。

## 隐私

公开仓库，禁止写入任何凭据、个人信息或本地绝对路径；构建与推送所需的凭据只通过环境变量 / CI Secrets 传入，不进入仓库文件。
