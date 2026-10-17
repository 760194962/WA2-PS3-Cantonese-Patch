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
# The ASCII (half-width) block is the first slots of the table. The game has no slot for a few ASCII characters the
# subtitles use (Q : -); reuse three slots the game never needs ({ } [) so every ASCII character is drawn as itself.
_half = [i for i, c in enumerate(tb) if (c & 0xFF) == 0x20 and (c >> 8) < 0x80]
assert _half == list(range(_half[0], _half[0] + len(_half)))
_blk = {chr(tb[i] >> 8) for i in _half} - set("{}[") | set("Q:-")
assert len(_blk) == len(_half)
tb[_half[0]:_half[-1] + 1] = [(ord(ch) << 8) | 0x20 for ch in sorted(_blk)]
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
LATIN_STRIPS = os.environ.get("LATIN_STRIPS") == "1"    # 1: whole English words as proportional strips; default: one glyph per letter
ASCII_OK = {chr(c >> 8) for c in tb if (c & 0xFF) == 0x20 and 0x30 <= (c >> 8) < 0x7B and chr(c >> 8).isalnum()}
if not LATIN_STRIPS: ASCII_OK |= {chr(c >> 8) for c in tb if (c & 0xFF) == 0x20 and 0x20 <= (c >> 8) < 0x7F and chr(c >> 8) not in ",<>|\\"}
PROP = not LATIN_STRIPS     # proportional half-width glyphs: patch the engine's draw routine to use a per-glyph advance table
PROP_CELLS = {}; ADV = bytearray([14]) * 256    # advance in atlas px (at the engine's 28px reference), indexed by byte value
if PROP:
    from glyph import render_prop
    for c_ in tb:
        if (c_ & 0xFF) == 0x20 and 0x20 <= (c_ >> 8) < 0x7F:
            cell_, adv_ = render_prop(chr(c_ >> 8)); PROP_CELLS[c_] = cell_; ADV[c_ >> 8] = max(1, min(255, int(round(adv_))))
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
    "春希＆かずさ": "春希＆和紗", "かずさ＆春希": "和紗＆春希", "かずさ・雪菜": "和紗・雪菜",
    "雪菜の母＆孝宏": "雪菜媽媽＆孝宏", "ラジオの天気予報": "電台天氣報告",
}
IC_CHAIN = "1001 1002 1003 1004 1005 1006 1007 1008 1008_020 1008_030 1008_031 1008_040 1008_050 1009 1009_020 1009_030 1010 1010_020 1010_030 1010_040 1010_050 1010_060 1010_070 1011 1011_020 1011_030 1012 1012_020 1012_030 1012_030_2 1013".split()
have = {p_[0] for p_ in plans}
for name in IC_CHAIN:
    if name not in have:
        orig = open(SCR + name + ".txt", "rb").read()
        plans.append((name, orig, orig.split(b","), {}))
# side story 「雪が解け、そして雪が降るまで」 (digital novel, scripts 5000-5004): whole pages from tools/novel_map.py
NOVEL_PKL = os.path.join(paths.WORK, "novel_map.pkl")
NOVEL = pickle.load(open(NOVEL_PKL, "rb")) if os.path.exists(NOVEL_PKL) and os.environ.get("NO_NOVEL") != "1" else {}
for name, pages_ in sorted(NOVEL.items()):
    orig = open(SCR + name + ".txt", "rb").read()
    plans.append((name, orig, orig.split(b","), dict(pages_)))
print("novel scripts:", len(NOVEL), "pages:", sum(map(len, NOVEL.values())))
for name, orig, fields, m in plans:
    if name in NOVEL: continue
    for i, f in enumerate(fields):
        if i in m: continue
        k = f.decode("cp932", "replace")
        if k in SPEAKER_MAP: m[i] = SPEAKER_MAP[k]
