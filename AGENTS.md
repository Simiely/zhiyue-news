# AGENTS.md · 项目规则

> 📌 **文档基线**：2026-11-06（commit `c35c70c`）按 knowledge-base 单项目规范完成 v1.9.1（同步提速 7s→0.6s）
> **更新文档/代码后，请更新此行**（日期 + 新 commit hash），并在 CHANGELOG 追加版本

只写代码里看不出的信息；核心约束 150 词内，细节按需 @引用。

## 技术栈

- Python 3.11（CI）/ 3.10+（本地），**仅标准库**，零第三方依赖
- 纯 HTML + CSS，交互版含内联 JS；静态版依赖 CSS `:has()`（不支持时退化为显示全部）
- GitHub Actions（定时构建）+ GitHub Pages（Deploy from a branch / main / root）
- 数据格式：`articles.csv` **15 列**（含 `fetched_at`），`content` 用 `|` 分段，`# ` 前缀为小标题；`links.csv` 5 列为永久链接台账

## 关键坑

1. **预览沙箱会剥离脚本、用 `connect-src 'none'` 拦 fetch**：任何"运行时才生成"的内容都可能白屏 → 列表与正文必须构建期写进 DOM。
2. **`window.open` 在 `sandbox` iframe 里静默失败**：外链一律用普通 `<a href>`，并把 URL 明文显示在按钮上供长按复制。
3. **按钮抓不到数据不是代码 bug，是时机问题**：运行时动作无法缓存；要可点就把结果预生成（`radio` + `label` + `:has()`）。
4. **构建脚本抓取失败会清空已有数据**：`merge()` 必须按 id/标题/链接合并，抓不到正文时保留上一版 `content`。
5. **CSV BOM 与重复 `@media` 会静默破坏结果**：读 CSV 用 `utf-8-sig`；CSS 嵌套块多写一层会让整段样式不生效。
6. **正文 TTL 不能按"合并成功"续期**：抓不到新正文而沿用旧正文时，必须连同旧的 `fetched_at` 一起保留，否则 7 天清理永远不会触发；`link` 是永久字段，新结果没给链接要沿用旧值，绝不写空。
7. **限流别用全局串行链**：`Promise.any` 里只要有一个通道排队 pending，整次同步就无法快速失败；排队必须可 abort、有上限，且明确失败时要立即收敛。手动点击要能取消在途自动同步，不要只弹「正在同步中」。

## 约定

- UI 文案、注释、文件名用中文；问题记录**一坑一篇**，格式与 [knowledge-base 条目模板](https://github.com/Simiely/knowledge-base/blob/main/%E6%A8%A1%E6%9D%BF%E5%BA%93/%E6%A8%A1%E6%9D%BF/%E6%9D%A1%E7%9B%AE%E6%A8%A1%E6%9D%BF%E4%B8%8E%E4%BD%BF%E7%94%A8%E8%AF%B4%E6%98%8E.md) 完全一致
- 不编造新闻、阅读量、摘要或原文链接；没抓到就如实标注
- 公开仓库隐私红线：凭据 / 个人信息 / 本地绝对路径一律不入库
- 文档基线用 **commit hash**（提交级），便于 `git diff <基线hash> HEAD`

## 常用命令

```bash
python3 build.py --offline   # 不联网，仍落盘 CSV / 归档链接 / 清理过期正文
python3 build.py             # 联网重抓并重建
python3 build.py --prune-days 14   # 改正文保留期
python3 build_static.py      # 重建两份页面 + 注入兜底
python3 -m http.server 8000  # 本地看交互版
```

## 详细规则（按需 @引用）

- @docs/架构.md
- @docs/使用指南.md
- @docs/问题记录/索引.md
