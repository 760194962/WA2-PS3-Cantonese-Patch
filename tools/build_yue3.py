#!/usr/bin/env python3
"""WHITE ALBUM2 PS3 (BLJM60571 v1.00) Cantonese patch builder.
Outputs EBOOT.elf (decrypted, patched) + 02309.elzma/02309.size (font atlas for data.dar)."""
import sys, os, struct, re, subprocess, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths
import numpy as np
from common import *
from glyph import render_cell
import wa2_eboot3 as w

OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
os.makedirs(OUT, exist_ok=True)
GLYPH_SIZE = int(os.environ.get("GLYPH_SIZE", "27"))
elf = bytearray(open(ELF, "rb").read())
COLS, CELL = 51, 40

# ---------------- elzma (no end marker, like the original tools) ----------------
LZENC = paths.LZENC
def lzma_block(raw):
    # raw LZMA stream WITHOUT end marker (the game's decoder rejects EOS), dict 2^14, lc3 lp0 pb2
    if not os.path.exists(LZENC):
        import pylzma   # fallback: pip install pylzma
        return pylzma.compress(raw, dictionary=14, fastBytes=273, literalContextBits=3,
                               literalPosBits=0, posBits=2, algorithm=1, eos=0)[5:]
    with tempfile.TemporaryDirectory() as td:
        a, b = os.path.join(td, "i"), os.path.join(td, "o")
        open(a, "wb").write(raw); subprocess.run([LZENC, a, b], check=True)
        return open(b, "rb").read()
def elzma_compress(data):
    out = bytearray(); pos = 0
    while pos < len(data):
        blk = data[pos:pos + 0x10000]; pos += len(blk)
        dst = lzma_block(blk)
        rec = struct.pack("<II", len(blk), len(dst)) + bytes.fromhex("5d00400000000000") + dst
        rec += b"\0" * ((-len(rec)) % 16)
        out += rec
    return bytes(out)

# ---------------- font table ----------------
tb = font_table(elf)
code_of = {}
for c in tb:
    if c >> 8 >= 0x81:
        ch = code2char(c)
        if ch and len(ch) == 1: code_of.setdefault(ch, c)

# ---------------- script mapping (full IC from alignment) ----------------
import pickle
Gm,TMAP,UNM,DIV=pickle.load(open(paths.MAP_PKL,"rb"))
from scr import lines as scr_lines, load as scr_load
NORM = {"〜": "～", "·": "・", "‧": "・", " ": "　", ",": "，", "!": "！", "?": "？", "(": "（", ")": "）",
        ":": "：", ";": "；", "~": "～", "-": "－", "&": "＆", "/": "／", "'": "’", '"': "”",
        "%": "％", ".": "．", "=": "＝", "_": "＿", "—": "―", "︰": "：", "﹐": "，"}
ASCII_OK = {chr(c >> 8) for c in tb if (c & 0xFF) == 0x20 and 0x30 <= (c >> 8) < 0x7B and chr(c >> 8).isalnum()}
def norm_char(ch):
    if ch in ASCII_OK: return ch
    ch = NORM.get(ch, ch)
    if "0" <= ch <= "9" or "A" <= ch <= "Z" or "a" <= ch <= "z":
        ch = chr(ord(ch) + 0xFEE0)
    return ch
def clean(t):
    ls = [l.strip("\u3000 ") if False else l for l in t.split("\n")]
    ls = [l for l in ls if l.strip(" \u3000")]
    return "\n".join(ls)
# translator's "（…）" notes that correspond to ruby (<Rbase|ruby>) in the Japanese script
RUBY_FIX = [("呢一度（機場）", "<R機場|呢一度>"), ("我哋（欖球部）", "<R欖球部|我哋>"),
            ("高三辛班（音樂部）", "<R高三辛班|音樂部>"), ("撚(彈)", "<R彈|撚>")]
