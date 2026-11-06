---
tags: [csv, ttl, data-lifecycle, copyright, web]
date: 2026-11-06
status: stable
related: [构建抓取失败清空数据-保留上一版.md, 单文件脱离CSV-内联数据包.md]
source: https://github.com/Simiely/zhiyue-news/blob/main/build.py
---
# 正文TTL与链接永久保留

**TL;DR**：正文快照是短期缓存、原文链接是长期索引，两者生命周期不同却常被塞进同一张表一起覆盖；给 CSV 加 `fetched_at` 列 + 独立 `links.csv` 追加台账，就能「正文 7 天自动清理、链接一条不丢」。

## 问题

用户要求：数据都存 CSV，刷新一次就落盘；**原文链接要保持存储**；**正文超过 7 天自行清理**。

原来的 `articles.csv` 是 14 列，`content` 与 `link` 混在一起，既没有抓取时刻，也没有"哪些链接曾经出现过"的记录。三个具体风险：

1. 抓取失败或源改版时，`merge()` 用新结果覆盖，可能把 `link` 写空；
2. 正文快照长期堆在 CSV 里，体积膨胀、版权上也不适合永久留存；
3. 页面数据只存 localStorage，换浏览器 / 清缓存就丢，用户希望"跟文件走"。

## 根因

- **缺时间维度**：没有 `fetched_at`，无法判断一段正文是什么时候抓的，TTL 无从算起。
- **所有字段同一生命周期**：链接需要永久、正文只需短期，却由同一条 `merged.update()` 一起处理。
- **浏览器与文件系统的边界**：网页不能静默写本地文件，只有构建脚本（服务端 / 本地 Python）能落盘；但 https / localhost 下 File System Access API 可以绑定文件后自动写回。

## 解决

**① CSV 加一列 + 每次刷新落盘**

```
HEADERS = [... , "content", "link", "fetched_at"]   # 15 列
```

`main()` 统一执行：`read/build_rows → prune_content → write_csv → write_links → rebuild_html`。`--offline` 也跑完整链路，所以"刷新一次就存到本地"成立；`articles.csv` 是唯一真相源。

**② 链接永久台账（只追加）**

```python
def write_links(rows):
    old = {r["link"]: r for r in read_links()}
    for r in rows:
        if r["link"] and r["link"] not in old:
            old[r["link"]] = {..., "first_seen": today}
    write_all(old)   # 不删除、不清理
```

`merge()` 里再加一条硬保护：新结果没给链接时沿用旧 `link`，**绝不写空**。

**③ 正文 7 天 TTL**

```python
def prune_content(rows, days=7):
    for r in rows:
        if r["content"] and content_age_days(r) > days:
            r["content"] = ""
            r["tag"] = "快照·正文已过期"
            r["fetched_at"] = ""
    return rows, n
```

`content_age_days()` 优先按 `fetched_at`（抓取时刻），缺失时退回 `published_at`；旧版 14 列 CSV 平滑迁移时按构建当天补齐。

**④ TTL 不能被虚假续期**：抓不到新正文而沿用旧正文时，必须连同旧的 `fetched_at` 一起保留，否则每次构建都把计时起点刷成今天，7 天清理永远不触发。

**⑤ 页面端自动落盘**：https / localhost 下用 `showSaveFilePicker` 绑定 `articles.csv`，句柄存 IndexedDB，每次 `syncAll()` / `loadFromFetch()` 结束调 `autoSaveLocalCSV()` 写回 15 列 CSV；沙箱、`file://`、不支持的浏览器明确提示降级为「导出 CSV」。

实测：造 8 天前正文 → 2 篇清空、链接与元数据全留、2 天前的正文保留；13 个源全 403 时 23 条数据前后一致；导出 CSV 往返 15 列、`fetched_at` 与 `link` 不丢；禁用 JS / 沙箱 / 真实浏览器三环境零报错。

## 预防

- 设计数据表时先问：**每列的生命周期一样吗？** 不一样就拆字段或拆表。
- "永久"字段要在合并逻辑里显式保护，不能只靠"新值非空才覆盖"的通用规则。
- TTL 的计时起点要随内容一起继承，别在合并时重置。
- 网页写本地文件必须处理安全上下文与权限失效，且一定要有导出降级路径。
- 口径（按抓取时刻 vs 按发布时间）要在文档里写死，否则用户按自己理解会以为实现错了。

## 来源

提炼自 [Simiely/zhiyue-news](https://github.com/Simiely/zhiyue-news) v1.9.0：
- [build.py](https://github.com/Simiely/zhiyue-news/blob/main/build.py) `prune_content()` / `write_links()` / `merge()`
- [README.md](https://github.com/Simiely/zhiyue-news/blob/main/README.md) 「订阅指定内容 · 数据生命周期」
