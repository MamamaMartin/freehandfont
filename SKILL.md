---
name: freehandfont
description: Turn someone's handwriting into a real installable font (.otf, Regular and optionally Bold) from phone photos of letters written on any paper. Use when the user says "/freehandfont", wants a font of their own handwriting, or wants to turn handwritten letters into a typeface.
---

# Freehandfont

Pen, paper, phone, font. No printer needed. All the work is done by `freehandfont.py`, which sits in this skill's base directory. Call it `FF` below.

## 0. Setup (once)

```bash
python3 -m venv ~/.cache/freehandfont-venv
~/.cache/freehandfont-venv/bin/pip install -r <skill dir>/requirements.txt
```

Use `~/.cache/freehandfont-venv/bin/python` for every command below. Put the work in a folder the user picks, for example `~/freehandfont-<name>`, with `work/` for glyphs and `out/` for the fonts.

## 1. Ask first

Ask the user for these, in one message:

- **Font name**, e.g. "Ada Hand".
- **Pen colour**: blue, black, red or green. Any ballpoint or fineliner works. Pencil does not.
- **Extra letters** beyond basic A to Z, digits and punctuation, e.g. `åäöÅÄÖ`, `éèàçÉ`, `ñ¿¡`, `ßüÜ`.
- **Weights**: Regular only, or Regular and Bold. Bold is a second full set written with a thicker pen (a felt tip or marker).

## 2. Tell them what to write

Any paper works, ruled or blank. Ask them to write, in rows:

- capitals: `A B C ... Z` plus their extra capitals
- small letters: `a b c ... z` plus their extra small letters
- digits: `1 2 3 4 5 6 7 8 9 0`
- punctuation: `. , ; : ! ? ' " - ( ) / & @ # $ % * + = _ [ ] { } < > | \ ^ ~` and any they use, like `€ £`

Tips to pass on:

- Leave about a finger's width between characters, and don't let them touch.
- Write the way you normally do, slightly bigger is fine. Keep each row on one line.
- A mistake? Scribble it out and write it again next to it.
- Take close-up photos, 1 to 3 per weight, from straight above, in daylight, without your shadow on the page. Turning the phone sideways is fine.

## 3. Cut out the letters

Do one photo at a time, and do photos that have letters before ones that only have punctuation.

**First a preview:**

```bash
FF cut IMG_1.HEIC --pen blue --out work/regular
```

It prints how many rows it found and how many glyphs in each, and writes `work/regular/preview-IMG_1.png`. **Open the preview with the Read tool.** It shows the ink with a numbered box around every glyph and a label for every row.

- Letters sideways or upside down? Run again with `--rotate 90`, `180` or `270` (degrees clockwise).
- Two characters in one box: run again with a smaller `--gap` (default 0.25), e.g. `0.15`.
- One character split into two boxes: run again with a bigger `--gap`, e.g. `0.4`.

**Then say what each row is.** Write a rows file, one line per row in the preview, top to bottom, with each box's character in order:

```
ABCDEFHIJK
LMNOPQRSTUVW
abcdefghijkl
mnopqrs□tuv
```

- `□` marks a box to leave out: a scribble, a speck, a stray mark.
- An empty line skips a whole row. Rows past the end of the file are skipped.

```bash
FF cut IMG_1.HEIC --pen blue --rows work/rows-1.txt --out work/regular
```

A row whose count doesn't match is skipped with a message. Fix that line and run again. The tool sizes letters from the capitals and small letters in each photo, so photos taken from different distances match. A photo with only punctuation is sized from the ruled lines, measured on an earlier photo. On blank paper, a punctuation-only photo needs at least one letter on it as well.

Use one glyph folder per weight (`work/regular`, `work/bold`). New photos merge into the folder: a character cut again replaces the old one, and everything else stays.

## 4. Check what's missing

Open `work/<weight>/review.png` with the Read tool and look at every tile. Each one shows the glyph, its label and a faint blue baseline. Look for a tile that doesn't match its label, a letter floating well above or sunk below the baseline, or strokes cut off. Compare the list `cut` prints against what the user wanted.

Tell the user exactly which characters to redo. They write just those on any paper, take one photo, and you cut it into the same folder. Repeat until nothing is missing or wrong. If they'd rather skip a character, that's fine. The font just won't have it.

## 5. Build the font

```bash
FF build work/regular --name "Ada Hand" --style Regular --out out
FF build work/bold    --name "Ada Hand" --style Bold    --out out
```

Writes `out/AdaHand-Regular.otf` (and `-Bold`). It traces each letter into curves, sets the side spacing (`--sidebearing`, default 45 units) and adds kerning for pairs like AV, To and Ty from the actual letter shapes.

## 6. Proof sheet

```bash
FF proof out/AdaHand-Regular.otf out/proof-regular.pdf   # or .jpg / .png
```

Shows every glyph, the tricky pairs and a few pangrams. Render a `.png` as well and look at it yourself before sending it. Check for:

- letters that collide, or gaps much wider than the rest: rebuild with `--sidebearing 30` (tighter) or `60` (looser)
- one letter much bigger or smaller than its neighbours, or sitting off the line: redo it (step 4)
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

## Optional: a printed sheet

If the user has a printer and wants the most hands-off route, there's a template with a box per character:

```bash
FF template --out work --add "<extra letters>"         # work/sheet-0.pdf
FF extract work/template.json IMG_1.HEIC --pen blue --out work/regular
FF template --out work --chars "<characters to redo>"  # a retry sheet with just those
```

Boxes and lines print in yellow, which the script can't see, and black corner squares let it straighten and identify each sheet. No rows file needed. `extract` writes the same glyph folder, so steps 4 to 7 are the same. Freehand and template glyphs can even go in the same folder.

## Notes

- Inputs: 1 to 3 photos per weight, a font name, the pen colour. Outputs: `Name-Regular.otf`, optionally `Name-Bold.otf`, a proof PDF or image, and the CSS above.
- `python test_roundtrip.py` runs both routes on fake photos, to check the setup works.
