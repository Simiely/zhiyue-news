# CHANGELOG.md

按版本分节，不拆分。版本号为文档/功能迭代标记。

## v1.9.3 · 预览信息增强：分层展示 + 三档密度（2026-11-06）

- 定位「信息太少」是**三个截断叠加**：`build.py` 把摘要硬截到 68 字、交互版 CSS `line-clamp:1/2`、7 篇正文全塞进默认收起的 `<details>`
- `build.py` 摘要上限 `68 → 240`；从已有 `content` 首段回灌较长提要，当前 23 条中 5 条立刻变充实；`normalizeItems()` 运行时上限 `120 → 300`
- 静态版卡片改为分层：**一句摘要 → 完整内文提要 → 正文预览前 3 段 → 6 格条目信息 → 原文按钮 → 折叠完整快照**；空值如实写「未提供」，无正文条目写清「只提供摘要」，不编造
- 新增零脚本 `cMore` 控件（默认勾）+ 原 `cCompact`，纯 CSS `:has()` 实现**详细 / 标准 / 简洁**三档；实测可见文本 10,292 / 5,343 / 3,385 字，**原文按钮三档都保留**
- 交互版新增 `state.moreInfo`（默认开，`html[data-more]`）、`previewHTML()`（卡片前 2 段 + 共 N 段）、`metaHTML` 追加段数；阅读页追加正文预览前 3 段 + 6 格信息；设置面板加「卡片显示详细预览」
- 交互版 CSS 在详细档放开 `line-clamp:unset`；仍不自动抓全文、阅读页无 loading
- 验证：静态版禁用 JS 23 预览 / 23 信息网格 / 138 格 / 7 折叠快照 / 23 原文或搜索按钮；三档切换正常；交互版 19 卡全带预览、阅读页 6 格信息；沙箱与禁用 JS 兜底零报错
- 文档：问题记录新增第 12 篇，README / 使用指南 / 架构 / AGENTS / DEVELOPMENT 同步

## v1.9.2 · 改为「标题 + 内文简介 + 点卡片打开原文」（2026-11-06）

- 用户明确「抓取不到全文也没关系」：**不再默认抓取全文**。`build.py` 的 `MAX_ARTICLE_FETCH` 默认 `0`，RSS 自带 `content:encoded` 只作折叠的「本地快照」；`--with-fulltext` 可恢复按需抓取
- 页面不再自动触发 `loadFullText()`，`state.autoFull` 默认 `false`，打开文章不再出现 4 秒 loading
- 交互版新增 `state.openMode`（默认 `link`）与 `handleOpen()`：**点有链接的卡片直接 `window.open` 新窗口打开原文**，不进站内阅读页；`noopener,noreferrer`
- `openExternal` 拦截检测保留：预览沙箱弹不出新窗口时自动弹菜单（复制链接 / 按标题搜索 / 本页加载原文 / 再试），并明文显示完整 URL
- `readerBodyHTML` 重写为「简介卡（含原文域名）+ 蓝色主按钮『↗ 在新窗口打开原文』+ ⋯ 兜底」，已有正文快照折叠进 `<details class="rd-snapshot">`，默认收起
- 设置面板「打开文章时自动加载全文」改为「**点卡片直接打开原文**」开关，关掉可回退到站内阅读页
- 静态版 `build_static.py`：标题包成 `<a class="s-title-link" target="_blank" rel="noopener noreferrer">`，卡片加蓝色 `s-open-primary` 按钮（印完整 URL），正文快照折叠进 `<details class="s-snap">`；紧凑模式只收起快照，不隐藏简介与主按钮
- **无链接条目不编造 URL**：改给「⌕ 按标题搜索原文」的 Bing 链接（零脚本可点），23 条卡片每条都有可点的出路
- 验证：静态版禁用 JS 链接属性正确；交互版点卡片新开 1 页且阅读页不打开；reader 模式无 loading；预览沙箱被拦时兜底菜单出现；紧凑模式主按钮仍可见；`articles.csv` 23 条全部有简介
- 文档：问题记录新增第 11 篇，README / 使用指南 / 架构 / AGENTS / DEVELOPMENT 同步

