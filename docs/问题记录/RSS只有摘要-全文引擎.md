---
tags: [rss, fulltext, parsing, readability]
date: 2026-11-05
status: stable
related: [查看原文无反应-弹窗拦截与链接解析.md]
source: https://github.com/Simiely/zhiyue-news/blob/main/CHANGELOG.md
---
# RSS只有摘要-全文引擎

**TL;DR**：RSS 的 `description` 按规范只是摘要，全文要另取 `content:encoded`；旧解析还把长文 `stripHTML` 切碎，两层问题叠加。

## 问题

订阅的文章点开只有一两段，看不到完整正文；用户反复反馈"看不了全文"。

## 根因

1. 实测 6 个源：多数只给带「查看全文」的短摘要，个别几乎只有标题链接；`content:encoded` 不是强制字段
2. 旧代码把整段 HTML `stripHTML` 成纯文本，再按 `|` / `。` 切段、丢掉短于 8 字的、最多留 8 段 → 长文被切碎截断
3. 阅读页只留一个「查看原文 ↗」跳出去，预览沙箱里又跳不动

## 解决

**解析层**：优先取 `content:encoded / content / description` 中最长的原始 HTML，白名单清洗后保留段落、小标题、图片、引用、列表；`# ` 前缀渲染成 `<h2>`，不再切碎。源自带全文 → 打开即完整可读，零请求。

**按需抓取**：只有摘要时并行竞速阅读器与跨域代理，取回原文 HTML 后选 `article` / `main` / 常见正文容器，剔除导航、广告、页脚；首个有效结果胜出，7 秒硬上限。

**降级**：全失败时写明原因，保留「查看原文」和「粘贴全文」；失败后 5 分钟内不自动重试。全文只存本机，标注来源与抓取时间，可重新抓取。

```python
# build.py：构建期也做同样的事，把正文写进 CSV
for ch in it:  # 优先 content:encoded
    ...
content = "|".join(paras)   # 段落分隔，# 前缀为小标题
```

实测：自动加载出多段 + 小标题 + 引用 + 列表；feed 自带 `content:encoded` 直接渲染；XSS 检查脚本/`javascript:` 链接全部被清洗。

## 预防

- 不要假设 RSS 有全文；先探测 `content:encoded`，再设计降级
- 解析 HTML 正文要保留结构，别 `stripHTML` 后按标点切段
- 抓不到的正文**如实标注「仅摘要」**，不能把摘要伪装成全文
- 全文抓取尊重版权：保留来源与原文链接，仅作本机个人阅读

## 来源

提炼自 [Simiely/zhiyue-news](https://github.com/Simiely/zhiyue-news) v1.2 / v1.4：
- [CHANGELOG.md](https://github.com/Simiely/zhiyue-news/blob/main/CHANGELOG.md)
- [build.py](https://github.com/Simiely/zhiyue-news/blob/main/build.py) `html_to_paras()` / `extract_article_html()`
