#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知阅 · 离线数据包构建脚本

用法：
    python3 build.py --offline    只把 articles.csv 重新内联进 zaker-news.html（不联网，秒级）
    python3 build.py              联网重新抓取 feeds.json 里的订阅源，更新 articles.csv 并重建 HTML
    python3 build.py --fetch-only 只抓取生成 articles.csv，不改 HTML

工作流程（对应「构建时抓取、运行时零请求」）：
    订阅源 RSS/Atom  ──urllib 并发抓取──▶ 解析条目
                                     ├─ 优先用 content:encoded / description 里的正文
                                     └─ 只有摘要时按 link 抓原文 HTML，抽 article/main 里的段落
                                     ▼
                              articles.csv（14 列，content 用 | 分段，# 开头为小标题）
                                     ▼
                              zaker-news.html 的 INLINE_DATA 区块（重建后预览里直接可读）

只依赖 Python 标准库。抓取失败不会清空已有数据，会保留上一版并打印失败来源。
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime
import html
import io
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent
FEEDS_FILE = ROOT / "feeds.json"
CSV_FILE = ROOT / "articles.csv"
HTML_FILE = ROOT / "zaker-news.html"

HEADERS = ["id", "channels", "title", "summary", "source", "author", "published_at",
           "image", "tag", "views", "likes", "read_minutes", "content", "link"]

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
TIMEOUT = 12
MAX_PER_FEED = 12
MAX_ARTICLE_FETCH = 10

START = "/* ==== INLINE_DATA_START ==== */"
END = "/* ==== INLINE_DATA_END ==== */"

NOISE_CLASS = re.compile(
    r"(comment|sidebar|advert|^ad$|ads|related|share|social|popup|modal|subscribe|"
    r"paywall|breadcrumb|toolbar|recommend|hot|promo|banner|footer|nav|menu)", re.I)
DROP_TAG = re.compile(r"<(script|style|noscript|iframe|svg|form|nav|footer|header|aside)[^>]*>.*?</\1>", re.I | re.S)
TAG = re.compile(r"<[^>]+>")


def log(msg: str) -> None:
    print(msg, flush=True)


def read_csv(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def write_csv(rows: list[dict]) -> None:
    with CSV_FILE.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: str(r.get(k, "") or "") for k in HEADERS})


def clean_text(s: str) -> str:
    s = html.unescape(re.sub(r"\s+", " ", TAG.sub(" ", s or ""))).strip()
    return re.sub(r"\s{2,}", " ", s)


def html_to_paras(raw: str) -> list[str]:
    """把 HTML 正文转成段落列表；# 前缀表示小标题。"""
    if not raw:
        return []
    src = DROP_TAG.sub(" ", raw)
    src = re.sub(r"<br\s*/?>", "\n", src, flags=re.I)
    # h1~h6 转成 # 小标题行，页面会渲染成 h2
    src = re.sub(r"<h([1-6])[^>]*>(.*?)</h\1>",
                 lambda m: "\n# " + clean_text(m.group(2)) + "\n", src, flags=re.I | re.S)
    src = re.sub(r"</(p|div|li|blockquote|section)>", "\n", src, flags=re.I)
    src = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", src)  # markdown 残留图片
    parts = []
    for chunk in src.split("\n"):
        if NOISE_CLASS.search(chunk) and "<" in chunk:
            continue
        t = clean_text(chunk)
        t = t.replace("**", "").replace("|", "丨").strip()
        if t.startswith("# "):
            if len(t) > 2:
                parts.append(t)
            continue
        if len(t) < 12:
            continue
        parts.append(t)
    # 合并相邻重复，限制长度
    out: list[str] = []
    for p in parts:
        if out and out[-1] == p:
            continue
        out.append(p[:1400])
        if len(out) >= 40:
            break
    return out


def extract_article_html(raw: str) -> list[str]:
    """轻量正文提取：优先 article/main/常见正文容器，否则退回全页 p 标签。"""
    if not raw:
        return []
    body = DROP_TAG.sub(" ", raw)
    m = re.search(
        r"<(article|main)\b[^>]*>(.*?)</\1>|<(?:div|section)\b[^>]*(?:article-content|post-content|"
        r"entry-content|rich_media_content|article-body|markdown-body|content-article)[^>]*>(.*?)</(?:div|section)>",
        body, re.I | re.S)
    scope = (m.group(2) or m.group(3)) if m else body
    paras: list[str] = []
    for hm in re.finditer(r"<h([1-6])[^>]*>(.*?)</h\1>", scope, re.I | re.S):
        t = clean_text(hm.group(2))
        if len(t) >= 4:
            paras.append("# " + t)
    blocks = re.findall(r"<p\b[^>]*>(.*?)</p>|<li\b[^>]*>(.*?)</li>|<blockquote[^>]*>(.*?)</blockquote>",
                        scope, re.I | re.S)
    for a, b, c in blocks:
        t = clean_text(a or b or c).replace("**", "").replace("|", "丨")
        if len(t) >= 12:
            paras.append(t[:1400])
        if len(paras) >= 40:
            break
    return paras


