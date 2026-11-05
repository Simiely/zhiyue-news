#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把「点击按钮后的每一种结果」在构建期预生成，做成零 JS 也能点的静态页面。

原理：
  按钮 = 运行时行为，要 JS 执行；预览沙箱可能剥离脚本 / 用 connect-src 'none' 拦 fetch /
  禁 window.open，所以点了没反应。
  缓存 = 构建期产物，写死在 HTML 里，浏览器只负责显示，不需要执行任何东西。

本脚本走得更远一步：连「频道切换 / 字号 / 夜间模式 / 只看全文 / 按来源」这些原本靠
按钮的动作，也用 <input type=radio> + <label> + CSS :has(:checked) 预生成好所有状态。
label 点击是浏览器原生行为，禁用 JavaScript 同样生效，CSP 管不着，且多个状态可同时保持。

输出：
  index.html        零脚本、默认深色、所有控件可点的静态快照
  zaker-news.html   最开始的交互版：注入同样的兜底 DOM/CSS，脚本被拦时也能点

用法：python3 build_static.py
"""
from __future__ import annotations

import csv
import datetime
import html as H
import io
import json
import pathlib
import re
import string

ROOT = pathlib.Path(__file__).resolve().parent
CSV_FILE = ROOT / "articles.csv"
SRC_HTML = ROOT / "zaker-news.html"
OUT = ROOT / "index.html"

CSS_START = "/* STATIC_FALLBACK_CSS_START */"
CSS_END = "/* STATIC_FALLBACK_CSS_END */"
FB_START = "<!-- STATIC_FALLBACK_START -->"
FB_END = "<!-- STATIC_FALLBACK_END -->"


def e(s) -> str:
    return H.escape(str(s or ""), quote=True)


def read_rows() -> list[dict]:
    with CSV_FILE.open(encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def ordered(values: list[str], prefer: list[str]) -> list[str]:
    out = [c for c in prefer if c in values]
    for v in values:
        if v not in out:
            out.append(v)
    return out


def channels_of(rows) -> list[str]:
    vals = []
    for r in rows:
        for c in (r.get("channels") or "").split("|"):
            c = c.strip()
            if c and c not in vals:
                vals.append(c)
    return ordered(vals, ["推荐", "科技", "生活", "国际", "娱乐", "财经", "健康"])


def sources_of(rows) -> list[str]:
    vals = []
    for r in rows:
        s = (r.get("source") or "").strip()
        if s and s not in vals:
            vals.append(s)
    return vals


def row_channels(r) -> list[str]:
    return [c.strip() for c in (r.get("channels") or "").split("|") if c.strip()]


def time_text(row: dict) -> str:
    s = (row.get("published_at") or "").strip()
    if not s:
        return "时间未提供"
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?", s)
    if m:
        y, mo, d, hh, mm = m.groups()
        return "%s月%s日%s" % (int(mo), int(d), (" " + hh + ":" + mm) if hh else "")
    return s[:16]


# ============ 内容 ============

def body_html(row: dict, date: str) -> str:
    paras = [p.strip() for p in (row.get("content") or "").split("|") if p.strip()]
    link = (row.get("link") or "").strip()
    origin = ('<a class="s-origin" href="%s" target="_blank" rel="noopener noreferrer">查看原文 ↗'
              '<code>%s</code></a>' % (e(link), e(link))) if link else ""
    if not paras:
        nolink = ('<div class="s-nolink">该订阅源未提供原文链接，同步成功后会自动补齐；本页只显示真实摘要，不编造正文。</div>') if not link else ""
        return ('<div class="s-body"><div class="s-only"><b>该订阅源只提供摘要</b><br>%s</div>'
                '%s%s<div class="s-copy">正文版权归原作者，完整版请阅读原文。</div></div>') % (
            e((row.get("summary") or "").strip() or "暂无摘要"), nolink, origin)

    parts = []
    for p in paras:
        parts.append("<h2>%s</h2>" % e(p[2:]) if p.startswith("# ") else "<p>%s</p>" % e(p))
    note = ('<div class="s-only" style="margin-top:18px">以上为 %s 抓取时按原文段落整理的<b>正文快照</b>，'
            '非逐字全文。版权归原作者，完整版请点「查看原文」。</div>') % e(date)
    nolink = '<div class="s-nolink">该订阅源未提供原文链接，同步成功后会自动补齐。</div>' if not link else ""
    return '<div class="s-body">' + "".join(parts) + note + origin + nolink + "</div>"


def article_html(row, idx, chans, sources, date) -> str:
    rid = "a-" + re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]", "-", row["id"])[:60]
    chs = row_channels(row)
    cls = ["art"]
    for c in chs:
        if c in chans:
            cls.append("ch%d" % chans.index(c))
    src = (row.get("source") or "").strip()
    if src in sources:
        cls.append("src%d" % sources.index(src))
    full = bool((row.get("content") or "").strip())
    if not full:
        cls.append("no-full")
    tag = (row.get("tag") or "").strip()
    badge = '<span class="s-tag">%s</span>' % e(tag) if tag else ""
    new = '<span class="s-new">NEW</span>' if idx < 3 else ""
    kicker = " · ".join(chs[:2]) or "推荐"
    return ('<article class="%s" id="%s">'
            '<div class="s-kicker">%s<span class="s-open">%s</span></div>'
            '<div class="s-title">%s</div>'
            '<p class="s-sum">%s</p>'
            '<div class="s-meta"><span class="s-src">%s</span><span>%s</span>%s%s</div>'
            '%s</article>') % (
        " ".join(cls), e(rid), e(kicker),
        "含正文快照" if full else "仅摘要",
        e(row.get("title") or ""), e((row.get("summary") or "").strip()),
        e(src or "未标注来源"), e(time_text(row)), new, badge,
        body_html(row, date))


def controls_html(chans, sources, rows, date) -> str:
    """所有「按钮」都是 <label> + 隐藏 radio/checkbox，结果已预生成在 DOM 里。"""
    full = sum(1 for r in rows if (r.get("content") or "").strip())
    links = sum(1 for r in rows if (r.get("link") or "").strip())

    hidden = ['<input class="sr" type="radio" name="ch" id="ch%d"%s>' % (i, " checked" if i == 0 else "")
              for i in range(len(chans))]
    hidden += ['<input class="sr" type="radio" name="src" id="src%d"%s>' % (i, " checked" if i < 0 else "")
               for i in range(len(sources))]
    # 来源用「全部」作为第 0 项，避免默认就过滤掉内容
    hidden = hidden[:len(chans)] + ['<input class="sr" type="radio" name="src" id="srcAll" checked>'] + \
             ['<input class="sr" type="radio" name="src" id="src%d">' % i for i in range(len(sources))]
    hidden += ['<input class="sr" type="radio" name="font" id="f15">',
               '<input class="sr" type="radio" name="font" id="f17" checked>',
               '<input class="sr" type="radio" name="font" id="f21">',
               '<input class="sr" type="radio" name="theme" id="tDark" checked>',
               '<input class="sr" type="radio" name="theme" id="tLight">',
               '<input class="sr" type="checkbox" id="cCompact">',
               '<input class="sr" type="checkbox" id="cFull">']

    bar = ['<div class="ctl"><span class="ctl-t">频道</span><div class="chips">']
    for i, c in enumerate(chans):
        bar.append('<label class="chip" for="ch%d">%s</label>' % (i, e(c)))
    bar.append('</div></div>')

    bar.append('<div class="ctl"><span class="ctl-t">来源</span><div class="chips">'
               '<label class="chip" for="srcAll">全部</label>')
    for i, s in enumerate(sources):
        bar.append('<label class="chip" for="src%d">%s</label>' % (i, e(s)))
    bar.append('</div></div>')

    bar.append('<div class="ctl"><span class="ctl-t">外观</span><div class="chips">'
               '<label class="chip" for="tDark">深色</label>'
               '<label class="chip" for="tLight">浅色</label>'
               '<label class="chip" for="f15">小字</label>'
               '<label class="chip" for="f17">标准</label>'
               '<label class="chip" for="f21">大字</label>'
               '<label class="chip" for="cCompact">紧凑</label>'
               '<label class="chip" for="cFull">只看含正文 %d</label>' % full)
    bar.append('</div></div>')

    note = ('<div class="static-note">这些按钮<b>不需要 JavaScript</b>：频道 / 来源 / 字号 / 深浅色 / 紧凑 / '
            '只看含正文，全部由构建期预生成的状态实现。内容已在 HTML 里（%d 条真实订阅、%d 篇含正文、%d 条带原文链接），'
            '预览沙箱、<code>file://</code>、禁用脚本下都能点。'
            '「查看原文」是普通链接；若宿主禁止跳出，长按复制地址到浏览器打开即可。</div>') % (
        len(rows), full, links)

    head = ('<div class="sync-bar pack-bar" style="margin:12px 16px;border-radius:12px;padding:13px 14px">'
            '<span class="ub-dot" style="background:var(--tint)"></span>'
            '<div class="sb-main"><b>静态快照已就绪 · %d 条真实订阅</b>'
            '<small>%s 构建 · %d 篇含正文 · 所有控件均已预生成，无需联网与脚本</small></div></div>') % (
        len(rows), e(date), full)

    return "".join(hidden) + head + note + "".join(bar)


# ============ CSS ============

BASE_CSS = """
:root{
  --bg:#000000;--card:#1C1C1E;--pressed:#2C2C2E;--label:#FFFFFF;
  --label2:#98989F;--label3:#6E6E73;--sep:rgba(84,84,88,.6);
  --tint:#0A84FF;--tint-soft:#0A2A4A;--red:#FF453A;
  --search:#1C1C1E;--nav:rgba(20,20,22,.88);--shadow:0 1px 2px rgba(0,0,0,.25);
  --rd-font:17px;
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:#000;font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","PingFang SC","Helvetica Neue",Arial,sans-serif;
  color:var(--label);-webkit-font-smoothing:antialiased}
