#!/usr/bin/env python3
"""判断シート（HTML）を作る。採用・不採用をボタンで選び、結果の文字をチャットに貼ってもらう形式。

使い方:
    python3 harness/tools/make_sheet.py <sheet.json> <out.html>

sheet.json の形は harness/templates/判断シート_例.json を見る。
  title        ページの題（例：第1話 r1 判断シート）
  result_head  結果の1行目（例：【第1話 r1 判断結果】）
  store_key    ブラウザに選択を残す時の鍵（話・ラウンドごとに変える）
  lead         冒頭の説明文
  sections     [{title, items:[{id, q, ctx, opts:[{k, t, d?, s?, rec?}]}]}]
                 k=選択肢の鍵、t=見出し、d=説明、s=試し書き（引用）、rec=推奨

外部の通信なし。標準ライブラリのみ。
"""
import json, sys, html, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "harness" / "templates" / "判断シート.html"


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    for k in ("title", "result_head", "store_key", "sections"):
        if k not in data:
            sys.exit(f"sheet.json に {k} がありません")
    t = TEMPLATE.read_text(encoding="utf-8")
    sections = json.dumps(data["sections"], ensure_ascii=False).replace("</", "<\\/")
    t = t.replace("__SECTIONS_JSON__", sections)
    t = t.replace("__TITLE__", html.escape(data["title"]))
    t = t.replace("__LEAD__", html.escape(data.get("lead", "選択肢を押すと選べます。下のバーで結果をコピーして、チャットへ貼ってください。")))
    t = t.replace("__STORE_KEY__", data["store_key"].replace("'", ""))
    t = t.replace("__RESULT_HEAD__", data["result_head"].replace("\\", "\\\\").replace("'", "\\'"))
    pathlib.Path(sys.argv[2]).write_text(t, encoding="utf-8")
    n = sum(len(s["items"]) for s in data["sections"])
    print(f"{sys.argv[2]}  項目 {n}")


if __name__ == "__main__":
    main()