# lines the Japanese splits over two fields but the subtitle gives as one cue: re-split to follow the Japanese layout
MANUAL = {"1006": {995: "「嗚！\\n", 996: "你咪等我冇咗件事先嚟提番醒我好冇！」",
                   # re-broken by hand: wrapping the subtitle's own breaks would need 5 lines
                   1902: "我本身琴晚已經夠哂崩潰，\\n而且我仲未抖完哂啲矇忪，隻眼好花。\\n不過我唔可以違抗師命，所以我哋好早就出嚟一齊練習，\\n仲早過我哋練第一支歌嗰陣時。"},
          # the automatic alignment misses these (it depends on the t2s converter in use); pin them to the subtitle text
          # the aligner took the translator's note shown at the same time as the line
          "1004": {454: "「況且呢…\\n開講都有話『少時不柒頭，長大做妓者』啦係咪先？」"},
          "1010_040": {39: "「噫～～～！」"},
          # missed by both alignments (few or no kanji to match on); checked against the video by hand
          "1010_050": {5: "「哎吔！？」", 6: "而我接落嚟就感覺到\\n塊面有一下痛痛地嘅衝擊。"},
          "1012_030": {660: "「我永遠…都係屬於妳嘅」"},
          # Io and Setsuna on the eve of graduation: also only in the 2nd-run subtitles
          "1012_020": {89: "「雪菜呀，真係純粹係你諗多咗㗎咋」", 91: "「真嘅話…都依然係噉有噉傷心啫」",
                       93: "「而家個年代仲邊有女仔會傻到\\n因為畀人飛而走去咁遠避開人㗎…邊可能痴線到噉㗎？\\n絕對冇可能㗎」",
                       95: "「唔應該攪成噉㗎………冇理由㗎」"},
          # Kazusa alone after the hot-spring trip: only in the 2nd-run subtitles, which the alignment missed
          "1010_060": {5: "「嗚嗄…嗄、嗄嗄、嗄嗄…」", 7: "「終於，返到喇…」", 9: "「哈、哈哈…」",
                       11: "「嗯哈哈哈…呀哈哈哈…唏！」", 13: "「………」", 15: "「嗄唏！」", 17: "「嗚噫…嗄、嗚嗚…」",
                       19: "「嗚！嗚呀、呀…嗚呀呀嗄…！\\n呀呀、呀…呀呀呀呀呀嗄！」",
                       21: "「嗚呀吓呀呀呀呀呀呀呀呀呀呀呀～！\\n唏！咿呀吓吓吓呀呀呀呀呀呀呀呀呀！」",
                       23: "「呀呀～！嗄…唏！呀吓呀呀呀～！哇呀呀！唏！\\n哇呀吓吓吓呀呀吓吓呀呀吓吓呀呀呀呀～～～！！！」"},
          "1011": {552: "「我合格…？」"},
          "1011_020": {5: "「啲人成日話『10歲就神童，\\n15歲就秀才，一過咗20歲就只係一個普通人』…」"},
          "1012": {225: "嘻嘻！」"}}      # 224 ends with \k\n; the subtitle's closing words belong here
# lines recovered through the PC script (tools/pc_bridge.py), only where nothing else filled the field
BRIDGE_PKL = os.path.join(paths.WORK, "pc_bridge.pkl")
BRIDGE = pickle.load(open(BRIDGE_PKL, "rb")) if os.path.exists(BRIDGE_PKL) else {}
nb = 0
for name, orig, fields, m in plans:
    for i, t in BRIDGE.get(name, {}).items():
        if i not in m: m[i] = t.replace("\n", "\\n"); nb += 1
print("PC-bridge lines:", nb)
for name, orig, fields, m in plans:
    m.update(MANUAL.get(name, {}))
# The window fits 27 full-width cells per line (the Japanese never goes wider); the engine char-wraps anything longer,
# which leaves e.g. a lone "，" on the next line. Re-break such fields: keep the subtitle's line count when the text
# fits (like the Japanese, a line may then break mid-phrase), otherwise add lines up to MAXL.
WRAP, MAXL = 27, 4
_BRK = set("，。！？、…）」』》～︰：；")      # may end a line, must not start one
_OPEN = set("「『（《")                        # must not end a line
_PART = set("㗎嘅啦呀喎囉嘞咩喇吖噃嘛啫咋㖞嗎")    # Cantonese sentence-final particles: never start a line
_UNIT = re.compile(r"<R[^>]*>|<[^>]*>|\\[nk]|.")
def _uw(u):
    if u.startswith("<R"): return sum(_uw(c) for c in u[2:u.index("|")])
    if u.startswith("<") or u.startswith("\\"): return 0
    if ord(u) < 0x80: return (ADV[ord(u)] / 28) if not LATIN_STRIPS else 0.5
    return 1
def _wrap(line):
    out = []
    us = _UNIT.findall(line)
    while sum(map(_uw, us)) > WRAP + 0.01:
        acc = 0; best = None
        for k, u in enumerate(us):
            acc += _uw(u)
            if acc > WRAP + 0.01: break
            if u in _BRK and k + 1 < len(us) and acc >= WRAP / 2: best = k + 1
        if best is None:                                   # no punctuation: hard break, never start a line with punctuation
            best = k
            while best > 1 and us[best] in _BRK: best -= 1
        out.append("".join(us[:best])); us = us[best:]
    out.append("".join(us))
    return "\\n".join(out)
