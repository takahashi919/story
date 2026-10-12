#!/usr/bin/env python3
"""勝浦の1980〜1982年の天気を引く（気象庁の日別値。標準ライブラリのみ）。

元データ: data/気象/勝浦_1980-1982_日別_気象庁原本.txt（気象庁「過去の気象データ」勝浦の日ごとの値。オーナーが用意）

使い方:
    python3 harness/tools/weather.py 1980-05-04 1980-05-10      日付ごとの天気
    python3 harness/tools/weather.py --month 1980-06             その月の全日
    python3 harness/tools/weather.py --rain 1980-05              その月の雨の日だけ
    python3 harness/tools/weather.py --rain 1980-05-01 1980-08-31   期間の雨の日だけ

「雨の日」の判定: 天気概況（昼 06-18時 / 夜 18-翌06時）に「雨」を含む、または日降水量が 1.0mm 以上。
エイリアンは海水を含む雨の日に出る（canon/世界/エイリアンと雨.md）。昼に降ったか夜に降ったかで、
襲来の時間帯も決められる。降水量 0.0 は「降ったが 0.5mm 未満」、-- は「降水なし」。
"""
import re
import sys
from datetime import date, timedelta
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "data/気象/勝浦_1980-1982_日別_気象庁原本.txt"
# 1日分の行の列（気象庁の表の並び）
COLS = ["現地気圧", "海面気圧", "降水量", "最大1時間", "最大10分間", "平均気温", "最高気温", "最低気温",
        "平均湿度", "最小湿度", "平均風速", "最大風速", "最大風速の風向", "最大瞬間風速", "最大瞬間風速の風向",
        "日照時間", "降雪", "最深積雪", "天気昼", "天気夜"]
WEEK = "月火水木金土日"


def load() -> dict[date, dict]:
    lines = SRC.read_text(encoding="utf-8").replace("\r", "").split("\n")
    head = re.compile(r"勝浦（千葉県\)\s*(\d{4})年(\d{1,2})月")
    days, ym, i = {}, None, 0
    while i < len(lines):
        m = head.search(lines[i])
        if m:
            ym = (int(m.group(1)), int(m.group(2)))
        elif ym and re.fullmatch(r"\d{1,2}", lines[i].strip()) and i + 1 < len(lines):
            f = lines[i + 1].split("\t")
            if len(f) >= 20:
                days[date(ym[0], ym[1], int(lines[i].strip()))] = dict(zip(COLS, f[:20]))
                i += 1
        i += 1
    return days


def rainy(d: dict) -> bool:
    if "雨" in d["天気昼"] or "雨" in d["天気夜"]:
        return True
    try:
        return float(d["降水量"]) >= 1.0
    except ValueError:
        return False


def line(day: date, d: dict | None) -> str:
    if d is None:
        return f"{day} {WEEK[day.weekday()]}  （データなし。1980〜1982年のみ）"
    mark = "☔" if rainy(d) else "  "
    return (f"{day} {WEEK[day.weekday()]} {mark} 降水量 {d['降水量']:>5}mm（最大1時間 {d['最大1時間']}）"
            f"  昼:{d['天気昼']}  夜:{d['天気夜']}  気温 {d['最低気温']}〜{d['最高気温']}℃"
            f"  風 {d['最大風速の風向']}{d['最大風速']}m/s  日照 {d['日照時間']}h")


def span(a: str, b: str | None) -> list[date]:
    if re.fullmatch(r"\d{4}-\d{2}", a) and b is None:
        y, m = map(int, a.split("-"))
        start = date(y, m, 1)
        end = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    else:
        start, end = date.fromisoformat(a), date.fromisoformat(b or a)
    return [start + timedelta(n) for n in range((end - start).days + 1)]


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    days = load()
    if argv[0] in ("--month", "--rain"):
        targets = span(argv[1], argv[2] if len(argv) > 2 else None)
        if argv[0] == "--rain":
            targets = [t for t in targets if t in days and rainy(days[t])]
            print(f"雨の日 {len(targets)}日")
    else:
        targets = [date.fromisoformat(a) for a in argv]
    for t in targets:
        print(line(t, days.get(t)))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:  # | head などで途中まで読まれた時
        sys.exit(0)
