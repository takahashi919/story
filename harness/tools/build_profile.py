#!/usr/bin/env python3
"""参考作家の本文から文体の数値プロファイルを作る（標準ライブラリのみ）。

使い方:
    python3 harness/tools/build_profile.py \\
        --magonote <理不尽な孫の手の参考文章.txt> \\
        --mishima <三嶋与夢①.txt> <三嶋与夢②.txt> \\
        [--old archive/2026-03_notebooklm/drafts/0*.txt]

出力は harness/文体/参照プロファイル.json（数値とファイルのハッシュだけ）。
参考文章は他の作家の著作物なのでリポジトリに入れない。手元の zip から取り出して指定する。

- 指標は measure.py と同じ関数で測る。
- 作家ごとに全文の値と、4,500字（1話ぶん）ずつに切った塊の p10/p50/p90 と標準偏差を持つ。
- 両作家の差が揺れ幅（標準偏差の二乗平均）の1倍以上ある指標だけを配合推定に使う。
- 「目安」は harness/文体/本作の文体.md の数値。変えるときは両方を直す。
"""
import argparse
import hashlib
import json
import statistics
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure import PROFILE, blend, metrics, paragraphs  # noqa: E402

CHUNK = 4500
TARGETS = {  # harness/文体/本作の文体.md「数値の確認」と同じ
    "字数": [3500, 5000],
    "会話比率%": [25, 35],
    "……/万字": [20, 40],
    "――/万字": [15, 25],
    "（）/万字": [0, 6],  # 一人称では（）モノローグは基本的に要らないので下限なし
}
SKIP = {"字数", "段落数"}  # 長さで決まる値は作家の特徴にしない


def paras_of(files: list[str]) -> list[str]:
    out = []
    for f in files:
        out += [p for sc in paragraphs(Path(f).read_text(encoding="utf-8")) for p in sc]
    return out


def chunks(paras: list[str]) -> list[list[str]]:
    res, cur, n = [], [], 0
    for p in paras:
        cur.append(p)
        n += len(p)
        if n >= CHUNK:
            res.append(cur)
            cur, n = [], 0
    return res


def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(int(q * len(xs)), len(xs) - 1)]


def summarize(files: list[str]) -> tuple[dict, list[dict], dict]:
    ps = paras_of(files)
    whole = metrics(ps)
    cs = [metrics(c) for c in chunks(ps)]
    stats = {}
    for k, v in whole.items():
        if k in SKIP:
            continue
        xs = [c[k] for c in cs]
        stats[k] = {"value": v, "p10": round(pct(xs, 0.1), 2), "p50": round(pct(xs, 0.5), 2),
                    "p90": round(pct(xs, 0.9), 2), "sd": round(statistics.pstdev(xs), 2)}
    meta = {"字数": whole["字数"], "塊の数": len(cs),
            "sha256": [hashlib.sha256(Path(f).read_bytes()).hexdigest()[:16] for f in files]}
    return stats, cs, meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--magonote", nargs="+", required=True)
    ap.add_argument("--mishima", nargs="+", required=True)
    ap.add_argument("--old", nargs="*", default=[])
    a = ap.parse_args()

    g, g_chunks, g_meta = summarize(a.magonote)
    s, s_chunks, s_meta = summarize(a.mishima)
    prof = {
        "説明": "参考作家の文体の数値（本文は持たない）。作り方と読み方は harness/文体/参照プロファイル.md",
        "作成日": date.today().isoformat(),
        "塊の字数": CHUNK,
        "字数の目安": TARGETS["字数"],
        "出典": {"孫の手": g_meta, "三嶋": s_meta},
        "metrics": {},
    }
    for k in g:
        pooled = ((g[k]["sd"] ** 2 + s[k]["sd"] ** 2) / 2) ** 0.5 or 1.0
        sep = abs(g[k]["value"] - s[k]["value"]) / pooled
        spec = {"孫の手": g[k], "三嶋": s[k], "pooled_sd": round(pooled, 3),
                "作家差": round(sep, 2), "used_for_blend": sep >= 1.0}
        if k in TARGETS:
            spec["target"] = TARGETS[k]
        prof["metrics"][k] = spec

    # 参考作家自身の塊が、配合点からどれだけずれるか ＝ 「似ている」と言える距離の上限
    dists = [blend(c, prof)["距離"] for c in g_chunks + s_chunks]
    prof["distance_p90"] = round(pct(dists, 0.9), 2)
    # 生の配合は作家本人の塊でも両端に届かない。塊の中央値を 0/100 に合わせる較正値を持つ
    w_of = lambda cs: [blend(c, prof)["孫の手"] / 100 for c in cs]
    prof["配合の較正"] = {"孫の手": pct(w_of(g_chunks), 0.5), "三嶋": pct(w_of(s_chunks), 0.5)}
    prof["塊の配合"] = {
        "孫の手の塊": {q: round(pct(w_of(g_chunks), v) * 100) for q, v in (("p10", 0.1), ("p50", 0.5))},
        "三嶋の塊": {q: round(pct(w_of(s_chunks), v) * 100) for q, v in (("p50", 0.5), ("p90", 0.9))},
    }

    if a.old:
        o, _, o_meta = summarize(a.old)
        for k, spec in prof["metrics"].items():
            spec["旧原稿"] = {"value": o[k]["value"]}
        prof["出典"]["旧原稿"] = o_meta | {"files": [Path(f).name for f in a.old]}

    PROFILE.write_text(json.dumps(prof, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {PROFILE}")
    print(f"distance_p90={prof['distance_p90']}  較正={prof['配合の較正']}  塊の配合（較正後）={prof['塊の配合']}")
    for k, spec in prof["metrics"].items():
        mark = "配合に使う" if spec["used_for_blend"] else ""
        print(f"  {k:<10} 孫の手 {spec['孫の手']['value']:>7}  三嶋 {spec['三嶋']['value']:>7}"
              f"  作家差 {spec['作家差']:>5}  {mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
