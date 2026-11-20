#!/usr/bin/env python3
"""Freehandfont: turn photos of a filled-in template into an .otf font.

  python freehandfont.py template --out work [--add "åäöÅÄÖ"] [--chars "Gq?"]
  python freehandfont.py extract work/template.json IMG_1.jpg IMG_2.jpg --pen blue --out work/regular
  python freehandfont.py build work/regular --name "Ada Hand" --style Regular --out out
  python freehandfont.py proof out/AdaHand-Regular.otf out/proof.pdf
"""
import argparse, json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from scipy import ndimage as ndi
try:
    from pillow_heif import register_heif_opener  # iPhone photos are HEIC
    register_heif_opener()
except ImportError:
    pass

# Page geometry in px at 300 dpi (US Letter). Any print scale works: the corner squares define the page.
W, H = 2550, 3300
MARK, INSET = 120, 120                      # black corner squares
CODE_Y, CODE_S, CODE_STEP = 135, 45, 80     # 7 small squares on top: sync bit + 6-bit sheet id
CELL_W, LABEL_H, CELL_H = 180, 40, 260      # each box: printed label on top, writing area below
COLS, ROWS, GRID_X, GRID_Y = 12, 10, 195, 330
BASE, XH = 150, 70                          # baseline and x-height guide, px from the top of the writing area
INNER = 6                                   # crop this far inside each box so its printed edges never count
UPX = 6                                     # font units per px: writing area above the baseline = 900 units
YELLOW, GREY = (255, 255, 0), (110, 110, 110)  # yellow vanishes in the green channel, which is where we read ink
DEFAULT_CHARS = ''.join(chr(c) for c in range(33, 127))
CORNERS = [(INSET + MARK / 2, INSET + MARK / 2), (W - INSET - MARK / 2, INSET + MARK / 2),
           (W - INSET - MARK / 2, H - INSET - MARK / 2), (INSET + MARK / 2, H - INSET - MARK / 2)]


