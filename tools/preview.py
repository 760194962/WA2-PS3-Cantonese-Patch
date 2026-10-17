"""Approximate in-game preview of translated script lines (glyph shapes + 2:1 full/half-width pitch).
   python tools/preview.py <script> <first_field> [last_field] [out.png]        e.g. 1008_030 120 135
It reads work/build (EBOOT.elf + 02309.elzma), so it shows exactly what build.py produced. The real engine's
blending/shadow/line pitch are not reproduced; placement follows the disassembly of the draw routine (EBOOT 0x263c): cell at pen-5, advance 29 / 14.5."""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import paths, wa2_eboot3 as w
B = os.path.join(paths.WORK, os.environ.get("PREVIEW_BUILD", "build"))
elf = open(os.path.join(B, "EBOOT.elf"), "rb").read()
N = struct.unpack(">H", elf[0xC98A:0xC98C])[0]
arr = struct.unpack(">%dH" % N, elf[0x120E00:0x120E00 + 2 * N])
idx = {c: i for i, c in enumerate(arr)}
pk = w.elzma_decompress(open(os.path.join(B, "02309.elzma"), "rb").read(), int(open(os.path.join(B, "02309.size")).read()))
o, s = struct.unpack("<LL", pk[0x10:0x18]); t = pk[o:o + s]
W, H = struct.unpack(">HH", t[0x20:0x24]); A = np.frombuffer(t[0x80:], ">u2").reshape(H, W)
PATCHED = elf[0x123100:0x123104] == bytes.fromhex('3ec00013')      # proportional-advance patch present
ADV = elf[0x123000:0x123100]
def cell(i):
    r, c = divmod(i, 51); x = A[r*40:(r+1)*40, c*40:(c+1)*40]
    return np.stack([((x >> 8) & 15) * 17, ((x >> 4) & 15) * 17, (x & 15) * 17, ((x >> 12) & 15) * 17], -1).astype(np.float32)
def script(name):
    for _, n, d, u, bs in w.entries(elf):
        if n == name + ".txt": return w.elzma_decompress(elf[d:d + bs], u).split(b",")
    raise SystemExit("no script " + name)
def glyphs(b):                         # -> list of (table index, is_half) ; None = newline
    out = []; i = 0
    while i < len(b):
        if b[i:i+2] == bytes([0x5C, 0x6E]): out.append(None); i += 2; continue     # literal backslash-n
        if b[i:i+2] == bytes([0x5C, 0x6B]): i += 2; continue                       # literal backslash-k
        if b[i:i+2] == b"<R":
            j = b.index(b"|", i); out += glyphs(b[i+2:j]); i = b.index(b">", j) + 1; continue
        c = b[i]
        if c < 0x80: out.append((idx.get(c), c)); i += 1
        else: out.append((idx.get(struct.unpack(">H", b[i:i+2])[0]), None)); i += 2
    return out
def main():
    name, a = sys.argv[1], int(sys.argv[2]); z = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else a
    outp = next((x for x in sys.argv[3:] if x.endswith(".png")), os.path.join(paths.WORK, "preview.png"))
    f = script(name); PITCH, LH = 29, 44
    lines = []
    for k in range(a, z + 1):
        cur = []
        for g in glyphs(f[k]):
            if g is None: lines.append(cur); cur = []
            else: cur.append(g)
        lines.append(cur); lines.append([])             # blank line between fields
    def adv_of(half): return PITCH if half is None else (ADV[half] * PITCH / 28 if PATCHED else PITCH / 2)
    # the window holds 27 full-width cells; like the engine, char-wrap anything past that (no line-start rules)
    COLS = int(os.environ.get("PREVIEW_COLS", "27")); LIMIT = COLS * PITCH; wrapped = []   # 27: dialogue box, 40: novel page
    for ln in lines:
        cur, x = [], 0
        for g in ln:
            if cur and x + adv_of(g[1]) > LIMIT + 0.5: wrapped.append(cur); cur, x = [], 0
            cur.append(g); x += adv_of(g[1])
        wrapped.append(cur)
    lines = wrapped
    img = np.zeros((LH * len(lines) + 20, PITCH * (COLS + 3) + 40, 3), np.float32); img[:] = (58, 88, 106)
    img[:, 20 + LIMIT:20 + LIMIT + 2] = (200, 70, 70)    # right edge of the text area
    for ly, ln in enumerate(lines):
        x = 20
        for gi, half in ln:
            adv = adv_of(half)                          # half = the byte of a 1-byte code
            if gi is not None:
                # engine: 40px cell drawn at pen-5 (EBOOT 0x263c), advance = size (2-byte code) or size/2 (1-byte code)
                cl = cell(gi); x0 = int(round(x - 5)); y0 = 10 + ly * LH
                for yy in range(40):
                    for xx in range(40):
                        if 0 <= x0 + xx < img.shape[1] and cl[yy, xx, 3] > 0:
                            a_ = cl[yy, xx, 3] / 255.0; img[y0 + yy, x0 + xx] = cl[yy, xx, :3] * a_ + img[y0 + yy, x0 + xx] * (1 - a_)
            x += adv
    im = Image.fromarray(img.astype(np.uint8)); im.resize((im.width * 2, im.height * 2), Image.LANCZOS).save(outp); print(outp)
if __name__ == "__main__": main()
