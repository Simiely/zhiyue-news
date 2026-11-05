---
tags: [csv, packaging, inline, preview]
date: 2026-11-05
status: stable
related: [预览沙箱白屏-构建期渲染.md]
source: https://github.com/Simiely/zhiyue-news/blob/main/CHANGELOG.md
---
# 单文件脱离CSV-内联数据包

**TL;DR**：只发 HTML 不带 CSV，数据就没了；而预览里连本地 `fetch` 都不许。解法是把整份 CSV 内联进 HTML，并连数据文件一起打包交付。

## 问题

用户指出「打个压缩包吧，不然 CSV 没有，不就没效果了」；同时希望"用 HTML 直接看信息"。只给一个 HTML 时，运行时读 `./news.csv` 在预览沙箱里被 CSP 拦掉，`file://` 的 `origin=null` 也禁止跨域读同目录文件。

## 根因

1. 外部 CSV 依赖 `fetch`，预览器 `connect-src 'none'` 会在网络层拦掉
2. `file://` origin 为 `null`，浏览器默认禁止本地文件读取
3. 交付物只给单文件，用户拿到手后没有数据文件也无法替换内容
4. 内嵌的旧数据是编造示例，不是真实订阅

## 解决

- 把真实抓取的 `articles.csv`（23 条、7 篇含正文）**整份内联**进 HTML 的 `INLINE_DATA_START/END` 区块，作为 `EMBEDDED_CSV`
- `boot()` 合并内联包与本机缓存；`state.packMode = isOfflinePreview()` 时**不发起任何自动外网请求**，直接读内联数据
- 离线模式禁用自动抓全文，保证预览零请求
- 交付改为压缩包：HTML + `articles.csv` + `news.csv` + `snapshot.csv` + `feeds.json` + 两个构建脚本 + README + Actions 工作流
- 新增 `build.py --offline`：改完 CSV 不联网就能重新内联，秒级生效

```js
const EMBEDDED_CSV = `id,channels,title,...`;  // 构建期注入
if(!state.items.length) state.items = rowsToItems(parseCSV(EMBEDDED_CSV));
```

实测：iframe 沙箱 + 外网全拦下，23 条 / 7 篇全文可读，0 个外网请求、0 报错。

## 预防

- 交付"单文件能看"的页面时，确认关键数据已在文件里，不是靠相对路径运行时加载
- 数据文件仍要一起给，否则用户无法维护；两者不矛盾
- 生成内联块时用标记包裹，方便幂等重建
- 读 CSV 用 `utf-8-sig`，否则 BOM 会混进第一个表头字段名

## 来源

提炼自 [Simiely/zhiyue-news](https://github.com/Simiely/zhiyue-news) v1.4：
- [CHANGELOG.md](https://github.com/Simiely/zhiyue-news/blob/main/CHANGELOG.md)
- [build.py](https://github.com/Simiely/zhiyue-news/blob/main/build.py) `rebuild_html()`