def _reflow(t):
    tail = ""
    if t.endswith("\\k\\n"): t, tail = t[:-4], "\\k\\n"
    if "\\k" in t: return None                              # click-waits inside: leave to the per-line fallback
    us, orig = [], set()
    for u in _UNIT.findall(t):
        if u == "\\n": orig.add(len(us))
        else: us.append(u)
    N = len(us); wid = [0.0]
    for u in us: wid.append(wid[-1] + _uw(u))
    def ok(p, mid):                                        # may a line start at us[p]?
        a, b = us[p - 1], us[p]
        if b in _BRK or b in _PART or a in _OPEN: return False
        if not mid and a not in _BRK: return False
        return not (len(a) == len(b) == 1 and a.isascii() and b.isascii() and a.isalnum() and b.isalnum())
    def cost(p): return (0 if us[p - 1] in _BRK else 3) - (1 if p in orig else 0)
    # fewest lines first (starting from the subtitle's own count); for each, punctuation-only breaks before mid-phrase ones
    for L, mid in [(L_, m_) for L_ in range(t.count("\\n") + 1, MAXL + 1) for m_ in (False, True)]:
        dp = {0: (0.0, [])}                                # line start -> (cost, breaks)
        for _ in range(L - 1):
            nd = {}
            for s, (c, br) in dp.items():
                for p in range(s + 1, N):
                    if wid[p] - wid[s] > WRAP + 0.01: break
                    if not ok(p, mid): continue
                    cc = c + cost(p) + (WRAP - (wid[p] - wid[s])) * 0.01
                    if p not in nd or cc < nd[p][0]: nd[p] = (cc, br + [p])
            dp = nd
        fits = [(c, br) for s, (c, br) in dp.items() if wid[N] - wid[s] <= WRAP + 0.01]
        if fits:
            cuts = [0] + min(fits)[1] + [N]
            return "\\n".join("".join(us[a:b]) for a, b in zip(cuts, cuts[1:])) + tail
    return None
WRAPPED = []
for name, orig, fields, m in plans:
    for i, t in list(m.items()):
        if os.environ.get("NOWRAP") == "1" or name in NOVEL: break   # novel pages are wrapped by the engine
        if all(sum(map(_uw, _UNIT.findall(ln))) <= WRAP + 0.01 for ln in t.split("\\n")): continue
        nt = _reflow(t) or "\\n".join(_wrap(ln) for ln in t.split("\\n"))
        m[i] = nt; WRAPPED.append((name, i, t.count("\\n") + 1, nt.count("\\n") + 1))
print("re-broke %d over-wide fields: %d kept their line count, %d got more lines; over %d lines: %s" % (
    len(WRAPPED), sum(a == b for _, _, a, b in WRAPPED), sum(b > a for _, _, a, b in WRAPPED), MAXL,
    [x[:2] for x in WRAPPED if x[3] > MAXL]))
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
        for mm in (RUN_RE.finditer(part) if LATIN_STRIPS else ()):
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