## v1.9.1 · 同步提速：从 7 秒到 0.6 秒（2026-11-06）

- 定位「全部请求立即 403 仍等 7 秒」根因：RSS2JSON 的**全局串行节流链**（7 源 × 1.2 s 排队）让 `Promise.any` 一直 pending，只能靠 `SYNC_BUDGET` 硬超时收尾
- 删掉全局链，改「延迟 600 ms + 独立短超时 + 可 abort 取消」；`abortableDelay` 正确清理监听，不再累积
- 预算收紧：`SYNC_BUDGET 7500→4000`、`FEED_BUDGET 6800→3500`、`CHANNEL_TIMEOUT 5200→2600`、`FULL_TIMEOUT 7000→4000`
- 预览 / 离线模式新增 `PREVIEW_SYNC_BUDGET=2500` 快速探测，2.5 秒无结果即停并明确提示
- 手动点击不再被 `state.syncing` 拦下：先 `activeSyncCtl.abort()` 取消在途自动同步，再由 `syncSeq` 让旧结果作废并立即接管
- 启动自动同步延后 1.2 秒，先把内容渲染出来
- 新增进度反馈 `state.syncDone` + `updateSyncBar()`（只改状态条文字，不整页 render）
- 顺手修回归：`updatesSection()` 调用了未定义的 `unreadItems()`，同步拿到新内容时会抛 `ReferenceError`
- 实测（393×852）：全部 403 手动同步 **7009→638 ms**；全挂起 **6814→3227 ms**；预览点同步 **~7500→824 ms**；快通道成功 112 ms 无回退
- 文档：问题记录新增第 10 篇，AGENTS / DEVELOPMENT / 使用指南 / 架构同步

## v1.9.0 · 订阅指定内容 + CSV 落盘 + 链接永久保留 + 正文 7 天清理（2026-11-06）

- `feeds.json` 新增**澎湃新闻 7 条**：首页头条 / 时事 25950 / 财经 25951 / 思想 25952 / 国际 122908 / 科技 119908 走 RSSHub 路由 + 官方 JSON 热榜 `thepaper_hot`
- RSSHub 多实例竞速（`rsshub.rssforever.com` → `rsshub.app`），首个有效结果胜出，逐源打印失败原因
- `articles.csv` 从 14 列扩到 **15 列**（新增 `fetched_at` 正文抓取时刻），旧数据平滑迁移
- **每次刷新都落盘**：`prune_content → write_csv → write_links → rebuild_html`，`--offline` 同样执行
- **原文链接永久保留**：`link` 永不被空值覆盖，另建 `links.csv`（5 列、只追加不清理、记录 `first_seen`）
- **正文 7 天自行清理**：超过 TTL 清空 `content`、`tag` 改「快照·正文已过期」，标题 / 摘要 / 来源 / 时间 / 链接全留；支持 `--prune-days N` / `--no-prune`
- 修复 TTL 虚假续期：沿用旧正文时连同旧 `fetched_at` 一起保留
- 交互版新增**绑定本地 articles.csv**（File System Access API + IndexedDB），同步 / 刷新后自动写回 15 列 CSV；沙箱与 `file://` 降级为导出
- 交互版 `HEADERS` / `toCSV` 同步 15 列，频道池加「时政 / 思想」
- Actions 显式 `--prune-days 7` 并把 `links.csv` 纳入提交
- 文档同步：README 新增「订阅指定内容 · 数据生命周期」，使用指南 / 架构补字段与验证矩阵，问题记录新增第 9 篇
- 验证：澎湃热榜 JSON 与 RSSHub RSS（含 CDATA `content:encoded`）mock 解析通过；13 源全 403 时 23 条数据前后一致；8 天前正文被清、链接保留；禁用 JS / 沙箱 Blob / 真实浏览器三环境零报错

## v1.8.0 · 按单项目规范重组文档并推送 GitHub

