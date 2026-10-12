#!/usr/bin/env python3
"""解説動画を作る（スライド画像 → Fish Audio の音声 → ffmpeg で結合、字幕焼き込み）。標準ライブラリのみ。

使い方（リポジトリ直下で）:
    python3 video/tools/build_video.py video/2026-10-12_制作の現在地            # 全部
    python3 video/tools/build_video.py video/2026-10-12_制作の現在地 --slides   # スライドだけ
    python3 video/tools/build_video.py video/2026-10-12_制作の現在地 --tts      # 音声だけ
    python3 video/tools/build_video.py video/2026-10-12_制作の現在地 --render   # 結合だけ

必要なもの:
- Chromium（スライドの描画）。環境変数 CHROME で場所を指定できる。なければ PATH と Playwright の場所を探す。
- ffmpeg / ffprobe（libass 入り）。日本語フォント（Noto Sans/Serif CJK JP 推奨）。
- 音声：環境変数 FISH_API_KEY（Fish Audio の API キー）。モデルIDは script.json の fish_reference_id。
  任意で FISH_MODEL（既定 "s1"）。キーがない・通信できない場合は、音声なしのプレビュー（字幕つき）を作る。

出力（台本フォルダの中）:
    slides/NN.png  audio/NN.mp3  subs.ass  解説.mp4（音声あり）または 解説_プレビュー無音.mp4
"""
import html
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

W, H = 1920, 1080
FISH_URL = "https://api.fish.audio/v1/tts"
CHARS_PER_SEC = 7.0  # 音声がない時の尺の見積もり（日本語の読み上げ速度の目安）
PAD = 0.7            # 場面の頭とお尻の間

CSS = """
:root { --bg:#0d1117; --ink:#e8e6e1; --dim:#9aa3ad; --light:#a9cbe4; --mud:#8a6a45; --line:#2a323c; }
* { margin:0; padding:0; box-sizing:border-box; }
html, body { width:1920px; height:1080px; background:var(--bg); color:var(--ink); position:relative;
  font-family:"Noto Sans CJK JP","IPAGothic",sans-serif; overflow:hidden; }
body::before { content:""; position:absolute; inset:0;
  background: repeating-linear-gradient(105deg, transparent 0 46px, rgba(169,203,228,.045) 46px 48px);
  pointer-events:none; }
.frame { position:absolute; left:120px; right:120px; top:96px; bottom:230px; display:flex; flex-direction:column; }
.kicker { font-size:30px; letter-spacing:.18em; color:var(--light); }
.kicker::before { content:""; display:inline-block; width:56px; height:2px; background:var(--light);
  vertical-align:middle; margin-right:22px; }
h1 { font-family:"Noto Serif CJK JP","IPAMincho",serif; font-weight:700; font-size:76px; line-height:1.3;
  margin-top:28px; white-space:pre-line; }
ul { list-style:none; margin-top:56px; }
li { font-size:40px; line-height:1.55; padding:14px 0 14px 46px; position:relative; border-top:1px solid var(--line); }
li:last-child { border-bottom:1px solid var(--line); }
li::before { content:""; position:absolute; left:6px; top:36px; width:14px; height:14px; background:var(--mud); transform:rotate(45deg); }
.title { justify-content:center; align-items:flex-start; }
.title h1 { font-size:124px; margin-top:36px; }
.title .sub { font-size:44px; color:var(--dim); margin-top:30px; letter-spacing:.12em; }
.two { display:flex; gap:64px; margin-top:52px; }
.col { flex:1; border-top:3px solid var(--line); padding-top:22px; }
.col.l { border-color:var(--mud); } .col.r { border-color:var(--light); }
.col h2 { font-size:40px; margin-bottom:12px; }
.col.l h2 { color:#c9a57a; } .col.r h2 { color:var(--light); }
.col p { font-size:36px; line-height:1.5; padding:10px 0; color:var(--ink); }
.steps { margin-top:52px; display:flex; flex-direction:column; gap:14px; }
.step { font-size:38px; line-height:1.4; display:flex; align-items:center; gap:28px; }
.step .n { flex:0 0 64px; height:64px; border:2px solid var(--light); color:var(--light); display:flex;
  align-items:center; justify-content:center; font-size:30px; font-family:"Noto Serif CJK JP",serif; }
.quote h1 { font-size:68px; }
"""


def slide_html(s: dict) -> str:
    e = html.escape
    k = s.get("kind", "points")
    head = f'<div class="kicker">{e(s.get("kicker", ""))}</div><h1>{e(s["title"])}</h1>'
    if k == "title":
        body = f'<div class="frame title">{head}<div class="sub">{e(s.get("sub", ""))}</div></div>'
    elif k == "two":
        col = lambda c, h, items: f'<div class="col {c}"><h2>{e(h)}</h2>' + "".join(f"<p>{e(x)}</p>" for x in items) + "</div>"
        body = (f'<div class="frame">{head}<div class="two">'
                f'{col("l", s["left_head"], s["left"])}{col("r", s["right_head"], s["right"])}</div></div>')
    elif k == "flow":
        steps = "".join(f'<div class="step"><div class="n">{i}</div><div>{e(x)}</div></div>'
                        for i, x in enumerate(s["steps"], 1))
        body = f'<div class="frame">{head}<div class="steps">{steps}</div></div>'
    else:  # points / quote
        cls = "frame quote" if k == "quote" else "frame"
        body = f'<div class="{cls}">{head}<ul>' + "".join(f"<li>{e(x)}</li>" for x in s.get("points", [])) + "</ul></div>"
    return f'<!doctype html><html lang="ja"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{body}</body></html>'


