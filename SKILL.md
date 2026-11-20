---
name: freehandfont
description: Turn someone's handwriting into a real installable font (.otf, Regular and optionally Bold) from phone photos of a printed template. Use when the user says "/freehandfont", wants a font of their own handwriting, or wants to turn handwritten letters into a typeface.
---

# Freehandfont

Pen, paper, phone, font. All the work is done by `freehandfont.py`, which sits in this skill's base directory. Call it `FF` below.

## 0. Setup (once)

```bash
python3 -m venv ~/.cache/freehandfont-venv
~/.cache/freehandfont-venv/bin/pip install -r <skill dir>/requirements.txt
```

Use `~/.cache/freehandfont-venv/bin/python` for every command below. Put the work in a folder the user picks, for example `~/freehandfont-<name>`, with `work/` for sheets and glyphs and `out/` for the fonts.

## 1. Ask first

Ask the user for these, in one message:

- **Font name**, e.g. "Ada Hand".
- **Pen colour**: blue, black, red or green. Any ballpoint or fineliner works. Pencil does not.
- **Extra letters** beyond basic A to Z, digits and punctuation, e.g. `åäöÅÄÖ`, `éèàçÉ`, `ñ¿¡`, `ßüÜ`.
- **Weights**: Regular only, or Regular and Bold. Bold needs a second filled-in sheet written with a thicker pen (a felt tip or marker).

## 2. Give them the template

```bash
FF template --out work --add "<extra letters>"
```

This writes `work/sheet-0.pdf` (more sheets if there are many characters) and `work/template.json`. Send the PDF to the user and tell them:

- Print it at any size. Colour is best. Black and white works too.
- Write one character per box, sitting on the solid yellow line. The dashed line is the top of small letters like x and n. Stay inside the box.
- Write the way you normally do. Slightly larger than usual is fine.
- For Bold, print a second copy and fill it in with the thicker pen.
- Take one photo per sheet: flat on a table, in daylight, no flash, the whole sheet in frame with all four black corner squares visible. Rotation doesn't matter.

## 3. Read the photos

One glyph folder per weight. Pass 1 to 3 photos.

```bash
FF extract work/template.json IMG_1.HEIC --pen blue --out work/regular
FF extract work/template.json IMG_2.HEIC --pen blue --out work/bold
```

It straightens each photo using the corner squares, works out which sheet the photo shows, reads the ink, and cuts out every box. Every box has the same size and baseline, so letters from different photos come out at the same scale.

If a photo fails ("could not find the four black corner squares"), ask for a retake. Say what to fix.

## 4. Check what's missing

`extract` prints the characters it found nothing for and the ones that touch the box edge, which may be cut off. Then **open `work/<weight>/review.png` with the Read tool and look at every tile.** Each tile shows the letter, its label (red if flagged) and a faint blue baseline. Look for:

- a tile that doesn't match its label (written in the wrong box, smudge, crossed out)
- a letter floating well above or sunk below the baseline
- strokes cut off at the box edge

Tell the user exactly which characters to redo, then make a sheet with only those:

```bash
FF template --out work --chars "<characters to redo>"
```

It appends a new sheet to `template.json` (`sheet-1.pdf`, ...). Run `extract` on just the new photo with the same `--out`. It merges: the new versions replace the old ones and everything else stays. Repeat until nothing is missing or wrong. If the user would rather skip a character, that's fine. The font just won't have it.

## 5. Build the font

```bash
FF build work/regular --name "Ada Hand" --style Regular --out out
FF build work/bold    --name "Ada Hand" --style Bold    --out out
```

Writes `out/AdaHand-Regular.otf` (and `-Bold`). It traces each letter into curves, sets the side spacing (`--sidebearing`, default 45 units) and adds kerning for pairs like AV, To and Ty from the actual letter shapes.

## 6. Proof sheet

```bash
FF proof out/AdaHand-Regular.otf out/proof-regular.pdf   # or .jpg
```

Shows every glyph, the tricky pairs and a few pangrams. Render a `.jpg` as well and look at it yourself before sending it. Check for:

- letters that collide or have gaps much wider than the rest: rebuild with `--sidebearing 30` (tighter) or `60` (looser)
- one letter much bigger or smaller than its neighbours, or sitting off the line: redo it with a retry sheet (step 4)
- "not in the font" characters in the output line

Send the user the proof and the `.otf` files.

## 7. Help them use it

**Mac:** double-click the `.otf` and press *Install* in Font Book. Or copy it to `~/Library/Fonts`.
**Windows:** right-click the `.otf` and choose *Install* (or *Install for all users*).
**Web:** put the files next to the CSS and add:

```css
@font-face {
  font-family: "Ada Hand";
  src: url("AdaHand-Regular.otf") format("opentype");
  font-weight: 400;
  font-display: swap;
}
@font-face {
  font-family: "Ada Hand";
  src: url("AdaHand-Bold.otf") format("opentype");
  font-weight: 700;
  font-display: swap;
}
body { font-family: "Ada Hand", cursive; }
```

Fill in the real font and file names. Leave out the Bold block if there's no Bold.

## Notes

- Inputs: 1 to 3 photos per weight, a font name, the pen colour. Outputs: `Name-Regular.otf`, optionally `Name-Bold.otf`, a proof PDF or JPG, and the CSS above.
- The template prints boxes and lines in pure yellow. The script reads ink from the green channel (red for a green pen), where yellow doesn't show, so the guides drop out without any line removal.
- `python test_roundtrip.py` runs the whole pipeline on a fake photo, to check the setup works.