plans = []    # (name, fields(bytes), {field_idx: text})
for name in sorted(TMAP):
    tm = TMAP[name]
    orig = open(SCR + name + ".txt", "rb").read()
    fields = orig.split(b",")
    idxs = [i for i, _ in scr_lines(name)]
    pos_ = {i: k for k, i in enumerate(idxs)}
    m = {}; done = set()
    for i in idxs:
        if i not in tm or i in done: continue
        jp = fields[i]
        if jp.endswith(b"\\k\\n"):
            k = pos_[i]
            if k + 1 >= len(idxs) or idxs[k + 1] not in tm: continue
            nx = idxs[k + 1]
            ta = clean(tm[i]).split("\n"); tbb = clean(tm[nx]).split("\n")
            rest = tbb[len(ta):] if len(tbb) > len(ta) else tbb[-1:]
            m[i] = "\n".join(ta).replace("\n", "\\n") + "\\k\\n"
            m[nx] = "\n".join(rest).replace("\n", "\\n")
            done.add(nx)
        else:
            m[i] = clean(tm[i]).replace("\n", "\\n")
    for i in list(m):
        for a_, b_ in RUBY_FIX:
            m[i] = m[i].replace(a_, b_)
    plans.append((name, orig, fields, m))
# speaker names -> Cantonese/HK forms (names follow the subtitle translation, e.g. かずさ=和紗)
SPEAKER_MAP = {
    "かずさ": "和紗", "隣席の女子生徒": "鄰座女同學", "雪菜の母": "雪菜媽媽", "雪菜の父": "雪菜爸爸",
    "諏訪先生": "諏訪老師", "男子生徒１": "男同學１", "男子生徒２": "男同學２", "男子生徒３": "男同學３",
    "女子生徒１": "女同學１", "女子生徒２": "女同學２", "女子生徒３": "女同學３", "担任教師": "班主任",
    "軽音部員": "輕音部部員", "女性教師１": "女老師１", "指導部長": "訓導主任", "車内アナウンス": "車廂廣播",
    "駅アナウンス": "車站廣播", "女性司会": "女司儀", "実行委員": "執行委員", "医師": "醫生", "女性": "女人",
    "演劇部員１": "話劇社社員１", "演劇部員２": "話劇社社員２", "演劇部員３": "話劇社社員３",
    "Ａ組担任": "甲班班主任", "男性教師": "男老師", "携帯アナウンス": "電話錄音", "大学生１": "大學生１",
    "大学生２": "大學生２", "教頭": "副校長", "コンビニ店員": "便利店店員", "ウェイトレス": "女侍應",
}
IC_CHAIN = "1001 1002 1003 1004 1005 1006 1007 1008 1008_020 1008_030 1008_031 1008_040 1008_050 1009 1009_020 1009_030 1010 1010_020 1010_030 1010_040 1010_050 1010_060 1010_070 1011 1011_020 1011_030 1012 1012_020 1012_030 1012_030_2 1013".split()
have = {p_[0] for p_ in plans}
for name in IC_CHAIN:
    if name not in have:
        orig = open(SCR + name + ".txt", "rb").read()
        plans.append((name, orig, orig.split(b","), {}))
for name, orig, fields, m in plans:
    for i, f in enumerate(fields):
        if i in m: continue
        k = f.decode("cp932", "replace")
        if k in SPEAKER_MAP: m[i] = SPEAKER_MAP[k]
# lines the Japanese splits over two fields but the subtitle gives as one cue: re-split to follow the Japanese layout
MANUAL = {"1006": {995: "「嗚！\\n", 996: "你咪等我冇咗件事先嚟提番醒我好冇！」"}}
for name, orig, fields, m in plans:
    m.update(MANUAL.get(name, {}))
plans = [p_ for p_ in plans if p_[3]]
plans.sort(key=lambda p_: p_[0])
print("scripts", len(plans), "fields", sum(len(p[3]) for p in plans))

_LAT = re.escape("".join(chr(c) for c in range(0x21, 0x7F) if chr(c) not in "<>|\\"))
# any run of half-width ASCII (letters, digits AND the subtitle's own ASCII punctuation such as
# ".meme", "I...see...", "=3=", "99%", "(彈)") is kept exactly as written and rendered as a Latin strip
RUN_RE = re.compile(r"[%s](?:[ %s]*[%s])?" % (_LAT, _LAT, _LAT))
def tokens(t):
    for part in re.split(r"(\\n|\\k|<R|\||>)", t):
        if part in ("\\n", "\\k", "<R", "|", ">"): yield ("tok", part); continue
        pos = 0
        for mm in RUN_RE.finditer(part):
            for ch in part[pos:mm.start()]: yield ("ch", ch)
            yield ("run", mm.group()); pos = mm.end()
        for ch in part[pos:]: yield ("ch", ch)
