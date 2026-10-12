#!/usr/bin/env python3
"""本文の文字数と文体の数値を測り、参考作家の数値と比べる（標準ライブラリのみ）。

使い方:
    python3 harness/tools/measure.py <本文.md> [他のファイル ...]
    python3 harness/tools/measure.py --compare <本文.md>   # 孫の手:三嶋 の配合推定と、外れた指標
    python3 harness/tools/measure.py --scenes <本文.md>    # ＊＊＊ で区切った場面ごとの配合推定
    python3 harness/tools/measure.py --json ...            # 上の結果を JSON で（1ファイル1行）

モデルに文字数を「数えさせる」と外す（3月の MTG3 では全話の字数を実測より少なく報告した）。
字数と記号密度は必ずこのスクリプトの出力を使う。

数え方:
- 字数: HTML コメント・Markdown 見出し行・空白を除いた文字数。
- 会話比率: 「 か 『 で始まる段落の字数 ÷ 字数。
- 記号密度: 1万字あたりの回数。「……」「――」は2文字で1回。
- （）モノローグ: （ で始まる段落の数（「防人（さきもり）」のような読み仮名は数えない）。
- 地の文と会話が同じ段落に混ざっている原稿では、会話比率が実際より高く出る。
- 一文平均: 。！？ と 」』 で区切った文の平均字数（会話の中も含む）。
- 地の文一文平均・短文率: 「『（ で始まらない段落だけで、。！？ で区切る。短文は10字以下。
- 段落平均: 1段落の平均字数。読点/文: 一文あたりの「、」。漢字率: 漢字と「々」の割合。

比較（--compare / --scenes）:
- 参考作家の数値は harness/文体/参照プロファイル.json（build_profile.py が作る。数値だけで本文は持たない）。
- 配合: 両作家で差の大きい指標ごとに「三嶋=0、孫の手=1」の物差しで本文の位置を測り、0〜1 に
  切り詰めて作家差の重みで平均する。作家本人の4,500字の塊の中央値が 0 と 100 になるよう較正済み。
- 距離: その点からのずれ（揺れ幅の何倍か）。参考作家自身の4,500字の塊の 90% はこの値に収まる
  （JSON の distance_p90）。それを超えたら、配合では説明できない ＝ どちらの作家にも似ていない。
- 1,500字未満の場面の配合は揺れが大きいので参考扱い。
"""
import json
import re
import sys
from pathlib import Path

PROFILE = Path(__file__).resolve().parents[1] / "文体" / "参照プロファイル.json"
SCENE_MARKERS = ("---", "＊＊＊", "◇")
SHORT_SCENE = 1500


def paragraphs(text: str) -> list[list[str]]:
    """場面ごとの段落リスト（空白は除去済み）。場面の区切りは ---・＊＊＊・◇。"""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    scenes, cur = [], []
    for line in text.splitlines():
        s = line.strip()
        if s in SCENE_MARKERS:
            if cur:
                scenes.append(cur)
            cur = []
            continue
        if not s or s.startswith("#"):
            continue
        cur.append(re.sub(r"\s", "", s))
    if cur:
        scenes.append(cur)
    return scenes


def metrics(paras: list[str]) -> dict:
    body = "".join(paras)
    n = len(body)
    if n == 0:
        return {"字数": 0}
    per10k = lambda c: round(c * 10000 / n, 1)
    dialogue = sum(len(p) for p in paras if p.startswith(("「", "『")))
    sentences = [s for s in re.split(r"[。！？!?」』]+", body) if s]
    narr = "".join(p for p in paras if not p.startswith(("「", "『", "（")))
    nsent = [s for s in re.split(r"[。！？!?]+", narr) if s]
    kanji = len(re.findall(r"[一-鿿々]", body))
    return {
        "字数": n,
        "会話比率%": round(dialogue * 100 / n, 1),
        "一文平均": round(n / max(len(sentences), 1), 1),
        "地の文一文平均": round(len(narr) / max(len(nsent), 1), 1),
        "短文率%": round(100 * sum(1 for s in nsent if len(s) <= 10) / max(len(nsent), 1), 1),
        "段落平均": round(n / len(paras), 1),
        "読点/文": round(body.count("、") / max(len(sentences), 1), 2),
        "漢字率%": round(100 * kanji / n, 1),
        "……/万字": per10k(body.count("……")),
        "――/万字": per10k(body.count("――")),
        "（）/万字": per10k(sum(1 for p in paras if p.startswith("（"))),
        "！/万字": per10k(len(re.findall(r"[！!]", body))),
        "？/万字": per10k(len(re.findall(r"[？?]", body))),
        "しかし/万字": per10k(body.count("しかし")),
        "段落数": len(paras),
    }


def measure(path: Path) -> dict:
    scenes = paragraphs(path.read_text(encoding="utf-8"))
    return {"file": str(path), **metrics([p for s in scenes for p in s])}


def load_profile() -> dict:
    if not PROFILE.exists():
        sys.exit(f"{PROFILE} がない。build_profile.py で作る（harness/文体/参照プロファイル.md）。")
    return json.loads(PROFILE.read_text(encoding="utf-8"))