# ---- proportional 1-byte glyphs: the draw routine (0x263c) advances size/2 for a 1-byte code; replace that with
#      size * ADV[byte] / 28 (ADV = glyph advance in atlas px). Table + trampoline live in the padding after the code array.
if PROP:
    TBL, CAVE = 0x123000, 0x123100
    assert NEW_N * 2 + ARR < TBL and set(elf[TBL:CAVE + 0x40]) == {0}
    assert struct.unpack(">II", elf[0x274c:0x2754]) == (0x7FF60E70, 0x7ED60194), "draw routine differs"   # srawi r22,r31,1 ; addze r22,r22
    def I(*w): return b"".join(struct.pack(">I", x) for x in w)
    VA = lambda o: o + 0x10000
    elf[TBL:TBL + 256] = bytes(ADV)
    cave = [(15 << 26) | (22 << 21) | (VA(TBL) >> 16),                     # lis    r22, hi(tbl)
            (14 << 26) | (22 << 21) | (22 << 16) | (VA(TBL) & 0xFFFF),     # addi   r22, r22, lo(tbl)   (lo < 0x8000)
            (31 << 26) | (22 << 21) | (22 << 16) | (4 << 11) | (87 << 1),  # lbzx   r22, r22, r4        r4 = the byte
            (31 << 26) | (22 << 21) | (22 << 16) | (31 << 11) | (235 << 1),# mullw  r22, r22, r31       r31 = size
            (14 << 26) | (22 << 21) | (22 << 16) | 14,                     # addi   r22, r22, 14
            (14 << 26) | (0 << 21) | (0 << 16) | 28,                       # li     r0, 28
            (31 << 26) | (22 << 21) | (22 << 16) | (0 << 11) | (491 << 1)] # divw   r22, r22, r0
    assert VA(TBL) & 0x8000 == 0
    back = 0x2768 - (CAVE + 4 * len(cave))
    cave.append((18 << 26) | (back & 0x03FFFFFC))                         # b      0x2768
    elf[CAVE:CAVE + 4 * len(cave)] = I(*cave)
    elf[0x274c:0x2750] = I((18 << 26) | ((CAVE - 0x274c) & 0x03FFFFFC))  # b      cave
    # dialogue / message-window renderer: after the per-char call (0x41400) the pen moves by (size+1)>>1 for a 1-byte code
    # (0x41404..0x41410, result in r4). Same table, byte = base[idx] (stack slots 0x52c / 0x190), size = 0x1a0(r1).
    CAVE2 = 0x123180
    assert struct.unpack(">4I", elf[0x41404:0x41414]) == (0x808101A0, 0x30840001, 0x7C840E70, 0x7C840194), "dialogue routine differs"
    c2 = [(32 << 26) | (3 << 21) | (1 << 16) | 0x52C,                       # lwz   r3, 0x52c(r1)    string base
          (32 << 26) | (4 << 21) | (1 << 16) | 0x190,                       # lwz   r4, 0x190(r1)    char index
          (31 << 26) | (3 << 21) | (3 << 16) | (4 << 11) | (87 << 1),       # lbzx  r3, r3, r4       the byte
          (15 << 26) | (4 << 21) | (VA(TBL) >> 16),                         # lis   r4, hi(tbl)
          (14 << 26) | (4 << 21) | (4 << 16) | (VA(TBL) & 0xFFFF),          # addi  r4, r4, lo(tbl)
          (31 << 26) | (3 << 21) | (4 << 16) | (3 << 11) | (87 << 1),       # lbzx  r3, r4, r3       advance (atlas px)
          (32 << 26) | (4 << 21) | (1 << 16) | 0x1A0,                       # lwz   r4, 0x1a0(r1)    size
          (31 << 26) | (3 << 21) | (3 << 16) | (4 << 11) | (235 << 1),      # mullw r3, r3, r4
          (14 << 26) | (3 << 21) | (3 << 16) | 14,                          # addi  r3, r3, 14
          (14 << 26) | (0 << 21) | (0 << 16) | 28,                          # li    r0, 28
          (31 << 26) | (4 << 21) | (3 << 16) | (0 << 11) | (491 << 1)]      # divw  r4, r3, r0
    c2.append((18 << 26) | ((0x41414 - (CAVE2 + 4 * len(c2))) & 0x03FFFFFC))   # b 0x41414
    assert set(elf[CAVE2:CAVE2 + 4 * len(c2)]) == {0}
    elf[CAVE2:CAVE2 + 4 * len(c2)] = I(*c2)
    elf[0x41404:0x41408] = I((18 << 26) | ((CAVE2 - 0x41404) & 0x03FFFFFC))   # b cave2
    # ...but 0x41404 only feeds 0x18c(r1). The pen itself (0x184) moves at 0x41480..0x414ac:
    #   pen += (size >> 1) + (spacing 0x4fc >> 1)        -> replace size>>1 (0x41480..0x41488, result in r3)
    CAVE3 = 0x123200
    assert struct.unpack(">3I", elf[0x41480:0x4148c]) == (0x806101A0, 0x7C630E70, 0x7C630194), "dialogue pen code differs"
    c3 = [(32 << 26) | (3 << 21) | (1 << 16) | 0x52C,                       # lwz   r3, 0x52c(r1)    string base
          (32 << 26) | (4 << 21) | (1 << 16) | 0x190,                       # lwz   r4, 0x190(r1)    char index
          (31 << 26) | (3 << 21) | (3 << 16) | (4 << 11) | (87 << 1),       # lbzx  r3, r3, r4       the byte
          (15 << 26) | (4 << 21) | (VA(TBL) >> 16),                         # lis   r4, hi(tbl)
          (14 << 26) | (4 << 21) | (4 << 16) | (VA(TBL) & 0xFFFF),          # addi  r4, r4, lo(tbl)
          (31 << 26) | (3 << 21) | (4 << 16) | (3 << 11) | (87 << 1),       # lbzx  r3, r4, r3       advance (atlas px)
          (32 << 26) | (4 << 21) | (1 << 16) | 0x1A0,                       # lwz   r4, 0x1a0(r1)    size
          (31 << 26) | (3 << 21) | (3 << 16) | (4 << 11) | (235 << 1),      # mullw r3, r3, r4
          (14 << 26) | (3 << 21) | (3 << 16) | 14,                          # addi  r3, r3, 14
          (14 << 26) | (4 << 21) | (0 << 16) | 28,                          # li    r4, 28           (r4 is reloaded at 0x4148c)
          (31 << 26) | (3 << 21) | (3 << 16) | (4 << 11) | (491 << 1)]      # divw  r3, r3, r4
    c3.append((18 << 26) | ((0x4148c - (CAVE3 + 4 * len(c3))) & 0x03FFFFFC))   # b 0x4148c
    assert CAVE3 + 4 * len(c3) < EMPTY and set(elf[CAVE3:CAVE3 + 4 * len(c3)]) == {0}
    elf[CAVE3:CAVE3 + 4 * len(c3)] = I(*c3)
    elf[0x41480:0x41484] = I((18 << 26) | ((CAVE3 - 0x41480) & 0x03FFFFFC))   # b cave3
    # backlog renderer (fn 0x43190, per-char call 0x3f060): a twin of the dialogue code with its own stack slots
    # (index 0x194, size 0x1a4, pen 0x188). Same two spots: 0x45074 (feeds 0x190) and 0x450f0 (the pen).
    def adv_cave(at, dst, tmp, idx, size, back):
        c_ = [(32 << 26) | (dst << 21) | (1 << 16) | 0x52C,                  # lwz   dst, 0x52c(r1)   string base
              (32 << 26) | (tmp << 21) | (1 << 16) | idx,                    # lwz   tmp, idx(r1)     char index
              (31 << 26) | (dst << 21) | (dst << 16) | (tmp << 11) | (87 << 1),   # lbzx dst, dst, tmp  the byte
              (15 << 26) | (tmp << 21) | (VA(TBL) >> 16),                    # lis   tmp, hi(tbl)
              (14 << 26) | (tmp << 21) | (tmp << 16) | (VA(TBL) & 0xFFFF),   # addi  tmp, tmp, lo(tbl)
              (31 << 26) | (dst << 21) | (tmp << 16) | (dst << 11) | (87 << 1),   # lbzx dst, tmp, dst  advance
              (32 << 26) | (tmp << 21) | (1 << 16) | size,                   # lwz   tmp, size(r1)
              (31 << 26) | (dst << 21) | (dst << 16) | (tmp << 11) | (235 << 1),  # mullw dst, dst, tmp
              (14 << 26) | (dst << 21) | (dst << 16) | 14,                   # addi  dst, dst, 14
              (14 << 26) | (tmp << 21) | (0 << 16) | 28,                     # li    tmp, 28
              (31 << 26) | (dst << 21) | (dst << 16) | (tmp << 11) | (491 << 1)]  # divw dst, dst, tmp
        c_.append((18 << 26) | ((back - (at + 4 * len(c_))) & 0x03FFFFFC))
        assert at + 4 * len(c_) < EMPTY and set(elf[at:at + 4 * len(c_)]) == {0}
        elf[at:at + 4 * len(c_)] = I(*c_)
    assert struct.unpack(">4I", elf[0x45074:0x45084]) == (0x808101A4, 0x30840001, 0x7C840E70, 0x7C840194), "backlog routine differs"
    assert struct.unpack(">3I", elf[0x450f0:0x450fc]) == (0x806101A4, 0x7C630E70, 0x7C630194), "backlog pen code differs"
    adv_cave(0x123240, 4, 3, 0x194, 0x1A4, 0x45084)        # r3 is reloaded at 0x45084
    adv_cave(0x123280, 3, 4, 0x194, 0x1A4, 0x450fc)        # r4 is reloaded at 0x450fc
    elf[0x45074:0x45078] = I((18 << 26) | ((0x123240 - 0x45074) & 0x03FFFFFC))
    elf[0x450f0:0x450f4] = I((18 << 26) | ((0x123280 - 0x450f0) & 0x03FFFFFC))

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
    if PROP and c in PROP_CELLS:
        img[r_*CELL:(r_+1)*CELL, c_*CELL:(c_+1)*CELL] = PROP_CELLS[c]
    elif (c & 0xFF) == 0x20 and 0x21 <= (c >> 8) < 0x7F:
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