need = []
seen_need = set(); RUNS = []
for _, _, _, m in plans:
    for t in m.values():
        for kind, v in tokens(t):
            if kind == "run":
                if v not in RUNS: RUNS.append(v)
                continue
            if kind != "ch": continue
            ch = norm_char(v)
            if ch not in ASCII_OK and ch not in code_of and ch not in seen_need: need.append(ch); seen_need.add(ch)
need.sort()
assert all(ord(c) > 0x80 for c in need), [c for c in need if ord(c) <= 0x80]
new_code = {}; cc = 0xF043
for ch in need:
    while (cc & 0xFF) < 0x40 or (cc & 0xFF) in (0x5C, 0x7F): cc += 1
    if cc > 0xFFFF or (cc >> 8) == 0xFF: raise SystemExit("out of code points")
    new_code[ch] = cc; cc += 1
from glyph import render_strip
STRIP = {}; STRIP_CELLS = []
for run in sorted(RUNS):
    cells = render_strip(run, size=GLYPH_SIZE)
    cs = []
    for cell in cells:
        while (cc & 0xFF) < 0x40 or (cc & 0xFF) in (0x5C, 0x7F): cc += 1
        if (cc >> 8) == 0xFF: raise SystemExit("out of code points")
        cs.append(cc); STRIP_CELLS.append((cc, cell)); cc += 1
    STRIP[run] = cs
print("latin runs:", len(RUNS), "cells:", len(STRIP_CELLS))
print("new glyphs:", len(need))
open(os.path.join(OUT, "new_glyphs.txt"), "w", encoding="utf-8").write("".join(need))
def enc(t):
    out = bytearray()
    for kind, v in tokens(t):
        if kind == "tok": out += v.encode()
        elif kind == "run":
            for c in STRIP[v]: out += struct.pack(">H", c)
        else:
            ch = norm_char(v)
            out += ch.encode() if ch in ASCII_OK else struct.pack(">H", code_of.get(ch) or new_code[ch])
    return bytes(out)

# ---------------- EBOOT layout in the zero padding after segment 0 ----------------
ARR, EMPTY, RES, END = 0x120E00, 0x124000, 0x124100, 0x12F000
assert set(elf[0x120DE8:0x130000]) == {0}
codes = tb + [new_code[c] for c in need] + [c for c, _ in STRIP_CELLS]
NEW_N = len(codes)
assert NEW_N * 2 < EMPTY - ARR
def expand(c):
    b0 = c >> 8
    return c if (0x80 <= b0 <= 0x9F or b0 >= 0xE0) else b0
MODE = os.environ.get("FONTMODE", "static")   # static | plain | static2706
if MODE == "static2706": codes = tb; NEW_N = TBL_N
if MODE != "plain":
    elf[ARR:ARR + NEW_N * 2] = b"".join(struct.pack(">H", expand(c)) for c in codes)
    # glyph count
    assert struct.unpack(">I", elf[0xC988:0xC98C])[0] == 0x38600A92
    elf[0xC98A:0xC98C] = struct.pack(">H", NEW_N)
    # use the static pre-expanded array instead of malloc+fill
    assert elf[0xC9F0] >> 2 == 0x12 and struct.unpack(">I", elf[0xC9F4:0xC9F8])[0] == 0x60000000
    av = ARR + 0x10000
    elf[0xC9F0:0xC9F8] = struct.pack(">II", 0x3C600000 | (av >> 16), 0x60630000 | (av & 0xFFFF))
    assert elf[0xCA04:0xCA0C] == bytes.fromhex("3C6000113063E3F0")
    ev_ = EMPTY + 0x10000; assert ev_ & 0x8000 == 0
    elf[0xCA04:0xCA0C] = struct.pack(">II", 0x3C600000 | (ev_ >> 16), 0x30630000 | (ev_ & 0xFFFF))

