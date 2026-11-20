"""End-to-end check on a fake photo: python test_roundtrip.py"""
import json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import freehandfont as ff

HERE = os.path.dirname(os.path.abspath(__file__))


def run(*args):
    subprocess.run([sys.executable, os.path.join(HERE, 'freehandfont.py'), *args], check=True)


def fake_photo(chars, page_id, path, ink=(30, 50, 160)):
    """Fill the sheet in pen (blue by default), then photograph it upside down, tilted, on a dark desk, in uneven light."""
    page = ff.draw_page(chars, page_id)
    d, pen = ImageDraw.Draw(page), ff.ui_font(110)
    for i, ch in enumerate(chars):
        x, y = ff.cell_xy(i)
        d.text((x + ff.CELL_W / 2, y + ff.LABEL_H + ff.BASE), ch, font=pen, fill=ink, anchor='ms')
    page = page.rotate(180).filter(ImageFilter.GaussianBlur(1.2))
    desk = Image.new('RGB', (3000, 4000), (60, 50, 45))
    w, h = 2400, 3100  # page size in the photo, then a mild perspective tilt
    quad = np.array([[300, 380], [300 + w, 300], [2950 - 80, 300 + h + 120], [260, 300 + h]], float)
    # warp page into the quad on the desk: for each desk pixel, find the page pixel
    Hq = ff.homography(quad, [(0, 0), (ff.W, 0), (ff.W, ff.H), (0, ff.H)])
    warped = page.transform(desk.size, Image.PERSPECTIVE, (Hq / Hq[2, 2]).ravel()[:8], Image.BICUBIC, fillcolor=(60, 50, 45))
    mask = Image.new('L', (ff.W, ff.H), 255).transform(desk.size, Image.PERSPECTIVE, (Hq / Hq[2, 2]).ravel()[:8])
    desk.paste(warped, (0, 0), mask)
    shade = np.linspace(1.0, 0.75, desk.size[0])[None, :, None]  # light falls off to the right
    Image.fromarray((np.asarray(desk) * shade).astype(np.uint8)).save(path, quality=88)


def main():
    work = tempfile.mkdtemp()
    run('template', '--out', work, '--add', 'åäöÅÄÖ')
    pages = json.load(open(os.path.join(work, 'template.json'), encoding='utf-8'))['pages']
    chars = pages['0']
    fake_photo(chars, 0, os.path.join(work, 'photo.jpg'))
    run('extract', os.path.join(work, 'template.json'), os.path.join(work, 'photo.jpg'), '--out', os.path.join(work, 'regular'))
    glyphs = json.load(open(os.path.join(work, 'regular', 'glyphs.json'), encoding='utf-8'))['glyphs']
    assert set(glyphs) == set(chars), f'missing {set(chars) - set(glyphs)}'
    # 'x' sits on the baseline: its lowest ink row should be within a few px of it
    x = np.asarray(Image.open(os.path.join(work, 'regular', glyphs['x']['file']))) < 128
    assert abs(np.nonzero(x)[0].max() - (ff.BASE - ff.INNER)) <= 6

    # retry sheet: only 'G', rewritten; extract merges it into the same folder
    run('template', '--out', work, '--chars', 'G')
    fake_photo('G', 1, os.path.join(work, 'retry.jpg'), ink=(25, 25, 25))  # black pen
    run('extract', os.path.join(work, 'template.json'), os.path.join(work, 'retry.jpg'), '--pen', 'black', '--out', os.path.join(work, 'regular'))
    glyphs = json.load(open(os.path.join(work, 'regular', 'glyphs.json'), encoding='utf-8'))['glyphs']
    assert glyphs['G']['photo'] == 'retry.jpg' and len(glyphs) == len(chars)

    run('build', os.path.join(work, 'regular'), '--name', 'Test Hand', '--out', os.path.join(work, 'out'))
    font = os.path.join(work, 'out', 'TestHand-Regular.otf')
    from fontTools.ttLib import TTFont
    tt = TTFont(font)
    assert all(ord(c) in tt.getBestCmap() for c in chars)
    run('proof', font, os.path.join(work, 'out', 'proof.jpg'))

    # freehand: rows on ruled paper, no template, a scribble to skip, photo taken sideways and a little tilted
    rows = ['ABCDEFGH', 'abcdefgh', 'ij!?:%"']
    paper = Image.new('RGB', (2400, 1500), (238, 236, 230))
    d, pen = ImageDraw.Draw(paper), ff.ui_font(150)
    for y in range(120, 1500, 200):
        d.line([0, y, 2400, y], fill=(150, 160, 175), width=4)
    for r, text in enumerate(rows):
        for i, ch in enumerate(text + '#'):
            xy = (150 + i * 240, 320 + r * 400)
            if ch == '#':
                d.ellipse([xy[0], xy[1] - 110, xy[0] + 110, xy[1]], fill=(30, 50, 160))  # scribble
            else:
                d.text(xy, ch, font=pen, fill=(30, 50, 160), anchor='ls')
    tilted = paper.rotate(2, fillcolor=(238, 236, 230)).crop((60, 60, 2340, 1440))  # close-up: lines run off the frame
    tilted.rotate(90, expand=True).save(os.path.join(work, 'free.jpg'))
    open(os.path.join(work, 'rows.txt'), 'w', encoding='utf-8').write('\n'.join(t + ff.SKIP for t in rows))
    out = os.path.join(work, 'free')
    run('cut', os.path.join(work, 'free.jpg'), '--rotate', '90', '--rows', os.path.join(work, 'rows.txt'), '--out', out)
    glyphs = json.load(open(os.path.join(out, 'glyphs.json'), encoding='utf-8'))['glyphs']
    assert set(glyphs) == set(''.join(rows)), f'got {"".join(glyphs)}'
    run('build', out, '--name', 'Free Hand', '--out', os.path.join(work, 'out'))
    print('ok', work)


if __name__ == '__main__':
    main()
