# 解説動画

| フォルダ | 中身 |
|---|---|
| `2026-10-12_制作の現在地/script.json` | 台本（14場面）。スライドの文言とナレーション、読み仮名の辞書、Fish Audio のモデルID |
| `tools/build_video.py` | スライド描画（Chromium）→ 音声（Fish Audio）→ 結合と字幕焼き込み（ffmpeg） |

## 作り方

```sh
python3 video/tools/build_video.py video/2026-10-12_制作の現在地
```

- 音声つきにするには Fish Audio の API キーが要る。クラウド環境では「ネットワークシークレット」で `api.fish.audio` 向けの `Authorization: Bearer <キー>` として登録する（スクリプト側の設定は不要）。手元のPCなら環境変数 `FISH_API_KEY`。
  - 声（モデル）は `script.json` の `fish_reference_id`（`6e4ec4c8c9d7407bab0a031af4d6c3db`）。
  - リクエストの `model` ヘッダは `FISH_MODEL`（既定 `s2.1-pro-free`。Fish Audio の無料 API の指定）。
  - キーがない・`api.fish.audio` に繋がらない時は、音声なし・字幕つきのプレビュー（`解説_プレビュー無音.mp4`）を作る。尺は1秒7字で見積もる。
- 音声を作り直したい場面は `audio/NN.mp3` を消してから再実行する（残っているものは再利用する）。
- 読み間違えた名前は `script.json` の `readings` に足す（字幕は漢字のまま、読み上げだけ置き換わる）。
- 必要なもの：Chromium、ffmpeg（libass 入り）、日本語フォント（Noto Sans/Serif CJK JP）。

生成物（`slides/`・`audio/`・`*.mp4`・`subs.ass`）はリポジトリに入れない（`.gitignore`）。