# scripts -> appended as a new PT_LOAD segment (VA 0x1200000)
NEWVA = 0x1209A00   # first 0x100-aligned address after .bss (ends 0x12099F0)
entries = {e[1]: e for e in w.entries(bytes(elf))}
blob = bytearray()
for name, orig, fields, m in plans:
    f2 = list(fields)
    for i, t in m.items(): f2[i] = enc(t)
    newtxt = b",".join(f2)
    assert len(f2) == len(fields)
    open(os.path.join(OUT, name + ".txt.bin"), "wb").write(newtxt)
    comp = elzma_compress(newtxt)
    assert w.elzma_decompress(comp, len(newtxt)) == newtxt
    off = len(blob); blob += comp; blob += b"\0" * ((-len(blob)) % 256)
    e = entries[name + ".txt"]
    name_off = struct.unpack(">I", elf[e[0]:e[0] + 4])[0]
    struct.pack_into(">4I", elf, e[0], name_off, NEWVA + off, len(newtxt), len(comp))
    print("%s.txt: %d -> %d bytes (orig %d)" % (name, len(newtxt), len(comp), len(orig)))
print("script blob %d bytes" % len(blob))
# segment 0 only needs to cover the static glyph tables
assert struct.unpack(">I", elf[0x64:0x68])[0] == 0x120DE8
SEG0 = 0x124100
elf[0x64:0x68] = struct.pack(">I", SEG0); elf[0x6C:0x70] = struct.pack(">I", SEG0)
# extend the data segment (#1) past the end of .bss and put the scripts there:
# PS3 lv2 refused an extra PT_LOAD (80010001), so keep the original 2-segment layout.
ph1 = 0x40 + 1 * 56
t_, fl_, off1, va1, pa_, fs1, ms1, al_ = struct.unpack(">IIQQQQQQ", elf[ph1:ph1 + 56])
assert (off1, va1, fs1, ms1) == (0x130000, 0x140000, 0x5717dc, 0x10c99f0)
SEGEND = off1 + fs1                      # 0x6a17dc: non-loaded sections + shdrs follow
tail = bytes(elf[SEGEND:])
blob_off = off1 + (NEWVA - va1)
newfs = (NEWVA - va1) + len(blob)
body = elf[:SEGEND] + b"\0" * (blob_off - SEGEND) + blob
pad = (-len(body)) % 16; body += b"\0" * pad
delta = len(body) - SEGEND
elf = bytearray(body + tail)
struct.pack_into(">QQ", elf, ph1 + 32, newfs, newfs)            # p_filesz, p_memsz
for k in (2, 3, 4):                                              # empty LOADs point at segment end
    struct.pack_into(">Q", elf, 0x40 + k * 56 + 8, SEGEND + delta)
shoff = struct.unpack(">Q", elf[0x28:0x30])[0] + delta
struct.pack_into(">Q", elf, 0x28, shoff)
for k in range(struct.unpack(">H", elf[0x3c:0x3e])[0]):
    o = shoff + k * 64
    ty = struct.unpack(">I", elf[o + 4:o + 8])[0]; so = struct.unpack(">Q", elf[o + 24:o + 32])[0]
    if ty != 8 and so >= SEGEND: struct.pack_into(">Q", elf, o + 24, so + delta)
open(os.path.join(OUT, "EBOOT.elf"), "wb").write(elf)

