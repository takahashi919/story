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

視点の印:
- 場面の頭に <!-- 視点: 一人称 --> や <!-- 視点: 三人称（スメラギ） --> と書くと、場面の視点として読む。
  印は場面ごとに書く（引き継がない）。印のない場面は「未指定」で、比較からも外れる。
- 印があれば視点ごとの字数の配分を出し、--compare は「一人称」の場面だけを参考作家と比べる
  （参考文章は2作とも一人称なので、三人称の場面を混ぜると比べものにならない）。
"""
import json
import re
import sys
from pathlib import Path

PROFILE = Path(__file__).resolve().parents[1] / "文体" / "参照プロファイル.json"
SCENE_MARKERS = ("---", "＊＊＊", "◇")
SHORT_SCENE = 1500


POV_MARK = "\x00視点:"
FIRST_PERSON = "一人称"


def scenes(text: str) -> list[tuple[str, list[str]]]:
    """（視点, 段落リスト）の場面ごとのリスト。段落の空白は除去済み。場面の区切りは ---・＊＊＊・◇。"""
    text = re.sub(r"<!--\s*視点\s*[:：]\s*(.*?)\s*-->", lambda mo: f"\n{POV_MARK}{mo.group(1)}\n", text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    out, cur, pov = [], [], ""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(POV_MARK):
            pov = s[len(POV_MARK):]
            continue
        if s in SCENE_MARKERS:
            if cur:
                out.append((cur_pov, cur))
            # 視点は場面ごとに書く。引き継ぐと、印を書き忘れた一人称の場面が三人称として数えられる
            cur, pov = [], ""
            continue
        if not s or s.startswith("#"):
            continue
        if not cur:
            cur_pov = pov  # 場面の視点は、最初の段落の時点の印で決める
        cur.append(re.sub(r"\s", "", s))
    if cur:
        out.append((cur_pov, cur))
    return out


def paragraphs(text: str) -> list[list[str]]:
    return [ps for _, ps in scenes(text)]


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
    scs = scenes(path.read_text(encoding="utf-8"))
    return {"file": str(path), **metrics([p for _, ps in scs for p in ps])}


def pov_split(path: Path) -> dict[str, int]:
    """視点ごとの字数。視点の印が一つもなければ空。"""
    scs = scenes(path.read_text(encoding="utf-8"))
    if not any(pov for pov, _ in scs):
        return {}
    split: dict[str, int] = {}
    for pov, ps in scs:
        split[pov or "未指定"] = split.get(pov or "未指定", 0) + sum(len(p) for p in ps)
    return split


def first_person(path: Path) -> list[str]:
    return [p for pov, ps in scenes(path.read_text(encoding="utf-8")) if pov.startswith(FIRST_PERSON) for p in ps]


def split_note(split: dict[str, int]) -> str:
    total = sum(split.values())
    return "視点の配分  " + " / ".join(f"{k} {v}字（{round(v * 100 / total)}%）" for k, v in split.items())


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


def compare_target(path: Path, m: dict) -> tuple[dict, str]:
    """比べる本文の数値と、その説明。視点の印があれば一人称の場面だけ。"""
    if not pov_split(path):
        return m, ""
    fp = first_person(path)
    if not fp:
        return {"字数": 0}, "一人称の場面がないので、参考作家とは比べない"
    fm = metrics(fp)
    return fm, f"比べた範囲：一人称の場面だけ（{fm['字数']}字）。三人称の場面は一人称の参考作家と比べない"


def print_compare(path: Path, m: dict, prof: dict) -> None:
    lo, hi = prof["字数の目安"]
    if not lo <= m["字数"] <= hi:
        print(f"✕ 字数 {m['字数']} が目安（{lo}〜{hi}）の外")
    cm, note = compare_target(path, m)
    if note:
        print(note)
    if not cm["字数"]:
        return
    c = compare(cm, prof)
    b = c["配合"]
    print(f"配合推定  孫の手 {b['孫の手']} : 三嶋 {b['三嶋']}   {distance_note(b['距離'], prof)}")
    print(f"  {'指標':<10}{'本文':>8}{'孫の手':>8}{'三嶋':>8}{'旧原稿':>8}  判定")
    for r in c["指標"]:
        old = "" if r["旧原稿"] is None else r["旧原稿"]
        print(f"  {r['指標']:<10}{r['本文']:>8}{r['孫の手']:>8}{r['三嶋']:>8}{old:>8}  {r['判定']}")


def scene_rows(path: Path, prof: dict) -> list[dict]:
    rows = []
    for i, (pov, sc) in enumerate(scenes(path.read_text(encoding="utf-8")), 1):
        m = metrics(sc)
        if not m["字数"]:
            continue
        b = blend(m, prof)
        rows.append({"場面": i, "視点": pov or "未指定", "字数": m["字数"], "書き出し": sc[0][:16], **b,
                     "参考扱い": m["字数"] < SHORT_SCENE or (bool(pov) and not pov.startswith(FIRST_PERSON))})
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
        split = pov_split(path)
        if "--json" in flags:
            out = dict(m)
            if split:
                out["視点の配分"] = split
            if "--compare" in flags and m["字数"]:
                cm, note = compare_target(path, m)
                out["比較"] = compare(cm, prof) | {"範囲": note or "全体"} if cm["字数"] else {"範囲": note}
            if "--scenes" in flags:
                out["場面"] = scene_rows(path, prof)
            print(json.dumps(out, ensure_ascii=False))
            continue
        print("  ".join(f"{k}={v}" for k, v in m.items()))
        if split:
            print(split_note(split))
        if "--compare" in flags and m["字数"]:
            print_compare(path, m, prof)
        if "--scenes" in flags:
            for r in scene_rows(path, prof):
                ref = "  ※参考（短い、または三人称）" if r["参考扱い"] else ""
                print(f"  場面{r['場面']} [{r['視点']}] {r['字数']}字 孫の手 {r['孫の手']} : 三嶋 {r['三嶋']}"
                      f"  距離 {r['距離']}  「{r['書き出し']}…」{ref}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.exit(0)