def blend(m: dict, prof: dict) -> dict:
    """孫の手の重み w（0〜1）と、配合点からの距離を返す。

    指標ごとに「三嶋=0、孫の手=1」の物差しで本文の位置を出し、0〜1 に切り詰めてから
    作家差の二乗で重み付き平均する。切り詰めないと、両作家の外に飛んだ1指標（旧原稿の
    段落の長さなど）が配合をまるごと片側へ押し切る。飛び具合は距離と判定に出す。
    """
    num = den = resid = 0.0
    used = []
    for k, spec in prof["metrics"].items():
        if not spec["used_for_blend"] or k not in m:
            continue
        g, s, sd = spec["孫の手"]["value"], spec["三嶋"]["value"], spec["pooled_sd"]
        pos = min(max((m[k] - s) / (g - s), 0.0), 1.0)
        num += pos * spec["作家差"] ** 2
        den += spec["作家差"] ** 2
        used.append((m[k], g, s, sd))
    w = num / den if den else 0.5
    for x, g, s, sd in used:
        resid += ((x - (w * g + (1 - w) * s)) / sd) ** 2
    dist = (resid / max(len(used), 1)) ** 0.5
    # 作家本人の文章でも全指標がそろって振り切れはしないので、生の w は両端まで届かない。
    # 作家ごとの塊の中央値を 0 と 100 に合わせ直し、「4:6」のような目安とそのまま比べられるようにする。
    cal = prof.get("配合の較正")
    if cal:
        w = min(max((w - cal["三嶋"]) / (cal["孫の手"] - cal["三嶋"]), 0.0), 1.0)
    return {"孫の手": round(w * 100), "三嶋": 100 - round(w * 100), "距離": round(dist, 2)}


def judge(k: str, x: float, spec: dict) -> str:
    """目安（本作の文体）と参考作家の揺れ幅から、外れているかを一言で。"""
    notes = []
    tgt = spec.get("target")
    if tgt:
        if x < tgt[0]:
            notes.append(f"目安より少ない（{tgt[0]}〜{tgt[1]}）")
        elif x > tgt[1]:
            notes.append(f"目安より多い（{tgt[0]}〜{tgt[1]}）")
    lo = min(spec["孫の手"]["p10"], spec["三嶋"]["p10"])
    hi = max(spec["孫の手"]["p90"], spec["三嶋"]["p90"])
    if x < lo:
        notes.append(f"両作家より少ない（両作家の範囲 {lo}〜{hi}）")
    elif x > hi:
        notes.append(f"両作家より多い（両作家の範囲 {lo}〜{hi}）")
    if notes:
        return "✕ " + "／".join(notes)
    g, s = spec["孫の手"]["value"], spec["三嶋"]["value"]
    if not spec["used_for_blend"]:
        return "○"
    side = "孫の手寄り" if abs(x - g) < abs(x - s) else "三嶋寄り"
    return f"○ {side}"


def compare(m: dict, prof: dict) -> dict:
    b = blend(m, prof)
    rows = []
    for k, spec in prof["metrics"].items():
        if k in m:
            rows.append({"指標": k, "本文": m[k], "孫の手": spec["孫の手"]["value"],
                         "三嶋": spec["三嶋"]["value"], "旧原稿": spec.get("旧原稿", {}).get("value"),
                         "判定": judge(k, m[k], spec)})
    return {"配合": b, "指標": rows}


def distance_note(d: float, prof: dict) -> str:
    p90 = prof["distance_p90"]
    if d <= p90:
        return f"距離 {d}（参考作家の塊の90%が {p90} 以内 ＝ 配合で説明できる）"
    return f"距離 {d}（{p90} を超える ＝ どちらの作家にも似ていない指標がある）"


def print_compare(m: dict, prof: dict) -> None:
    c = compare(m, prof)
    b = c["配合"]
    lo, hi = prof["字数の目安"]
    if not lo <= m["字数"] <= hi:
        print(f"✕ 字数 {m['字数']} が目安（{lo}〜{hi}）の外")
    print(f"配合推定  孫の手 {b['孫の手']} : 三嶋 {b['三嶋']}   {distance_note(b['距離'], prof)}")
    print(f"  {'指標':<10}{'本文':>8}{'孫の手':>8}{'三嶋':>8}{'旧原稿':>8}  判定")
    for r in c["指標"]:
        old = "" if r["旧原稿"] is None else r["旧原稿"]
        print(f"  {r['指標']:<10}{r['本文']:>8}{r['孫の手']:>8}{r['三嶋']:>8}{old:>8}  {r['判定']}")


def scene_rows(path: Path, prof: dict) -> list[dict]:
    rows = []
    for i, sc in enumerate(paragraphs(path.read_text(encoding="utf-8")), 1):
        m = metrics(sc)
        if not m["字数"]:
            continue
        b = blend(m, prof)
        rows.append({"場面": i, "字数": m["字数"], "書き出し": sc[0][:16], **b,
                     "参考扱い": m["字数"] < SHORT_SCENE})
    return rows


def main(argv: list[str]) -> int:
    flags = {a for a in argv if a.startswith("--")}
    files = [a for a in argv if not a.startswith("--")]
    unknown = flags - {"--compare", "--scenes", "--json"}
    if not files or unknown:
        print(__doc__)
        return 2
    prof = load_profile() if flags & {"--compare", "--scenes"} else None
    for a in files:
        path = Path(a)
        m = measure(path)
        if "--json" in flags:
            out = dict(m)
            if "--compare" in flags and m["字数"]:
                out["比較"] = compare(m, prof)
            if "--scenes" in flags:
                out["場面"] = scene_rows(path, prof)
            print(json.dumps(out, ensure_ascii=False))
            continue
        print("  ".join(f"{k}={v}" for k, v in m.items()))
        if "--compare" in flags and m["字数"]:
            print_compare(m, prof)
        if "--scenes" in flags:
            for r in scene_rows(path, prof):
                ref = "  ※短いので参考" if r["参考扱い"] else ""
                print(f"  場面{r['場面']} {r['字数']}字 孫の手 {r['孫の手']} : 三嶋 {r['三嶋']}"
                      f"  距離 {r['距離']}  「{r['書き出し']}…」{ref}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.exit(0)
