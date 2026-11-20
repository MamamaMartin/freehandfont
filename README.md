# Freehandfont

Turn your handwriting into a real font you can install and type with. You need a pen, a printer and a phone.

It's a [Claude Code](https://claude.com/claude-code) skill. Type `/freehandfont` and Claude walks you through it: print a sheet, fill it in, send photos, get `.otf` files back. The script also works on its own from the command line.

## How it works

1. **Template.** A printable sheet with a box for each character. Boxes and lines are yellow, with black squares in the corners.
2. **Reads the photos.** It finds the corner squares, straightens the page and reads the ink. Yellow doesn't show in the green channel, so the printed lines drop out on their own.
3. **Cuts out each letter.** Every box has the same size and baseline, so letters from different photos come out the same size.
4. **Checks what's missing.** It lists empty boxes and letters touching the box edge, and makes a contact sheet to check by eye. You redo just those characters on a short retry sheet.
5. **Builds the font.** It traces each letter into curves and writes an `.otf` with spacing and kerning. You get Regular, and Bold too if you fill in a second sheet with a thicker pen.
6. **Proof sheet.** Every glyph plus tricky pairs like "AV" and "To", so you can see spacing problems before you install.
7. **Install steps** for Mac, Windows and the web (`@font-face`).

**In:** 1 to 3 photos per weight, a font name, the pen colour.
**Out:** `Name-Regular.otf`, optionally `Name-Bold.otf`, `proof.pdf` or a JPG, and a CSS snippet.

## Install the skill

```bash
git clone https://github.com/MamamaMartin/freehandfont ~/.claude/skills/freehandfont
```

Then type `/freehandfont` in Claude Code.

## Use it without Claude

```bash
pip install -r requirements.txt
python freehandfont.py template --out work --add "åäöÅÄÖ"
# print work/sheet-0.pdf, fill it in with a pen, take a photo
python freehandfont.py extract work/template.json photo.jpg --pen blue --out work/regular
python freehandfont.py build work/regular --name "My Hand" --out out
python freehandfont.py proof out/MyHand-Regular.otf out/proof.pdf
```

`python test_roundtrip.py` runs the whole pipeline on a fake photo.

## Why

I made a font of my own handwriting for [my site](https://martinkullander.com) and wanted anyone to be able to do the same.

MIT licensed.
