#!/usr/bin/env python3
"""index.html を 8 種類の抽出器にかけ、profile.json の主要情報が残るかを確かめる。

    python3 tools/verify/extractors.py [HTMLファイル]   # 既定: index.html
全部残れば exit 0、欠けがあれば表を出して exit 1。
"""
import json, subprocess, sys, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import html2text, markdownify, trafilatura
from bs4 import BeautifulSoup
from readability import Document

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "index.html"
p = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
h = target.read_text(encoding="utf-8")

must = {f"# {p['name']}": "名前見出し"}
must.update({l["url"]: l["key"] for l in p["links"]})
must.update({e["title"]: f"実績{e['year']}" for e in p["log"]})

out = json.loads(subprocess.run(["node", str(HERE / "extract.mjs"), str(target)],
                                check=True, capture_output=True, text=True, cwd=HERE).stdout)
out["trafilatura"] = trafilatura.extract(h) or ""
out["trafilatura_md"] = trafilatura.extract(h, include_links=True, output_format="markdown") or ""
out["readability_lxml"] = html2text.html2text(Document(h).summary())
out["html2text"] = html2text.html2text(h)
out["markdownify"] = markdownify.markdownify(h)
out["bs4_text"] = BeautifulSoup(h, "lxml").get_text(" ")

fail = 0
for name, text in out.items():
    miss = [label for s, label in must.items() if s not in text]
    fail += bool(miss)
    print(f"{'OK  ' if not miss else 'NG  '}{name:18s}" + (f" 欠け: {', '.join(miss)}" if miss else ""))
sys.exit(1 if fail else 0)