- 按 [knowledge-base 单项目规范](https://github.com/Simiely/knowledge-base/tree/main/%E6%A8%A1%E6%9D%BF%E5%8D%95%E9%A1%B9%E7%9B%AE%E8%A7%84%E8%8C%83) 建立四件套：`README.md` / `AGENTS.md` / `DEVELOPMENT.md` / `CHANGELOG.md`
- `docs/` 生长式拆分：使用指南、架构说明、8 篇一坑一篇的问题记录 + 索引
- `AGENTS.md` 顶部写入文档基线（日期 + commit hash），支持 `git diff <基线hash> HEAD`
- 创建公开仓库 `Simiely/zhiyue-news` 并推送全部产物；启用 GitHub Pages
- 全仓隐私检查：无凭据、无个人信息、无本地绝对路径

## v1.7.0 · 按钮结果预生成（零 JS 可点）

- 频道 / 来源 / 字号 / 深浅色 / 紧凑 / 只看含正文 改为 `radio + label + CSS :has(:checked)`
- 禁用 JavaScript 下多状态可同时保持（科技 + 大字 + 浅色）；不支持 `:has()` 时退化为显示全部
- 「查看原文」在按钮上明文显示完整 URL，宿主禁止跳出时可长按复制
- `index.html` 压到 51 KB；交互版注入同一组控件与兜底 DOM

## v1.6.0 · 默认深色 + 交互版零脚本兜底

- 两份页面均默认 `data-theme="dark"`，交互版 `state.theme` 默认值同步
- 最开始的 `zaker-news.html` 注入构建期兜底 DOM：脚本能跑则 `render()` 覆盖，被拦则原样可读
- 右上夜间模式按钮仍可切回浅色并记住选择

## v1.5.0 · 零脚本静态版 + GitHub Pages 工作流

- 新增 `index.html`：零 `<script>`、零 fetch、零 localStorage，内容直接写进 DOM
- 新增 `build_static.py`、`.github/workflows/update.yml`（每 6 小时抓取重建）、`.nojekyll`
- 调研 GitHub 生态静态 RSS 方案（gereader / llun feeds / newsnow 等），确定「构建期渲染 + Pages」路径

## v1.4.0 · 离线数据包与压缩包交付

- 编造数据全部清除，换成 6 个公开 RSS 真实订阅源
- `articles.csv` 14 列；7 篇按原文段落整理的正文快照；`snapshot.csv` 溯源
- 整份 CSV 内联进 HTML，预览 / `file://` 下零外网请求
- 新增 `build.py`（联网抓取 + 重建内联数据）

## v1.3.0 · 原文打开修复

- `window.open` 统一拦截检测，被拦时给出新窗口 / 本页阅读 / 复制链接 / 标题搜索四条兜底
- 链接规范化：解码 `&amp;`、相对地址补全、拒绝非 HTTP 协议、`guid` 不再冒充链接
- 按标题归一化合并，实时 RSS 的真实链接补回快照条目且不产生重复

## v1.2.0 · 完整全文引擎

- 解析层优先取 `content:encoded / content / description` 中最长原始 HTML，白名单清洗后保留段落/小标题/引用/列表
- 只有摘要时按需并行竞速抓取原文，Readability 式容器选择，7 秒硬上限
- 全文仅存本机、标注来源与抓取时间；失败 5 分钟内不重试；支持粘贴全文

## v1.1.0 · 刷新稳定性修复

- 通道由串行改并行竞速，首个有效结果胜出并取消其余请求
- 移除提前返回的外层 `race`，整次同步用 `Promise.all` 收敛；单源 6.8 秒 / 单次 7.5 秒硬上限
- 加同步序号丢弃陈旧结果；失败保留上次成功内容；下拉刷新等同步结束再复位

## v1.0.0 · 首版

- iOS 风格移动端新闻页：大标题 + 毛玻璃导航、卡片杂志流、快讯时间线、热门榜
- 阅读页、搜索高亮、收藏点赞、夜间模式、字号、频道订阅、底部 Tab
- 订阅更新：CSV/JSON/RSS 导入、自动同步频率、NEW 标记与未读数