def get(url: str, timeout: int = TIMEOUT) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(2_000_000)
    for enc in ("utf-8", "gb18030", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "ignore")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def child_text(node, *names: str) -> str:
    for ch in node:
        if local_name(ch.tag) in names:
            return "".join(ch.itertext()).strip()
    return ""


def child_raw(node, *names: str) -> str:
    """返回元素内部的原始 HTML（CDATA 里的标签需要保留）。"""
    for ch in node:
        if local_name(ch.tag) in names:
            if len(ch):
                return "".join(ET.tostring(x, encoding="unicode") for x in ch)
            return ch.text or ""
    return ""


def parse_feed(text: str) -> list[dict]:
    text = re.sub(r"^\s*<\?xml[^>]*\?>", "", text).strip()
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        # 部分站点输出未声明的命名空间前缀（如 dc:creator），去掉前缀再试一次
        root = ET.fromstring(re.sub(r"(</?)[A-Za-z_][\w.-]*:", r"\1", text))
    items = [n for n in root.iter() if local_name(n.tag) in ("item", "entry")]
    out = []
    for it in items[:MAX_PER_FEED * 2]:
        title = clean_text(child_text(it, "title"))
        if not title:
            continue
        link = child_text(it, "link").strip()
        if not link:
            for ch in it:
                if local_name(ch.tag) == "link" and ch.get("href"):
                    link = ch.get("href")
                    break
        guid = child_text(it, "guid", "id").strip()
        desc_raw = child_raw(it, "description", "summary", "encoded", "content")
        full_raw = child_raw(it, "encoded", "content") or desc_raw
        date = child_text(it, "pubdate", "published", "updated", "date")
        author = clean_text(child_text(it, "author", "creator"))
        img = ""
        for ch in it:
            if local_name(ch.tag) == "enclosure" and ch.get("url"):
                img = ch.get("url")
                break
        if not img:
            im = re.search(r"<img[^>]+src=[\"']([^\"']+)[\"']", full_raw, re.I)
            if im:
                img = html.unescape(im.group(1))
        if not re.match(r"^https?://", link):
            link = ""
        out.append({
            "title": title, "link": link, "guid": guid,
            "full_raw": full_raw, "desc_raw": desc_raw,
            "date": date, "author": author, "image": img,
        })
    return out


def normalize_date(s: str) -> str:
    if not s:
        return ""
    fmts = ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
            "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"]
    for f in fmts:
        try:
            d = datetime.datetime.strptime(s.strip(), f)
            return d.isoformat()
        except ValueError:
            pass
    m = re.search(r"\d{4}-\d{2}-\d{2}[T ][\d:]+", s)
    return m.group(0) if m else ""


def norm_title(t: str) -> str:
    return re.sub(r"[\s\W_]+", "", (t or "").lower(), flags=re.UNICODE)


def stable_id(title: str, link: str, guid: str, source: str) -> str:
    base = link or guid or title
    slug = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "-", base).strip("-")[-40:]
    return (re.sub(r"\s+", "-", source) + "-" + (slug or str(abs(hash(title)) % 99999)))[:80]


def fetch_one(feed: dict) -> tuple[str, list[dict], str]:
    name = feed["name"]
    try:
        xml = get(feed["url"])
        items = parse_feed(xml)
        if not items:
            return name, [], "无条目"
        return name, items[:MAX_PER_FEED], ""
    except Exception as e:
        return name, [], "%s: %s" % (type(e).__name__, str(e)[:90])


def fetch_article_paras(url: str) -> list[str]:
    try:
        return extract_article_html(get(url, TIMEOUT))
    except Exception:
        return []


def merge(prev: list[dict], fresh: list[dict]) -> list[dict]:
    """按 id / 规范化标题 / link 合并；抓取失败的条目沿用上一版正文。"""
    by_id = {r["id"]: dict(r) for r in prev}
    by_title = {norm_title(r["title"]): r["id"] for r in prev}
    by_link = {r["link"]: r["id"] for r in prev if r.get("link")}
    for r in fresh:
        rid = (r.get("id") in by_id and r["id"]) or by_title.get(norm_title(r["title"])) or \
              by_link.get(r.get("link", "")) or r["id"]
        old = by_id.get(rid, {})
        merged = dict(old)
        merged.update({k: v for k, v in r.items() if v not in ("", None)})
        # 新抓不到正文时保留旧正文
        if not merged.get("content") and old.get("content"):
            merged["content"] = old["content"]
            merged["tag"] = old.get("tag", "快照")
        by_id[rid] = merged
        by_title[norm_title(r["title"])] = rid
        if r.get("link"):
            by_link[r["link"]] = rid
    return list(by_id.values())