def find_chrome() -> str:
    for c in [os.environ.get("CHROME"), shutil.which("chromium"), shutil.which("chromium-browser"),
              shutil.which("google-chrome"), "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"]:
        if c and Path(c).exists():
            return c
    for c in sorted(Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome")):
        return str(c)
    sys.exit("Chromium が見つからない。環境変数 CHROME で指定してください。")


def render_slides(d: Path, script: dict) -> None:
    out = d / "slides"
    out.mkdir(exist_ok=True)
    chrome = find_chrome()
    for s in script["scenes"]:
        h = out / f"{s['id']}.html"
        h.write_text(slide_html(s), encoding="utf-8")
        png = out / f"{s['id']}.png"
        subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                        f"--window-size={W},{H}", f"--screenshot={png}", h.resolve().as_uri()],
                       check=True, capture_output=True)
        print("slide", png)


def tts_text(text: str, readings: dict) -> str:
    for k in sorted(readings, key=len, reverse=True):
        text = text.replace(k, readings[k])
    return text


def synth(d: Path, script: dict) -> bool:
    key = os.environ.get("FISH_API_KEY")
    if not key:
        print("FISH_API_KEY が未設定。音声は作らず、無音プレビューにします。")
        return False
    out = d / "audio"
    out.mkdir(exist_ok=True)
    for s in script["scenes"]:
        mp3 = out / f"{s['id']}.mp3"
        if mp3.exists() and mp3.stat().st_size > 0:
            continue
        body = json.dumps({"text": tts_text(s["narration"], script.get("readings", {})),
                           "reference_id": script["fish_reference_id"], "format": "mp3",
                           "normalize": True, "latency": "normal"}).encode()
        req = urllib.request.Request(FISH_URL, data=body, method="POST", headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json",
            "model": os.environ.get("FISH_MODEL", "s1")})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                mp3.write_bytes(r.read())
        except Exception as ex:  # 通信不可・キー不正など
            print(f"Fish Audio の呼び出しに失敗（{s['id']}）: {ex}\n無音プレビューに切り替えます。")
            return False
        print("tts", mp3)
    return True


def duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def ass_time(t: float) -> str:
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def chunks(text: str) -> list[str]:
    """字幕の1枚分に分ける：句点で切り、長い文は読点で切る（1枚32字前後）。"""
    out = []
    for sent in [x for x in re.split(r"(?<=。)", text) if x.strip()]:
        while len(sent) > 34:
            cut = max(sent.rfind("、", 0, 34), 0)
            cut = cut + 1 if cut else 34
            out.append(sent[:cut]); sent = sent[cut:]
        out.append(sent)
    return out


def render(d: Path, script: dict, with_audio: bool) -> Path:
    tmp = d / "_build"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    events, t0, parts = [], 0.0, []
    for s in script["scenes"]:
        png = d / "slides" / f"{s['id']}.png"
        mp3 = d / "audio" / f"{s['id']}.mp3"
        voice = duration(mp3) if with_audio else len(s["narration"]) / CHARS_PER_SEC
        dur = voice + PAD * 2
        seg = tmp / f"{s['id']}.mp4"
        audio_in = (["-itsoffset", str(PAD), "-i", str(mp3)] if with_audio
                    else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"])
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", "30", "-i", str(png), *audio_in,
                        "-filter_complex", f"[0:v]scale={W}:{H},format=yuv420p,fade=in:st=0:d=0.4,fade=out:st={dur-0.4:.2f}:d=0.4[v];"
                                           f"[1:a]apad,atrim=0:{dur:.3f},aresample=44100[a]",
                        "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "medium",
                        "-crf", "20", "-c:a", "aac", "-b:a", "160k", str(seg)], check=True)
        parts.append(seg)
        # 字幕：文字数の比で尺を配る
        cs = chunks(s["narration"])
        total = sum(len(c) for c in cs)
        t = t0 + PAD
        for c in cs:
            span = voice * len(c) / total
            events.append((t, t + span, c))
            t += span
        t0 += dur
    ass = d / "subs.ass"
    ass.write_text("\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Noto Sans CJK JP,50,&H00F0F0F0,&H000000FF,&H00101010,&H90000000,0,0,0,0,100,100,1,0,3,18,0,2,160,160,70,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        *[f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Default,,0,0,0,,{c}" for a, b, c in events]]) + "\n",
        encoding="utf-8")
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
    joined = tmp / "joined.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)], check=True)
    final = d / ("解説.mp4" if with_audio else "解説_プレビュー無音.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(joined), "-vf", f"ass={ass.resolve()}",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "copy", "-movflags", "+faststart",
                    str(final)], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print("video", final, f"{duration(final):.1f}s")
    return final


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    d = Path(argv[0])
    script = json.loads((d / "script.json").read_text(encoding="utf-8"))
    steps = set(argv[1:]) or {"--slides", "--tts", "--render"}
    if "--slides" in steps:
        render_slides(d, script)
    with_audio = False
    if "--tts" in steps:
        with_audio = synth(d, script)
    elif all((d / "audio" / f"{s['id']}.mp3").exists() for s in script["scenes"]):
        with_audio = True
    if "--render" in steps:
        render(d, script, with_audio)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
