#!/usr/bin/env python3
"""profile.json から、サイトの内容に関わる部分をすべて生成する。

    python3 tools/build.py          # 生成して書き込む
    python3 tools/build.py --check  # 生成結果とファイルが一致するか確認（不一致なら exit 1）

生成するもの:
  - index.html の <!-- gen:NAME --> 〜 <!-- /gen:NAME --> で囲まれた区間
  - index.md   … テキスト版プロフィール（index.html の #profile-md にも同じ内容を埋め込む）
  - llms.txt   … llms.txt v2 形式（https://llmstxt.org/）

標準ライブラリのみ。詳細は AGENTS.md。
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "profile.json"
INDEX_HTML = ROOT / "index.html"
INDEX_MD = ROOT / "index.md"
LLMS_TXT = ROOT / "llms.txt"

# 埋め込みブロックを画面に出さないためのスタイル。
# display:none / hidden / aria-hidden / inert は使わない（抽出器やアクセシビリティツリーから消えるため）。
HIDE_STYLE = ("position:absolute;width:1px;height:1px;margin:-1px;padding:0;border:0;"
              "overflow:hidden;clip-path:inset(50%);white-space:pre")


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def attr(s: str) -> str:
    return html.escape(s, quote=True)


def item_text(it) -> str:
    return it if isinstance(it, str) else it["text"]


# ---------------------------------------------------------------- HTML 区間

def current_grade(p: dict, today: dt.date) -> str:
    """JS（assets/index-*.js）と同じ規則で、静的HTMLに入れる学年の初期値を決める。"""
    for g in p["grades"]:
        if today.isoformat() <= g["until"]:
            return g["label"]
    return ""


def gen_head(p: dict) -> str:
    tag = "".join(p["tagline"])
    links = " / ".join(f'{l["key"]}: {l["url"]}' for l in p["links"])
    x = next((l for l in p["links"] if l["key"] == "X"), None)
    out = [
        f'<meta name="description" content="{attr(p["name"])} — {attr(tag)}。{attr(links)}">',
        *[f'<link rel="me" href="{attr(l["url"])}">' for l in p["links"]],
        f'<meta property="og:title" content="{attr(p["name"])}">',
        f'<meta property="og:description" content="{attr(tag)}。">',
        '<meta property="og:type" content="profile">',
        '<meta name="twitter:card" content="summary">',
    ]
    if x:
        out.append(f'<meta name="twitter:creator" content="{attr(x["handle"])}">')
    return "\n".join(out)


def gen_intro(p: dict) -> str:
    ps = "".join(f'<p class="rise" style="--i:{i}">{esc(t)}</p>' for i, t in enumerate(p["tagline"]))
    return f'<div class="intro" lang="ja">{ps}</div>'


def gen_who(p: dict, today: dt.date) -> str:
    grade = current_grade(p, today)
    sep_hidden = "" if grade else " hidden"
    role = (f'<p class="role mono"><span>{esc(p["role"]["en"])}</span><i class="sep"></i>'
            f'<span>{esc(p["born"]["label"])}</span><i class="sep" data-grade-sep{sep_hidden}></i>'
            f'<span data-grade>{esc(grade)}</span></p>')
    chars = "".join(f'<span class="ch" aria-hidden="true" style="--i:{i}">{esc(c)}</span>'
                    for i, c in enumerate(p["name"]))
    name = f'<h1 class="name" id="name"><span class="sr">{esc(p["name"])}</span>{chars}</h1>'
    lis = "".join(
        f'<li><a href="{attr(l["url"])}" target="_blank" rel="noopener me"><span class="k">{esc(l["key"])}</span>'
        f'<span class="v">{esc(l["handle"])}</span><span class="arr" aria-hidden="true">↗</span></a></li>'
        for l in p["links"])
    return "\n".join([role, name, f'<ul class="links mono">{lis}</ul>'])


def gen_log(p: dict) -> str:
    lis, i = [], 0
    for e in p["log"]:
        i += 1
        link = ""
        if e.get("link"):
            link = (f'<a class="mono" href="{attr(e["link"]["url"])}" target="_blank" rel="noopener me">'
                    f'{esc(e["link"]["label"])}<span class="arr" aria-hidden="true">↗</span></a>')
        lis.append(f'<li class="rise" style="--i:{i}"><span class="year mono">\'{e["year"] % 100:02d}</span>'
                   f'<div><h3>{esc(e["title"])}</h3><p>{esc(e["desc"])}</p>{link}</div></li>')
    for _ in range(p.get("log_blank_rows", 0)):
        i += 1
        lis.append(f'<li class="blank rise" style="--i:{i}" aria-hidden="true">'
                   f'<span class="year"><i class="sep"></i></span><div></div></li>')
    return f'<ol class="log">{"".join(lis)}</ol>'


def gen_about(p: dict) -> str:
    # 実績リスト（空き枠を含む）の続きから --i を振る
    i = len(p["log"]) + p.get("log_blank_rows", 0)
    divs = []
    for g in p["about"]:
        i += 1
        spans = "".join(f"<span>{esc(item_text(it))}</span>" for it in g["items"])
        divs.append(f'<div class="rise" style="--i:{i}"><dt>{esc(g["label"])}</dt><dd>{spans}</dd></div>')
    return f'<dl class="about" lang="ja">{"".join(divs)}</dl>'


def gen_foot_links(p: dict) -> str:
    a = "".join(f'<a href="{attr(l["url"])}" target="_blank" rel="noopener me">{esc(l["key"])}</a>'
                for l in p["links"])
    return f'<span class="foot-links">{a}</span>'


def gen_jsonld(p: dict) -> str:
    knows = [item_text(it) for g in p["about"] if g.get("knows_about") for it in g["items"]]
    person = {
        "@type": "Person",
        "name": p["name"],
        "alternateName": next((l["handle"] for l in p["links"] if l["key"] == "X"), p["name"]),
        "jobTitle": p["role"]["en"],
        "description": "".join(p["tagline"]) + "。",
        "url": p["site_url"],
        "image": f'https://github.com/{p["name"]}.png',
        "sameAs": [l["url"] for l in p["links"]],
        "knowsAbout": knows,
        "award": [e["award"] for e in p["log"] if e.get("award")],
    }
    ld = {"@context": "https://schema.org", "@type": "ProfilePage", "url": p["site_url"], "mainEntity": person}
    body = json.dumps(ld, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{body}</script>'


def gen_profile_md_block(md: str) -> str:
    return "\n".join([
        "<!-- テキスト版プロフィール（AI・スクレイパー向け）。tools/build.py が index.md と同じ内容を埋め込む。",
        "     画面には出さない（1pxクリップ）が、inert / aria-hidden / display:none は使わない。",
        "     Readability 系抽出器やアクセシビリティツリー型エージェント（Muse 等）に届かなくなるため。 -->",
        f'<section id="profile-md" lang="ja" aria-label="テキスト版プロフィール（Markdown）" style="{HIDE_STYLE}">'
        f"<pre>{esc(md)}</pre></section>",
    ])


REGION_RE = re.compile(r"^([ \t]*)<!-- gen:([\w-]+) -->\n(.*?)^\1<!-- /gen:\2 -->$", re.M | re.S)


def fill_regions(src: str, blocks: dict[str, str]) -> str:
    seen = set()

    def repl(m: re.Match) -> str:
        indent, name = m.group(1), m.group(2)
        if name not in blocks:
            raise SystemExit(f"index.html: 未知の生成区間 gen:{name}")
        seen.add(name)
        # <pre> の中身は字下げしない（Markdown の行頭空白がコードブロック扱いになるため）
        out_lines, in_pre = [], False
        for line in blocks[name].split("\n"):
            out_lines.append(line if (in_pre or not line) else indent + line)
            if "<pre>" in line:
                in_pre = True
            if "</pre>" in line:
                in_pre = False
        body = "\n".join(out_lines)
        return f"{indent}<!-- gen:{name} -->\n{body}\n{indent}<!-- /gen:{name} -->"

    out = REGION_RE.sub(repl, src)
    missing = set(blocks) - seen
    if missing:
        raise SystemExit(f"index.html: 生成区間が見つからない: {', '.join(sorted(missing))}")
    return out


# ------------------------------------------------- 表示テキストの抽出（原文そのまま）

class VisibleText(HTMLParser):
    """人間に見えるテキストを文書順に行単位で取り出す。

    除外: head / script / style / aside(深度計) / aria-hidden="true" / #profile-md
    li と「dl 直下の div」は 1 行にまとめる。dt の後ろに「:」、dd の項目は「 / 」で区切る。
    外部リンク（http…）はリンク文字列の後ろに URL を添える。
    """
    BLOCK = {"p", "h1", "h2", "h3", "h4", "li", "div", "dt", "dd", "footer", "section",
             "main", "ul", "ol", "dl", "header", "nav", "article"}
    SKIP = {"head", "script", "style", "aside", "noscript", "template"}
    VOID = {"img", "br", "hr", "meta", "link", "input", "source", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool, bool, str | None]] = []  # (tag, skip, join, href)
        self.lines: list[str] = []
        self.cur: list[str] = []
        self.sep = " "

    def _skipping(self) -> bool:
        return any(s for _, s, _, _ in self.stack)

    def _joining(self) -> bool:
        return any(j for _, _, j, _ in self.stack)

    def _flush(self) -> None:
        line = " ".join(t for t in self.cur if t).strip()
        line = line.replace(" : ", ": ")
        if line:
            self.lines.append(line)
        self.cur = []

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            return
        a = dict(attrs)
        skip = (tag in self.SKIP or a.get("aria-hidden") == "true" or a.get("id") == "profile-md")
        parent = self.stack[-1][0] if self.stack else None
        join = tag == "li" or (tag == "div" and parent == "dl")
        if tag in self.BLOCK and not self._joining() and not self._skipping():
            self._flush()
        if tag == "dd" and not self._skipping():
            self.cur.append(":")
        self.stack.append((tag, skip, join, a.get("href")))

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        while self.stack:
            t, skip, _, href = self.stack.pop()
            if t == tag:
                break
        else:
            return
        if self._skipping() or skip:
            return
        if tag == "a" and href and href.startswith("http"):
            self.cur.append(href)
        if tag in self.BLOCK and not self._joining():
            self._flush()

    def handle_data(self, data):
        if self._skipping():
            return
        t = " ".join(data.split())
        if not t:
            return
        in_dd = any(tg == "dd" for tg, _, _, _ in self.stack)
        if in_dd and self.cur and self.cur[-1] not in (":",):
            self.cur.append("/")
        self.cur.append(t)

    def text(self) -> str:
        self._flush()
        return "\n".join(self.lines)


def visible_text(page: str) -> str:
    v = VisibleText()
    v.feed(page)
    return v.text()


# ---------------------------------------------------------------- Markdown

def gen_index_md(p: dict, verbatim: str) -> str:
    site = p["site_url"]
    links_inline = " / ".join(f'{l["key"]}: {l["url"]}' for l in p["links"])
    grades = " / ".join(f'{g["fiscal_year"]}年度 {g["label"]}（{g["ja"]}）' for g in p["grades"])
    L = [f'# {p["name"]}', "",
         f'> {"".join(p["tagline"])}（{p["role"]["en"]}）。{links_inline}', "",
         f'- 名前（ハンドル）: {p["name"]}',
         f'- 肩書き: {p["role"]["en"]}（{p["role"]["ja"]}）',
         f'- 生年: {p["born"]["year"]}年（{p["born"]["label"]}）',
         f'- 学年: {grades}（予定を含む）',
         f'- Webサイト: {site}', "",
         "## リンク", ""]
    L += [f'- {l["label"]}: [{l["handle"]}]({l["url"]}) — {l["url"]}' for l in p["links"]]
    L += ["", "## 実績", ""]
    for e in p["log"]:
        s = f'- {e["year"]}: {e.get("detail") or (e["title"] + " " + e["desc"])}'
        src = e.get("source") or (e.get("link") or {}).get("url")
        if src:
            s += f' — {e["source_label"]}: {src}' if e.get("source_label") else f" — {src}"
        L.append(s)
    for g in p["about"]:
        L += ["", f'## {g["label"]}', ""]
        for it in g["items"]:
            if isinstance(it, str):
                it = {"text": it}
            s = f'- {it["text"]}'
            if it.get("note"):
                s += f'（{it["note"]}）'
            if it.get("url"):
                s += f' — {it["url"]}'
            L.append(s)
    L += ["", "## サイト上の表示テキスト（原文そのまま）", "", "```text", verbatim, "```", "",
          "## このページについて", "",
          f"- {site} の内容をそのままテキストにしたものです。",
          f"- Markdown版: {site}index.md",
          f"- llms.txt: {site}llms.txt", ""]
    return "\n".join(L)


def gen_llms_txt(p: dict) -> str:
    site = p["site_url"]
    links_inline = " / ".join(f'{l["key"]}: {l["url"]}' for l in p["links"])
    cur = p["grades"][0]
    about = {g["label"]: [item_text(it) for it in g["items"]] for g in p["about"]}
    sentence = (f'{p["name"]} は{p["born"]["year"]}年生まれの{p["role"]["ja"]}で、'
                f'{cur["fiscal_year"]}年度は{cur["ja"]}（{cur["label"]}）です。')
    parts = []
    for g in p["about"]:
        parts.append(f'{g["label"]}: {" / ".join(about[g["label"]])}')
    L = [f'# {p["name"]}', "",
         f'> {"".join(p["tagline"])}（{p["role"]["en"]}）{p["name"]} の個人サイト（{site}）。{links_inline}', "",
         sentence + "。".join(parts) + "。", "",
         "実績:", ""]
    L += [f'- {e["year"]}: {e.get("detail") or (e["title"] + " " + e["desc"])}' for e in p["log"]]
    L += ["", "## プロフィール", "",
          f"- [プロフィール全文（Markdown）]({site}index.md): サイトの内容をMarkdownにしたもの"]
    L += [f'- [{l["label"]} {l["handle"]}]({l["url"]}): {l["label"]} のアカウント' for l in p["links"]]
    if p.get("references"):
        L += ["", "## Optional", ""]
        L += [f'- [{r["label"]}]({r["url"]})' + (f': {r["note"]}' if r.get("note") else "")
              for r in p["references"]]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- 整合性チェック

def check_js_grades(p: dict) -> list[str]:
    """学年の切り替え表は JS バンドルにも埋め込まれているので、食い違いを検出する。"""
    errs = []
    for js in sorted((ROOT / "assets").glob("index-*.js")):
        pairs = re.findall(r"until:`([^`]+)`,label:`([^`]+)`", js.read_text(encoding="utf-8"))
        if pairs and pairs != [(g["until"], g["label"]) for g in p["grades"]]:
            errs.append(f"{js.name} の学年表 {pairs} が profile.json の grades と一致しない")
    return errs


def build(today: dt.date | None = None) -> dict[Path, str]:
    p = json.loads(PROFILE.read_text(encoding="utf-8"))
    today = today or dt.datetime.now(ZoneInfo("Asia/Tokyo")).date()
    src = INDEX_HTML.read_text(encoding="utf-8")
    blocks = {
        "head": gen_head(p),
        "intro": gen_intro(p),
        "who": gen_who(p, today),
        "log": gen_log(p),
        "about": gen_about(p),
        "foot-links": gen_foot_links(p),
        "jsonld": gen_jsonld(p),
        "profile-md": gen_profile_md_block(""),
    }
    # 1 回目: 表示部分を確定させて、そこから原文テキストを抽出する
    page = fill_regions(src, blocks)
    verbatim = visible_text(page)
    md = gen_index_md(p, verbatim)
    # 2 回目: Markdown を埋め込む
    blocks["profile-md"] = gen_profile_md_block(md)
    page = fill_regions(src, blocks)

    # 人間に見える文字列がすべて Markdown に含まれていることを保証する
    missing = [ln for ln in verbatim.split("\n") if ln not in md]
    errs = check_js_grades(p) + [f"Markdown に無い表示テキスト: {m}" for m in missing]
    if errs:
        raise SystemExit("\n".join(errs))
    return {INDEX_HTML: page, INDEX_MD: md, LLMS_TXT: gen_llms_txt(p)}


def main() -> None:
    check = "--check" in sys.argv[1:]
    outputs = build()
    stale = [f for f, s in outputs.items() if not f.exists() or f.read_text(encoding="utf-8") != s]
    if check:
        if stale:
            print("生成物が profile.json と一致しません。python3 tools/build.py を実行してください:",
                  ", ".join(f.name for f in stale))
            sys.exit(1)
        print("OK: 生成物は最新です")
        return
    for f in stale:
        f.write_text(outputs[f], encoding="utf-8")
    print("更新:", ", ".join(f.name for f in stale) if stale else "なし（すでに最新）")


if __name__ == "__main__":
    main()