.device{max-width:430px;margin:0 auto;min-height:100vh;background:var(--bg);position:relative}
@media(min-width:500px){.device{min-height:92vh;margin:4vh auto;border-radius:38px;overflow:hidden;
  box-shadow:0 20px 60px rgba(0,0,0,.5)}}
.app{position:relative;min-height:100vh;display:flex;flex-direction:column}
.statusbar{height:44px;display:flex;justify-content:space-between;align-items:center;
  padding:0 26px;font-size:14px;font-weight:650;flex:none}
.sb-right{display:flex;gap:6px;align-items:center}
.sb-right svg{width:17px;height:13px;fill:var(--label)}
.bat{width:24px;height:12px;border:1.5px solid var(--label);border-radius:3px;position:relative;display:inline-block}
.bat:after{content:"";position:absolute;right:-4px;top:3px;width:2px;height:5px;background:var(--label);border-radius:0 2px 2px 0}
.bat i{position:absolute;left:1.5px;top:1.5px;bottom:1.5px;width:70%;background:var(--label);border-radius:1px}
.scroll{flex:1;overflow-y:auto;padding-bottom:96px;overscroll-behavior-y:contain}
.nav-compact{height:44px;display:flex;align-items:center;justify-content:space-between;padding:0 16px;
  background:var(--nav);backdrop-filter:saturate(180%) blur(20px);position:sticky;top:0;z-index:5}