def build_rows() -> tuple[list[dict], int]:
    feeds = json.loads(FEEDS_FILE.read_text(encoding="utf-8"))["feeds"]
    feeds = [f for f in feeds if f.get("enabled") and f.get("type") == "rss"]
    log("订阅源：%d 个，开始并发抓取…" % len(feeds))
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(feeds))) as ex:
        futs = {ex.submit(fetch_one, f): f for f in feeds}
        for fut in concurrent.futures.as_completed(futs):
            f = futs[fut]
            try:
                name, items, err = fut.result()
            except Exception as e:
                name, items, err = f["name"], [], str(e)
            results[f["name"]] = items
            log("  %-14s %2d 条 %s" % (f["name"], len(items), ("· " + err) if err else ""))

    # 收集需要抓原文的条目
    jobs = []
    for f in feeds:
        for it in results.get(f["name"], []):
            paras = html_to_paras(it["full_raw"])
            if len("".join(paras)) < 220 and it["link"]:
                jobs.append((f, it, paras))
    jobs = jobs[:MAX_ARTICLE_FETCH]
    if jobs:
        log("摘要过短，尝试抓取原文正文：%d 篇…" % len(jobs))
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            extra = list(ex.map(lambda j: fetch_article_paras(j[1]["link"]), jobs))
        for (f, it, paras), got in zip(jobs, extra):
            if len("".join(got)) > len("".join(paras)):
                it["_paras"] = got

    rows: list[dict] = []
    for f in feeds:
        for it in results.get(f["name"], []):
            paras = it.get("_paras") or html_to_paras(it["full_raw"]) or html_to_paras(it["desc_raw"])
            content = "|".join(paras)
            summary = clean_text(html_to_paras(it["desc_raw"])[0] if it["desc_raw"] else "")
            if content:
                first = next((p for p in paras if not p.startswith("# ")), "")
                summary = (first[:68] + "…") if len(first) > 68 else first
            rows.append({
                "id": stable_id(it["title"], it["link"], it["guid"], f["name"]),
                "channels": f.get("channels", "推荐"),
                "title": it["title"],
                "summary": summary or (f["name"] + " · 点击查看原文"),
                "source": f["name"],
                "author": it["author"],
                "published_at": normalize_date(it["date"]),
                "image": it["image"],
                "tag": "快照·全文" if content else "快照",
                "views": "0", "likes": "0", "read_minutes": "0",
                "content": content,
                "link": it["link"],
            })
    prev = read_csv(CSV_FILE)
    merged = merge(prev, rows)
    for r in merged:
        for k in HEADERS:
            r.setdefault(k, "")
    return merged, sum(1 for r in merged if r.get("content"))


def js_template(csv_text: str) -> str:
    return csv_text.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")


def rebuild_html(meta: dict) -> None:
    text = HTML_FILE.read_text(encoding="utf-8")
    i, j = text.find(START), text.find(END)
    if i < 0 or j < 0 or j <= i:
        raise RuntimeError("找不到 INLINE_DATA 标记，无法重建 HTML")
    body = ("/* ==== INLINE_DATA_START ==== */\n"
            "const PACK_META = " + json.dumps(meta, ensure_ascii=False) + ";\n"
            "const EMBEDDED_CSV = `" + js_template(CSV_FILE.read_text(encoding="utf-8-sig")) + "`;\n")
    HTML_FILE.write_text(text[:i] + body + text[j:], encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="知阅离线数据包构建")
    ap.add_argument("--offline", action="store_true", help="只重建内联数据，不联网")
    ap.add_argument("--fetch-only", action="store_true", help="只抓取并更新 CSV")
    args = ap.parse_args()

    if not CSV_FILE.exists():
        log("缺少 articles.csv")
        return 1
    if args.offline:
        rows = read_csv(CSV_FILE)
        meta = {
            "generated_at": datetime.date.today().isoformat(),
            "articles": len(rows),
            "fulltext": sum(1 for r in rows if r.get("content")),
            "note": "真实订阅源抓取的离线数据包；含按原文段落整理的正文快照，其余为真实摘要。内容版权归原作者，完整版请看原文。"
        }
    else:
        rows, nfull = build_rows()
        write_csv(rows)
        meta = {
            "generated_at": datetime.date.today().isoformat(),
            "articles": len(rows),
            "fulltext": nfull,
            "note": "真实订阅源抓取的离线数据包；含按原文段落整理的正文快照，其余为真实摘要。内容版权归原作者，完整版请看原文。"
        }
        log("articles.csv 已更新：%d 条，其中 %d 篇含正文" % (len(rows), nfull))

    if not args.fetch_only:
        rebuild_html(meta)
        log("zaker-news.html 内联数据已重建（%d 条 / %d 篇全文）" % (meta["articles"], meta["fulltext"]))
        static = ROOT / "build_static.py"
        if static.exists():
            import subprocess
            subprocess.run([sys.executable, str(static)], check=True, cwd=str(ROOT))
    log("完成。预览里打开 index.html（零脚本静态版）即可离线阅读；"
        "真实浏览器打开 zaker-news.html 可用完整交互功能。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