def ui_font(size):
    """A system font with accented letters for labels; Pillow's built-in one lacks them."""
    for name in ('Arial Unicode.ttf', 'Arial.ttf', 'arial.ttf', 'DejaVuSans.ttf', 'Helvetica.ttc'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def code_box(i):
    x = W // 2 - 7 * CODE_STEP // 2 + i * CODE_STEP
    return x, CODE_Y, x + CODE_S, CODE_Y + CODE_S


def cell_xy(i):
    r, c = divmod(i, COLS)
    return GRID_X + c * CELL_W, GRID_Y + r * CELL_H


# ---------- template ----------

def draw_page(chars, page_id):
    im = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(im)
    for x, y in CORNERS:
        d.rectangle([x - MARK / 2, y - MARK / 2, x + MARK / 2, y + MARK / 2], fill='black')
    for i in range(7):
        if i == 0 or page_id >> (i - 1) & 1:
            d.rectangle(code_box(i), fill='black')
    d.text((W / 2, 250), f'Freehandfont sheet {page_id}. One character per box, sitting on the yellow line.',
           fill=GREY, font=ui_font(34), anchor='mm')
    label = ui_font(30)
    for i, ch in enumerate(chars):
        x, y = cell_xy(i)
        b = y + LABEL_H + BASE
        d.rectangle([x, y, x + CELL_W, y + CELL_H], outline=YELLOW, width=4)
        d.line([x, y + LABEL_H, x + CELL_W, y + LABEL_H], fill=YELLOW, width=3)
        d.text((x + CELL_W / 2, y + LABEL_H / 2), ch, fill=GREY, font=label, anchor='mm')
        d.line([x, b, x + CELL_W, b], fill=YELLOW, width=5)
        for xx in range(x + 6, x + CELL_W - 6, 24):
            d.line([xx, b - XH, xx + 12, b - XH], fill=YELLOW, width=3)
    return im


def cmd_template(a):
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, 'template.json')
    pages = json.load(open(path, encoding='utf-8'))['pages'] if os.path.exists(path) else {}
    chars = [c for c in dict.fromkeys(a.chars + a.add) if not c.isspace()]
    per = COLS * ROWS
    for k in range(0, len(chars), per):
        pid = len(pages)
        if pid >= 64:
            raise SystemExit(f'{path} already has 64 sheets; start a new work folder')
        pages[str(pid)] = ''.join(chars[k:k + per])
        out = os.path.join(a.out, f'sheet-{pid}.pdf')
        draw_page(chars[k:k + per], pid).save(out, resolution=300)
        print('wrote', out, f'({len(pages[str(pid)])} characters)')
    json.dump({'pages': pages}, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


# ---------- extract ----------

def darkness(a):
    """How much darker each pixel is than the paper around it (evens out shadows and uneven light)."""
    a = a.astype(float)
    bg = ndi.percentile_filter(a[::8, ::8], 90, size=25)  # brightest-ish nearby = paper, even next to a dark desk
    bg = np.kron(bg, np.ones((8, 8)))[:a.shape[0], :a.shape[1]]
    return bg - a


def homography(src, dst):
    A, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        A += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        b += [u, v]
    return np.append(np.linalg.solve(np.array(A, float), b), 1).reshape(3, 3)


def find_corners(rgb):
    """Centres of the four black corner squares in the photo, as [top-left, top-right, bottom-right, bottom-left]."""
    s = 1000 / max(rgb.shape[:2])
    small = np.asarray(Image.fromarray(rgb).resize((round(rgb.shape[1] * s), round(rgb.shape[0] * s)))).mean(2)
    lab, _ = ndi.label(darkness(small) > 60)
    cands = []
    for i, sl in enumerate(ndi.find_objects(lab), 1):
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        blob = lab[sl] == i
        if 12 <= min(h, w) and max(h, w) <= 80 and max(h, w) < 2 * min(h, w) and blob.sum() > 0.5 * h * w:
            ys, xs = np.nonzero(blob)
            cands.append((xs.mean() + sl[1].start, ys.mean() + sl[0].start))
    if len(cands) < 4:
        raise ValueError('could not find the four black corner squares')
    c = np.array(cands)
    pick = [np.argmin(c.sum(1)), np.argmax(c[:, 0] - c[:, 1]), np.argmax(c.sum(1)), np.argmax(c[:, 1] - c[:, 0])]
    if len(set(pick)) < 4:
        raise ValueError('could not tell the four corner squares apart')
    return c[pick] / s


def straighten(rgb):
    """Warp the photo onto the template's coordinates, trying all four rotations and keeping the one
    where the sync square (always black) lands on ink."""
    pts, lum = find_corners(rgb), rgb.mean(2)
    x0, y0, x1, y1 = code_box(0)
    best = None
    for k in range(4):
        Hm = homography(CORNERS, np.roll(pts, -k, axis=0))
        u, v, w = Hm @ ((x0 + x1) / 2, (y0 + y1) / 2, 1)
        u, v = int(np.clip(u / w, 3, lum.shape[1] - 4)), int(np.clip(v / w, 3, lum.shape[0] - 4))
        val = lum[v - 3:v + 4, u - 3:u + 4].mean()
        if best is None or val < best[0]:
            best = (val, Hm)
    Hm = best[1] / best[1][2, 2]
    return np.asarray(Image.fromarray(rgb).transform((W, H), Image.PERSPECTIVE, Hm.ravel()[:8], Image.BICUBIC))


def box_mean(d, box):
    x0, y0, x1, y1 = box
    m = (x1 - x0) // 4
    return d[y0 + m:y1 - m, x0 + m:x1 - m].mean()


def cmd_extract(a):
    pages = json.load(open(a.template, encoding='utf-8'))['pages']
    os.makedirs(a.out, exist_ok=True)
    meta_path = os.path.join(a.out, 'glyphs.json')
    glyphs = json.load(open(meta_path, encoding='utf-8'))['glyphs'] if os.path.exists(meta_path) else {}
    channel = 0 if a.pen == 'green' else 1   # read ink in the channel the yellow guides don't show in
    for photo in a.photos:
        rgb = np.asarray(ImageOps.exif_transpose(Image.open(photo)).convert('RGB'))
        try:
            page = straighten(rgb)
        except ValueError as e:
            print(f'{photo}: {e}. Retake it flat, with the whole sheet and all four squares in view.')
            continue
        pid = sum(1 << (i - 1) for i in range(1, 7) if box_mean(darkness(page.mean(2)), code_box(i)) > 60)
        if str(pid) not in pages:
            print(f'{photo}: sheet id {pid} is not in {a.template}; skipped')
            continue
        ink = darkness(page[..., channel]) > 40
        got = 0
        for i, ch in enumerate(pages[str(pid)]):
            x, y = cell_xy(i)
            crop = ink[y + LABEL_H + INNER:y + CELL_H - INNER, x + INNER:x + CELL_W - INNER]
            lab, n = ndi.label(crop)
            sizes = ndi.sum(crop, lab, range(1, n + 1))
            crop = np.isin(lab, 1 + np.nonzero(np.asarray(sizes) >= 30)[0])  # drop specks
            if not crop.any():
                continue
            edge = crop[0].any() or crop[-1].any() or crop[:, 0].any() or crop[:, -1].any()
            name = f'U+{ord(ch):04X}.png'
            Image.fromarray(np.where(crop, 0, 255).astype(np.uint8)).save(os.path.join(a.out, name))
            glyphs[ch] = {'file': name, 'photo': os.path.basename(photo), 'flags': ['touches the box edge'] if edge else []}
            got += 1
        print(f'{photo}: sheet {pid}, {got} characters')
    json.dump({'baseline': BASE - INNER, 'units_per_px': UPX, 'glyphs': glyphs},
              open(meta_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    review(glyphs, a.out)
    missing = [c for c in dict.fromkeys(''.join(pages.values())) if c not in glyphs]
    flagged = [c for c, g in glyphs.items() if g['flags']]
    print(f'{len(glyphs)} glyphs in {a.out}. Contact sheet: {os.path.join(a.out, "review.png")}')
    print('missing:', ''.join(missing) or 'none')
    print('touching the box edge (may be cut off):', ''.join(flagged) or 'none')


def review(glyphs, folder, T=150, cols=12):
    """One tile per glyph, label in red when flagged, faint blue baseline, so a person (or Claude) can check them."""
    chars = list(glyphs)
    im = Image.new('RGB', (cols * T, max(1, -(-len(chars) // cols)) * T), 'white')
    d, f = ImageDraw.Draw(im), ui_font(22)
    for i, ch in enumerate(chars):
        x, y = i % cols * T, i // cols * T
        g = Image.open(os.path.join(folder, glyphs[ch]['file']))
        scale = min((T - 10) / g.width, (T - 34) / g.height)
        g = g.resize((round(g.width * scale), round(g.height * scale)))
        im.paste(g.convert('RGB'), (x + 5, y + 30))
        by = y + 30 + (BASE - INNER) * scale
        d.line([x + 5, by, x + 5 + g.width, by], fill=(150, 190, 255), width=1)
        d.text((x + 5, y + 3), ch, fill='red' if glyphs[ch]['flags'] else 'black', font=f)
        d.rectangle([x, y, x + T - 1, y + T - 1], outline=(220, 220, 220))
    im.save(os.path.join(folder, 'review.png'))


# ---------- build ----------

def trace(bitmap):
    import potrace  # the "potracer" package
    return potrace.Bitmap(~bitmap).trace(turdsize=20, alphamax=1.0, opticurve=True, opttolerance=0.3)  # falsy = ink


def draw(plist, pen, fx):
    for curve in plist:
        pen.moveTo(fx(curve.start_point))
        for seg in curve.segments:
            if seg.is_corner:
                pen.lineTo(fx(seg.c)); pen.lineTo(fx(seg.end_point))
            else:
                pen.curveTo(fx(seg.c1), fx(seg.c2), fx(seg.end_point))
        pen.closePath()


def smooth(bmp, pad=20):
    return ndi.gaussian_filter(np.pad(bmp, pad).astype(float), 2.0) > 0.5, pad


def profile(m, base, xmin, upx, sb, step=20):
    """Leftmost/rightmost ink x (font units) per 20-unit band of height; used for kerning."""
    ys, xs = np.nonzero(m)
    yu = ((base - ys) * upx // step).astype(int)
    xu = (xs - xmin) * upx + sb
    left, right = {}, {}
    for b in np.unique(yu):
        sel = xu[yu == b]
        left[b], right[b] = sel.min(), sel.max()
    return left, right


def kern_pairs(chars):
    """Pairs worth kerning in handwriting: overhangs (T, F, P, V, W, Y), diagonals (A/V), open sides (L, r)."""
    lower = [c for c in chars if c.islower()] + ['.', ',']
    a_like = [c for c in chars if c in 'AÀÁÂÃÄÅ']
    return ([(l, r) for l in 'TFPVWY' for r in lower] + [(l, r) for l in a_like for r in 'TVWYvwy'] +
            [(l, r) for l in 'TVWY' for r in a_like] + [('L', r) for r in "TVWY'\""] +
            [(l, r) for l in 'rvwyf' for r in '.,'])


def kern_value(L, R, target):
    (adv, _, right), (_, left, _) = L, R
    common = set(right) & set(left)
    for b in list(common):  # also compare neighbouring bands so diagonals don't touch
        common |= {b - 1, b + 1} & set(left) & set(right)
    if not common:
        return 0
    gap = min(adv - right[b] + left[b] for b in common)
    return int(max(-90, min(0, 0.5 * (target - gap))))  # half strength, only tighten, at most 90 units


def cmd_build(a):
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.t2CharStringPen import T2CharStringPen
    from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
    meta = json.load(open(os.path.join(a.glyphs, 'glyphs.json'), encoding='utf-8'))
    upx, sb, bold = meta['units_per_px'], a.sidebearing, a.style.lower() == 'bold'
    order, cmap, charstrings, metrics, prof = ['.notdef', 'space'], {}, {}, {}, {}
    for ch, g in meta['glyphs'].items():
        m, pad = smooth(np.asarray(Image.open(os.path.join(a.glyphs, g['file'])).convert('L')) < 128)
        base = meta['baseline'] + pad
        ys, xs = np.nonzero(m)
        xmin, xmax = xs.min(), xs.max()
        fx = lambda p: (round((p.x - xmin) * upx + sb), round((base - p.y) * upx))
        adv = round((xmax - xmin) * upx + 2 * sb)
        name = f'uni{ord(ch):04X}'
        pen = T2CharStringPen(adv, None)
        draw(trace(m), pen, fx)
        order.append(name)
        charstrings[name], metrics[name], cmap[ord(ch)] = pen.getCharString(), (adv, sb), name
        prof[ch] = (adv, *profile(m, base, xmin, upx, sb))
    lower = [metrics[cmap[ord(c)]][0] for c in 'nou' if ord(c) in cmap]
    space = round(0.6 * np.median(lower)) if lower else 300
    for name, adv in (('.notdef', 500), ('space', space)):
        charstrings[name], metrics[name] = T2CharStringPen(adv, None).getCharString(), (adv, 0)
    cmap[32] = cmap[160] = 'space'

    family = a.name
    ps = ''.join(c for c in family if c.isascii() and c.isalnum()) or 'Freehand'
    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupCFF(f'{ps}-{a.style}', {'FullName': f'{family} {a.style}'}, charstrings, {})
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=950, descent=-450)
    fb.setupNameTable({'familyName': family, 'styleName': a.style})
    fb.setupOS2(sTypoAscender=950, sTypoDescender=-450, sTypoLineGap=100, usWinAscent=1150, usWinDescent=500,
                usWeightClass=700 if bold else 400, fsSelection=0x20 if bold else 0x40)
    fb.setupPost()
    kerns = [(l, r, kern_value(prof[l], prof[r], target=2 * sb + 10))
             for l, r in kern_pairs(prof) if l in prof and r in prof]
    kerns = [k for k in kerns if k[2] <= -10]
    if kerns:
        addOpenTypeFeaturesFromString(fb.font, 'feature kern {\n' + ''.join(
            f'  pos uni{ord(l):04X} uni{ord(r):04X} {v};\n' for l, r, v in kerns) + '} kern;\n')
    fb.font['head'].macStyle = 1 if bold else 0
    os.makedirs(a.out, exist_ok=True)
    out = os.path.join(a.out, f'{ps}-{a.style}.otf')
    fb.save(out)
    print(f'wrote {out}: {len(meta["glyphs"])} glyphs, {len(kerns)} kern pairs')


# ---------- proof ----------

PAIRS = 'AV AW AY Av Aw Ay LT LV LY To Ta Te Tr Ty Va Ve Vo Wa We Wo Ya Ye Yo P. F, r. y, f.'
PROOF_LINES = ['The quick brown fox jumps over the lazy dog.', 'Sphinx of black quartz, judge my vow!',
               'THE FIVE BOXING WIZARDS JUMP QUICKLY', '0123456789 (){}[] ?!&@#%$*+=/']


def cmd_proof(a):
    from fontTools.ttLib import TTFont
    tt = TTFont(a.font)
    cmap, hmtx = tt.getBestCmap(), tt['hmtx']
    kern = {}
    if 'GPOS' in tt:
        for lk in tt['GPOS'].table.LookupList.Lookup:
            for st in lk.SubTable:
                if st.Format == 1:
                    for first, ps in zip(st.Coverage.glyphs, st.PairSet):
                        for r in ps.PairValueRecord:
                            kern[first, r.SecondGlyph] = r.Value1.XAdvance

    def line(d, x, y, text, size):  # Pillow's basic layout ignores GPOS, so apply kerning by hand
        f, prev = ImageFont.truetype(a.font, size), None
        for ch in text:
            g = cmap.get(ord(ch), 'space')
            if prev:
                x += kern.get((prev, g), 0) * size / 1000
            d.text((x, y), ch, font=f, fill=0)
            x += hmtx[g][0] * size / 1000
            prev = g

    chars = [chr(c) for c in sorted(cmap) if c > 32 and c != 160]
    PW, cell = 2000, 110
    cols = PW // cell
    rows = -(-len(chars) // cols)
    im = Image.new('L', (PW, 60 + rows * cell + 110 * (len(PROOF_LINES) + 1) + 60), 255)
    d, small = ImageDraw.Draw(im), ui_font(18)
    glyph_font = ImageFont.truetype(a.font, 72)
    for i, ch in enumerate(chars):
        x, y = 20 + i % cols * cell, 40 + i // cols * cell
        d.text((x, y), ch, font=small, fill=150)
        d.text((x + 20, y + 10), ch, font=glyph_font, fill=0)
    y = 60 + rows * cell
    for text in [PAIRS] + PROOF_LINES:
        line(d, 40, y, text, 64)
        y += 110
    im.save(a.out)
    missing = sorted({c for c in PAIRS + ''.join(PROOF_LINES) if c != ' ' and ord(c) not in cmap})
    print('wrote', a.out, '| not in the font:', ''.join(missing) or 'none')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    t = sub.add_parser('template', help='print a sheet with a box per character')
    t.add_argument('--out', required=True, help='work folder; template.json there records every sheet')
    t.add_argument('--chars', default=DEFAULT_CHARS, help='characters to include (default: printable ASCII)')
    t.add_argument('--add', default='', help='extra characters on top of --chars, e.g. "åäöÅÄÖ"')
    e = sub.add_parser('extract', help='cut each letter out of photos of filled-in sheets')
    e.add_argument('template')
    e.add_argument('photos', nargs='+')
    e.add_argument('--pen', default='blue', help='pen colour: blue, black, red, green (default blue)')
    e.add_argument('--out', required=True, help='glyph folder, one per weight; later photos replace earlier ones')
    b = sub.add_parser('build', help='trace the glyphs into an .otf')
    b.add_argument('glyphs')
    b.add_argument('--name', required=True)
    b.add_argument('--style', default='Regular', help='Regular or Bold')
    b.add_argument('--sidebearing', type=int, default=45, help='space on each side of a letter, font units')
    b.add_argument('--out', required=True)
    r = sub.add_parser('proof', help='render every glyph and tricky pairs')
    r.add_argument('font')
    r.add_argument('out', help='.pdf, .jpg or .png')
    a = p.parse_args()
    {'template': cmd_template, 'extract': cmd_extract, 'build': cmd_build, 'proof': cmd_proof}[a.cmd](a)


if __name__ == '__main__':
    main()