.nc-left,.nc-actions{min-width:44px;display:flex;gap:8px}
.avatar-btn{width:30px;height:30px;border-radius:50%;background:var(--tint);color:#fff;font-size:13px;
  font-weight:700;display:grid;place-items:center;border:0}
.nc-title{font-size:16px;font-weight:650}
.large-title{padding:8px 20px 10px}
.lt-date{font-size:13px;color:var(--label2);font-weight:600}
.large-title h1{font-size:34px;line-height:1.15;margin:5px 0 2px;font-weight:750;letter-spacing:-.5px}
.large-title p{font-size:13px;color:var(--label2);margin:0}
.sec{margin:14px 0 4px}
.sec-head{display:flex;align-items:baseline;gap:9px;padding:0 20px 6px}
.sec-head h2{font-size:21px;font-weight:700;margin:0;letter-spacing:-.3px}
.sec-head .sub{font-size:12px;color:var(--label2)}
.tabbar{position:absolute;bottom:0;left:0;right:0;height:78px;display:flex;
  background:var(--nav);backdrop-filter:saturate(180%) blur(20px);border-top:1px solid var(--sep);z-index:6}
.tab{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;
  color:var(--label2);font-size:10px}
.tab svg{width:23px;height:23px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.tab.on{color:var(--tint)}
.home-indicator{position:absolute;bottom:7px;left:50%;transform:translateX(-50%);
  width:134px;height:5px;border-radius:3px;background:var(--label);opacity:.85;z-index:7}
"""


CARDS_CSS = """
/* ===== 静态控件与卡片（两套页面共用） ===== */
.sr{position:fixed;top:0;left:0;width:1px;height:1px;opacity:0;pointer-events:none;z-index:-1}
.ctl{padding:6px 0}
.ctl-t{display:block;font-size:11px;font-weight:700;color:var(--label2);padding:0 20px 5px;letter-spacing:.4px}
.chips{display:flex;gap:8px;overflow-x:auto;padding:0 16px 4px;scrollbar-width:none}
.chips::-webkit-scrollbar{display:none}
.ctl .chips{flex-wrap:wrap;overflow:visible;padding:0 16px 4px}
.ctl .chip{flex:none;padding:7px 14px;border-radius:20px;background:var(--card);font-size:12.5px;
  font-weight:600;color:var(--label);border:1px solid var(--sep);white-space:nowrap;cursor:pointer;
  text-decoration:none;display:inline-block;user-select:none}
.ctl .chip:hover{background:var(--pressed)}
.sync-bar{display:flex;gap:10px;align-items:center}
.pack-bar{background:var(--tint-soft)}
.ub-dot{width:8px;height:8px;border-radius:50%;background:var(--tint);flex:none;
  box-shadow:0 0 0 5px rgba(10,132,255,.18)}
.sb-main b{display:block;font-size:13.5px;font-weight:680}
.sb-main small{display:block;font-size:11px;color:var(--label2);line-height:1.5;margin-top:2px}
.static-note{font-size:11.5px;line-height:1.7;color:var(--label2);background:var(--card);
  border-radius:12px;padding:12px 14px;margin:12px 16px}
.static-note code{background:var(--bg);padding:1px 4px;border-radius:4px}
.art{background:var(--card);border-radius:14px;margin:10px 16px;padding:14px 16px;
  box-shadow:var(--shadow);scroll-margin-top:56px}
.s-kicker{font-size:11px;font-weight:700;color:var(--tint);letter-spacing:.3px;
  margin-bottom:7px;text-transform:uppercase}
.s-title{font-size:17px;font-weight:680;line-height:1.4;color:var(--label);margin:0 0 8px}
.s-sum{font-size:13px;line-height:1.6;color:var(--label2);margin:0 0 10px}
.s-meta{font-size:11.5px;color:var(--label3);display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.s-src{color:var(--label2);font-weight:600}
.s-tag{padding:2px 7px;border-radius:5px;background:var(--tint-soft);color:var(--tint);font-size:10.5px}
.s-new{color:var(--red);font-weight:700;font-size:10.5px}
.s-open{float:right;font-size:11px;color:var(--label2);font-weight:600;margin-top:2px}
.s-body{border-top:1px solid var(--sep);margin-top:12px;padding-top:2px}
.s-body p{font-size:var(--rd-font);line-height:1.82;color:var(--label);margin:14px 0}
.s-body h2{font-size:19px;font-weight:700;line-height:1.45;color:var(--label);
  margin:22px 0 4px;padding-left:11px;border-left:3px solid var(--tint)}
.s-only{font-size:13.5px;line-height:1.75;color:var(--label2);
  background:var(--bg);border-radius:10px;padding:12px 13px;margin:14px 0}
.s-origin{display:block;text-align:center;margin:18px 0 4px;padding:12px;
  background:var(--tint-soft);color:var(--tint);border-radius:11px;
  font-size:14px;font-weight:650;text-decoration:none;word-break:break-all}
.s-origin code{display:block;font-size:10px;font-weight:400;color:var(--label2);margin-top:5px}
.s-nolink,.s-copy{font-size:12px;line-height:1.7;color:var(--label2);
  background:var(--bg);border-radius:10px;padding:12px 13px;margin:14px 0;word-break:break-all}
.s-foot{text-align:center;font-size:11px;line-height:1.8;color:var(--label3);padding:22px 24px 40px}
.s-foot a{color:var(--tint)}
"""


def state_css(chans, sources) -> str:
    """把按钮的每一种结果预先写成 CSS 规则：label 点击只改变 :checked，不执行脚本。"""
    r = ["/* ===== 纯 CSS 状态机：所有按钮结果已预生成 ===== */"]
    # 频道：第 0 项「推荐」显示全部，其余隐藏不属于该频道的文章
    for i in range(1, len(chans)):
        r.append("html:has(#ch%d:checked) .art:not(.ch%d){display:none}" % (i, i))
    # 来源
    for i in range(len(sources)):
        r.append("html:has(#src%d:checked) .art:not(.src%d){display:none}" % (i, i))
    # 只看含正文
    r.append("html:has(#cFull:checked) .art.no-full{display:none}")
    # 紧凑：隐藏正文，只留标题与摘要
    r.append("html:has(#cCompact:checked) .art .s-body{display:none}")
    # 字号
    r.append("html:has(#f15:checked){--rd-font:15px}")
    r.append("html:has(#f21:checked){--rd-font:21px}")
    # 浅色：覆盖深色变量（默认深色）
    r.append("""html:has(#tLight:checked){
  --bg:#F2F2F7;--card:#FFFFFF;--pressed:#E5E5EA;--label:#000000;
  --label2:#8A8A8F;--label3:#C7C7CC;--sep:rgba(60,60,67,.13);
  --tint:#007AFF;--tint-soft:#EAF3FF;--red:#FF3B30;
  --search:#E4E4E9;--nav:rgba(249,249,249,.86);--shadow:0 1px 2px rgba(0,0,0,.04);
}""")
    r.append("html:has(#tLight:checked) body{background:#E5E5EA}")
    r.append("html:has(#tLight:checked) .device{background:var(--bg)}")
    # 选中态高亮（radio 组）
    ids = [("ch%d" % i, i) for i in range(len(chans))] + [("srcAll", -1)] + \
          [("src%d" % i, i) for i in range(len(sources))] + \
          [("f15", 0), ("f17", 0), ("f21", 0), ("tDark", 0), ("tLight", 0)]
    for rid, _ in ids:
        r.append('html:has(#%s:checked) label[for="%s"]{background:var(--tint);color:#fff;border-color:var(--tint)}' % (rid, rid))
    r.append('html:has(#cCompact:checked) label[for="cCompact"],'
             'html:has(#cFull:checked) label[for="cFull"]'
             '{background:var(--tint);color:#fff;border-color:var(--tint)}')
    # 不支持 :has() 的老环境：全部文章照常显示（内容不丢）
    r.append("""@supports not selector(:has(*)){
  .ctl{display:none}
}""")
    return "\n".join(r)


NOSCRIPT = """<noscript><style>
#searchWrap,#chipsWrap,#tabbar,#refresh,.foot-note,.home-indicator{display:none!important}
.scroll{padding-bottom:28px!important}
</style></noscript>"""


# ============ 模板 ============

STATIC_DOC = string.Template("""<!doctype html>
<html lang="zh-CN" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="dark light">
<title>知阅 · 真实订阅快照</title>
<style>$BASE
$CARDS
$STATE</style>
</head>
<body>
<div class="device"><div class="app" id="app">
  <div class="statusbar"><span>9:41</span><div class="sb-right">
    <svg viewBox="0 0 18 14"><path d="M1 10h2v3H1zM5 7h2v6H5zM9 4h2v9H9zM13 1h2v12h-2z"/></svg>
    <span class="bat"><i></i></span></div></div>
  <div class="scroll" id="scroll">
    <header class="nav-compact">
      <div class="nc-left"><div class="avatar-btn">阅</div></div>
      <div class="nc-title">知阅</div>
      <div class="nc-actions"></div>
    </header>
    <div class="large-title">
      <div class="lt-date">$DATE 星期四</div>
      <h1>知阅</h1>
      <p>为你精选今日要闻</p>
    </div>
    $CONTROLS
    <section class="sec"><div class="sec-head"><h2>全部资讯</h2><span class="sub">共 $N 条 · 点上方按钮筛选</span></div></section>
    $ARTICLES
    <div class="s-foot">
      数据来源：$FEEDS 个公开 RSS 订阅源 · 抓取快照 $DATE<br>
      页面不含编造内容；未抓到正文的条目如实只显示摘要，未存链接的条目不编造链接。<br>
      正文版权归原作者，仅作个人离线阅读，完整版请阅读原文。<br>
      <a href="zaker-news.html">打开完整交互版（联网同步 / 订阅 / 全文抓取）↗</a>
    </div>
  </div>
  <div class="tabbar">
    <div class="tab on"><svg viewBox="0 0 24 24"><path d="M3 11l9-8 9 8v9h-6v-6H9v6H3z"/></svg><span>首页</span></div>
    <div class="tab"><svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg><span>频道</span></div>
    <div class="tab"><svg viewBox="0 0 24 24"><path d="M6 3h12v18l-6-4-6 4z"/></svg><span>收藏</span></div>
    <div class="tab"><svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg><span>我的</span></div>
  </div>
  <div class="home-indicator"></div>
</div></div>
</body>
</html>
""")


def fallback_fragment(rows, chans, sources, date) -> str:
    return ('<div class="fb-note" style="font-size:11.5px;line-height:1.7;color:var(--label2);'
            'background:var(--card);border-radius:12px;padding:12px 14px;margin:12px 16px">'
            '当前环境未运行脚本，以下内容与全部控件状态已由构建期预生成，'
            '点按钮即可切换，无需联网。</div>' +
            controls_html(chans, sources, rows, date) +
            '<section class="sec"><div class="sec-head"><h2>全部资讯</h2>'
            '<span class="sub">共 %d 条 · 点上方按钮筛选 · %s</span></div></section>' % (len(rows), e(date)) +
            "".join(article_html(r, i, chans, sources, date) for i, r in enumerate(rows)) +
            '<div class="s-foot">数据来自公开 RSS 订阅源 · 抓取快照 %s<br>'
            '正文版权归原作者，仅作个人离线阅读，完整版请阅读原文。</div>' % e(date))


def inject_into_interactive(rows, chans, sources, date) -> None:
    """把兜底 DOM/CSS 幂等注入最开始的交互版，并设为默认深色。
    JS 正常运行时 render() 覆盖 #main，交互功能不受影响；
    脚本被剥离时，兜底内容与全部控件原样可点。"""
    s = SRC_HTML.read_text(encoding="utf-8")
    s = re.sub(r'<html([^>]*)data-theme="[^"]*"', r'<html\1data-theme="dark"', s, count=1)
    s = s.replace('theme:LS("zy_theme","light")', 'theme:LS("zy_theme","dark")')
    if "<noscript>" not in s:
        s = s.replace("</head>", NOSCRIPT + "\n</head>", 1)

    css_block = CSS_START + "\n" + CARDS_CSS + "\n" + state_css(chans, sources) + "\n" + CSS_END
    if CSS_START in s:
        s = re.sub(re.escape(CSS_START) + r".*?" + re.escape(CSS_END),
                   lambda m: css_block, s, count=1, flags=re.S)
    else:
        s = s.replace("</style>", css_block + "\n</style>", 1)

    frag = FB_START + "\n" + fallback_fragment(rows, chans, sources, date) + "\n" + FB_END
    if FB_START in s:
        s = re.sub(re.escape(FB_START) + r".*?" + re.escape(FB_END),
                   lambda m: frag, s, count=1, flags=re.S)
    else:
        s = s.replace('<main id="main"></main>',
                      '<main id="main">\n' + frag + "\n</main>", 1)

    SRC_HTML.write_text(s, encoding="utf-8")
    print("zaker-news.html 已注入预生成控件与兜底（%d 条）并设为默认深色 / %d KB" %
          (len(rows), len(s.encode()) // 1024))


def main() -> None:
    rows = read_rows()
    feeds = json.loads((ROOT / "feeds.json").read_text(encoding="utf-8"))["feeds"]
    enabled = sum(1 for f in feeds if f.get("enabled"))
    chans, sources = channels_of(rows), sources_of(rows)
    date = datetime.date.today().isoformat()
    full = sum(1 for r in rows if (r.get("content") or "").strip())

    doc = STATIC_DOC.substitute(
        BASE=BASE_CSS, CARDS=CARDS_CSS, STATE=state_css(chans, sources),
        DATE=e(date), CONTROLS=controls_html(chans, sources, rows, date),
        N=len(rows),
        ARTICLES="".join(article_html(r, i, chans, sources, date) for i, r in enumerate(rows)),
        FEEDS=enabled)
    OUT.write_text(doc, encoding="utf-8")
    print("index.html 已生成：%d 条 / %d 篇全文 / %d 频道 / %d 来源 / %d KB / 零脚本 / 默认深色" %
          (len(rows), full, len(chans), len(sources), len(doc.encode()) // 1024))

    inject_into_interactive(rows, chans, sources, date)


if __name__ == "__main__":
    main()
