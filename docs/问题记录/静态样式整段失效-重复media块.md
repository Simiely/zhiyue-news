---
tags: [css, generator, debugging]
date: 2026-11-05
status: stable
related: [按钮点击抓不到-运行时与构建期.md]
source: https://github.com/Simiely/zhiyue-news/blob/main/build_static.py
---
# 静态样式整段失效-重复media块

**TL;DR**：生成器把 `@media (prefers-color-scheme:dark){` 重复拼了一行，导致后续整段 CSS 规则被浏览器丢弃，页面变成无样式裸 HTML。

## 问题

静态版 `index.html` 生成后截图发现卡片没有圆角、标题字号是默认 16px、整体没有 iOS 视觉；但 DOM 里 23 张卡片都在，文本也能读到。

## 根因

1. `build_static.py` 重构时，`EXTRA_CSS` 里原有 `@media (prefers-color-scheme:dark){` 一行，编辑时又加了一次，形成嵌套：
   ```css
   @media (prefers-color-scheme:dark){
   @media (prefers-color-scheme:dark){
     :root{...}
   }
   .static-note{...}   /* 实际被吃进了未闭合的 @media 块 */
   ```
2. 浏览器 CSS 解析器遇到未正确闭合的 `@media` 会丢弃块内后续规则；`document.styleSheets[0].cssRules.length` 只剩 40 条（应为 75 条）
3. 计算样式验证暴露问题：`.s-item` borderRadius `0px`、`.s-title` fontSize `16px`

## 解决

1. 删掉重复的 `@media` 声明，改为显式的 `html[data-theme="dark"]` / `html[data-theme="light"]` 变量覆盖（默认深色，不依赖系统偏好）
2. 补齐 `--red` 变量，避免 `var(--red)` 未定义
3. 加生成后自动校验：`cssRules.length`、关键类计算样式、`<script` 计数

```python
# 生成器自检
r = await pg.evaluate("document.styleSheets[0].cssRules.length")
assert r >= 70
```

修复后 `cssRules=75`、卡片 `14px`、标题 `17px`、正文 `17px`、chip `20px`，视觉恢复正常。

## 预防

- 生成器拼接 CSS 时，把"基础变量"和"条件覆盖"分开写，别嵌套 `@media`
- 每次改生成器都要看**计算样式**（getComputedStyle），不能只看「文本在不在」
- 主题默认值写死在 `<html data-theme>` 上，别依赖 `prefers-color-scheme`，否则预览器里颜色不可控
- 把 `cssRules` 计数、关键类样式纳入构建后的自动校验

## 来源

提炼自 [Simiely/zhiyue-news](https://github.com/Simiely/zhiyue-news) v1.5 / v1.7：
- [build_static.py](https://github.com/Simiely/zhiyue-news/blob/main/build_static.py) `BASE_CSS` / `state_css()`
