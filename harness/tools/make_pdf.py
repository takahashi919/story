#!/usr/bin/env python3
"""Markdown の本文や文書を PDF にする。オーナーに「読んでもらうもの」は PDF で渡す。

使い方:
    python3 harness/tools/make_pdf.py <in.md> <out.pdf>          本文（A5。視点の印・見出し行は消す）
    python3 harness/tools/make_pdf.py --doc <in.md> <out.pdf>    文書（A4。見出し・箇条書き・表を整える）

要: reportlab、日本語フォント（IPAGothic など）。PDF の中身確認には pypdf（任意）。
外部の通信なし。
"""
import sys, re, html, pathlib

FONTS = [
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/truetype/ipafont-gothic/ipag.ttf",
]


def main():
    args = sys.argv[1:]
    doc = False
    if args and args[0] == "--doc":
        doc, args = True, args[1:]
    if len(args) != 2:
        print(__doc__)
        sys.exit(2)
    try:
        from reportlab.lib.pagesizes import A4, A5
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import SimpleDocTemplate, Paragraph
    except ImportError:
        sys.exit("reportlab が要ります（pip install reportlab）")
    font = next((f for f in FONTS if pathlib.Path(f).exists()), None)
    if not font:
        sys.exit("日本語フォント（IPAGothic）が見つかりません。FONTS に追加してください")
    pdfmetrics.registerFont(TTFont("JP", font))
    src, out = args
    lines = open(src, encoding="utf-8").read().split("\n")

    def st(name, size, lead, **kw):
        return ParagraphStyle(name, fontName="JP", fontSize=size, leading=lead, wordWrap="CJK", **kw)

    def esc(t):
        t = html.escape(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
        return re.sub(r"`(.+?)`", r"\1", t)

    story, title = [], "文書"
    if doc:
        S = {"h1": st("h1", 16, 24, spaceAfter=10, spaceBefore=4), "h2": st("h2", 13, 20, spaceAfter=6, spaceBefore=14),
             "h3": st("h3", 11, 17, spaceAfter=4, spaceBefore=8), "p": st("p", 9.5, 15, spaceAfter=4),
             "b1": st("b1", 9.5, 15, leftIndent=10, firstLineIndent=-8, spaceAfter=2),
             "b2": st("b2", 9.5, 15, leftIndent=22, firstLineIndent=-8, spaceAfter=2)}
        for ln in lines:
            if not ln.strip():
                continue
            if ln.startswith("# "):
                title = ln[2:].strip(); story.append(Paragraph(esc(title), S["h1"]))
            elif ln.startswith("## "):
                story.append(Paragraph(esc(ln[3:]), S["h2"]))
            elif ln.startswith("### "):
                story.append(Paragraph(esc(ln[4:]), S["h3"]))
            elif re.match(r"^\s{2,}- ", ln):
                story.append(Paragraph("・" + esc(ln.strip()[2:]), S["b2"]))
            elif ln.startswith("- "):
                story.append(Paragraph("・" + esc(ln[2:]), S["b1"]))
            elif re.match(r"^\d+\. ", ln):
                story.append(Paragraph(esc(ln), S["b1"]))
            elif ln.startswith("|"):
                cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                if set("".join(cells)) <= set("-: "):
                    continue
                story.append(Paragraph("・" + esc(" ／ ".join(cells)), S["b1"]))
            else:
                story.append(Paragraph(esc(ln), S["p"]))
        size, margins = A4, (18, 18, 16, 18)
    else:
        body = st("b", 10, 19, spaceAfter=7)
        head = st("h", 16, 24, spaceAfter=14)
        paras, cur = [], []
        for ln in lines:
            if ln.startswith("# "):
                title = ln[2:].strip(); continue
            if ln.startswith("<!--"):
                continue
            if not ln.strip():
                if cur:
                    paras.append("".join(cur)); cur = []
            else:
                cur.append(ln.strip())
        if cur:
            paras.append("".join(cur))
        story.append(Paragraph(html.escape(title), head))
        story += [Paragraph(html.escape(p), body) for p in paras]
        size, margins = A5, (16, 16, 16, 18)

    def footer(c, d):
        c.setFont("JP", 8)
        c.drawCentredString(size[0] / 2, 10 * mm, str(d.page))

    SimpleDocTemplate(out, pagesize=size, leftMargin=margins[0] * mm, rightMargin=margins[1] * mm,
                      topMargin=margins[2] * mm, bottomMargin=margins[3] * mm, title=title).build(
        story, onFirstPage=footer, onLaterPages=footer)
    print(out)


if __name__ == "__main__":
    main()