# ---------------- font atlas (data.dar entry 2309) ----------------
pk = open(paths.FONT_PKG, "rb").read()
n = struct.unpack("<I", pk[:4])[0]
ents = [struct.unpack("<LL", pk[0x10 + 16*i:0x18 + 16*i]) for i in range(n)]
t0 = bytearray(pk[ents[0][0]:ents[0][0] + ents[0][1]])
W0, H0 = struct.unpack(">HH", t0[0x20:0x24]); assert (W0, H0) == (2040, 2160)
H1 = max(H0, (NEW_N + COLS - 1) // COLS * CELL)
if os.environ.get("MAXH"): H1 = int(os.environ["MAXH"])
assert H1 <= 4096
img = np.frombuffer(bytes(t0[0x80:]), dtype=">u2").reshape(H0, 2040).astype(np.uint16)
img = np.concatenate([img, np.full((H1 - H0, 2040), (5 << 8) | (8 << 4) | 14, np.uint16)], 0)
def put(slot, ch):
    r, c = divmod(slot, COLS)
    if (r + 1) * CELL > H1: return
    img[r*CELL:(r+1)*CELL, c*CELL:(c+1)*CELL] = render_cell(ch, size=GLYPH_SIZE, cx=19.5, weight="Medium")
nre = 0
for i, c in enumerate(tb):
    ch = code2char(c) if c >> 8 >= 0x81 else None
    if ch and len(ch) == 1 and (0x3400 <= ord(ch) <= 0x9FFF or 0xF900 <= ord(ch) <= 0xFAFF):
        put(i, ch); nre += 1
for k, ch in enumerate(need): put(TBL_N + k, ch)
for k, (_, cell) in enumerate(STRIP_CELLS):
    r_, c_ = divmod(TBL_N + len(need) + k, COLS)
    cell = cell.copy()
    # the engine centres each glyph's ink box inside its cell; give strip cells a full-width
    # ink box with two almost transparent pixels so the pieces line up seamlessly
    dot = (1 << 12) | (2 << 8) | (3 << 4) | 3
    img[r_*CELL:(r_+1)*CELL, c_*CELL:(c_+1)*CELL] = cell
import glyph as _g
_yp_cmap = _g._cmap("Medium")
# Latin letters / digits in the round font too (half-width slots + full-width Ａ-ｚ０-９)
for i, c in enumerate(tb):
    r_, c_ = divmod(i, COLS)
    if (c & 0xFF) == 0x20 and 0x21 <= (c >> 8) < 0x7F:
        img[r_*CELL:(r_+1)*CELL, c_*CELL:(c_+1)*CELL] = (render_cell(chr(c >> 8), size=24, cx=12, weight="Medium", half=True, maxw=19) if chr(c >> 8) in "WMmw" else render_cell(chr(c >> 8), size=27, cx=12, weight="Medium", half=True, maxw=15))
    elif 0x8141 <= c <= 0x81FC:                      # full-width punctuation / symbols
        ch = code2char(c)
        if ch and len(ch) == 1 and ord(ch) in _yp_cmap:
            img[r_*CELL:(r_+1)*CELL, c_*CELL:(c_+1)*CELL] = render_cell(ch, size=GLYPH_SIZE, cx=19.5, weight="Medium")
    elif 0x824F <= c <= 0x829A:
        ch = code2char(c)
        if ch and ch.isalnum():
            ch = chr(ord(ch) - 0xFEE0)       # YuPearl's own full-width Ｕ is a malformed square-bottomed glyph; draw the ASCII letter
            img[r_*CELL:(r_+1)*CELL, c_*CELL:(c_+1)*CELL] = render_cell(ch, size=GLYPH_SIZE + 1, cx=19.5, weight="Medium", maxw=34)
print("redrawn %d original ideographs, %d new glyphs, atlas height %d" % (nre, len(need), H1))
t0n = bytearray(t0[:0x80]) + img.astype(">u2").tobytes()
struct.pack_into(">I", t0n, 4, len(t0n) - 0x80); struct.pack_into(">I", t0n, 0x14, len(t0n) - 0x80)
struct.pack_into(">H", t0n, 0x22, H1)
parts = [bytes(t0n)] + [pk[o:o+s] for o, s in ents[1:]]
body = bytearray(pk[:0x40]); offs = []; p = 0x40
for part in parts:
    offs.append(p); p = (p + len(part) + 0x3F) // 0x40 * 0x40
for i, (o, part) in enumerate(zip(offs, parts)):
    struct.pack_into("<LL", body, 0x10 + 16*i, o, len(part))
for o, part in zip(offs, parts):
    body += b"\0" * (o - len(body)); body += part
open(os.path.join(OUT, "02309.elzma"), "wb").write(elzma_compress(bytes(body)))
open(os.path.join(OUT, "02309.size"), "w").write("%d\n" % len(body))
from PIL import Image
r0 = max(0, (TBL_N // COLS) * CELL)
sub = img[r0:]
rgb = np.stack([((sub >> 8) & 15) * 17, ((sub >> 4) & 15) * 17, (sub & 15) * 17], -1).astype(float)
al = (((sub >> 12) & 15) * 17)[..., None] / 255.0
Image.fromarray((rgb * al + 80 * (1 - al)).astype(np.uint8)).save(os.path.join(OUT, "new_glyphs_preview.png"))
print("done")
