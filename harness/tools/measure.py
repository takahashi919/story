#!/usr/bin/env python3
"""本文の文字数と文体の数値を測る（標準ライブラリのみ）。

使い方:
    python3 harness/tools/measure.py episodes/第0部/00_泥雨の異端者/本文.md [他のファイル ...]

モデルに文字数を「数えさせる」と外す（3月の MTG3 では全話の字数を実測より少なく報告した）。
字数と記号密度は必ずこのスクリプトの出力を使う。

数え方:
- 字数: HTML コメント・Markdown 見出し行・空白を除いた文字数。
- 会話比率: 「 か 『 で始まる段落の字数 ÷ 字数。
- 記号密度: 1万字あたりの回数。「……」「――」は2文字で1回。
- （）モノローグ: （ で始まる段落の数（「防人（さきもり）」のような読み仮名は数えない）。
- 地の文と会話が同じ段落に混ざっている原稿では、会話比率が実際より高く出る。
- 一文平均: 。！？ と 」』 で区切った文の平均字数（会話の中も含む）。
"""
import re
import sys
from pathlib import Path


def strip(text: str) -> list[str]:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    paras = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s in ("---", "＊＊＊", "◇"):
            continue
        paras.append(s)
    return paras


def measure(path: Path) -> dict:
    paras = strip(path.read_text(encoding="utf-8"))
    body = "".join(re.sub(r"\s", "", p) for p in paras)
    n = len(body)
    if n == 0:
        return {"file": str(path), "字数": 0}
    dialogue = sum(len(re.sub(r"\s", "", p)) for p in paras if p.startswith(("「", "『")))
    per10k = lambda c: round(c * 10000 / n, 1)
    sentences = [s for s in re.split(r"[。！？!?」』]+", body) if s]
    return {
        "file": str(path),
        "字数": n,
        "会話比率%": round(dialogue * 100 / n, 1),
        "一文平均": round(n / max(len(sentences), 1), 1),
        "……/万字": per10k(body.count("……")),
        "――/万字": per10k(body.count("――")),
        "（）/万字": per10k(sum(1 for p in paras if p.startswith("（"))),
        "段落数": len(paras),
    }


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    for a in argv:
        r = measure(Path(a))
        print("  ".join(f"{k}={v}" for k, v in r.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
