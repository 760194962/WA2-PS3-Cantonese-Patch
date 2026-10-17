"""Side story 「雪が解け、そして雪が降るまで」 (scripts 5000-5004, digital-novel mode) <- ASS "The Snow Melts 01-03".
The novel pages are one field each; a page holds several paragraphs separated by click-waits (\\k). Each subtitle cue
is (almost always) one paragraph, so align cue <-> paragraph and replace the paragraph body, keeping the page layout
(indent, \\k, blank lines). Writes work/novel_map.pkl = {script: {field: new field text}} and work/novel_report.md."""
import os, sys, re, pickle, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from align import ass_lines, feats, align_fast
import paths
BS = "\\"
NOVEL = "5000 5001 5002 5003 5004".split()
ASS = ["White Album 2 (ic) - The Snow Melts, And Until The Snow Falls %02d.ass" % k for k in (1, 2, 3)]
SEG = re.compile(r"^((?:\\n)*)(　?)(.*?)((?:\\n)*)$", re.S)

def pages(name):
    f = open(os.path.join(paths.JP_DIR, name + ".txt"), "rb").read().split(b",")
    return [x.decode("cp932", "replace") for x in f]

TEXT = re.compile(r"[぀-ヿ一-鿿]")
def is_text(x): return bool(TEXT.search(x)) and not re.search(r"\.\w{3}$", x)   # skip file names / commands
G = []                                  # (script, field, segment index, body)
FIELDS = {}
for n in NOVEL:
    fs = pages(n); FIELDS[n] = fs
    for fi, x in enumerate(fs):
        if not is_text(x): continue
        for si, part in enumerate(x.split(BS + "k")):
            body = SEG.match(part).group(3)
            if body.strip(): G.append((n, fi, si, body))
A = []; NOTES = []
for f in ASS:
    L = ass_lines(os.path.join(paths.ASS_DIR, f))
    starts = collections.Counter(a["start"] for a in L)
    for a in L:
        if not a["style"].startswith("Dialogue"): continue
        t = a["text"].replace("\n", "").lstrip("　 ")
        # translator's notes: a bracketed cue shown at the same time as the real one
        if t.startswith("（") and starts[a["start"]] > 1: NOTES.append((f[-6:-4], a["start"], t)); continue
        A.append(dict(a, text=t, file=f[-6:-4]))
print("translator notes skipped", len(NOTES))
print("paragraphs", len(G), "cues", len(A))
FG = feats([g[3] for g in G], True); FA = feats([a["text"] for a in A], False)
pairs, S0 = align_fast(FA, FG, gap=-1.0)
match = {g: a for a, g in pairs if a is not None and g is not None}
lone_a = [a for a, g in pairs if g is None and a is not None]
new = {n: {fi: x.split(BS + "k") for fi, x in enumerate(FIELDS[n]) if is_text(x)} for n in NOVEL}
gidx = {g[:3]: k for k, g in enumerate(G)}
low = []
for (n, fi, si), k in gidx.items():
    if k not in match: continue
    a = match[k]; txt = A[a]["text"]
    if S0[a, k] < 1.0: low.append((float(S0[a, k]), n, fi, si, G[k][3], txt))
    m_ = SEG.match(new[n][fi][si])
    new[n][fi][si] = m_.group(1) + m_.group(2) + txt + m_.group(4)
out = {n: {fi: (BS + "k").join(parts) for fi, parts in d.items()} for n, d in new.items()}
out = {n: {fi: t for fi, t in d.items() if t != FIELDS[n][fi]} for n, d in out.items()}
# the engine char-wraps novel pages at ~40 cells (half-width = 0.5); break before the one English word it would split
for n, fi, a, b in [("5000", 10, "松川自high", "松川自" + BS + "nhigh")]:
    assert a in out[n][fi]; out[n][fi] = out[n][fi].replace(a, b)
pickle.dump(out, open(os.path.join(paths.WORK, "novel_map.pkl"), "wb"))
un_g = [g for k, g in enumerate(G) if k not in match]
print("matched", len(match), "unmatched paragraphs", len(un_g), "unmatched cues", len(lone_a), "low-similarity matches", len(low))
with open(os.path.join(paths.WORK, "novel_report.md"), "w", encoding="utf-8") as f:
    f.write("# 外传对齐报告\n\n## 没有对上字幕的日文段落（%d）\n\n" % len(un_g))
    for n, fi, si, b in un_g: f.write("- %s #%d.%d %s\n" % (n, fi, si, b[:80]))
    f.write("\n## 没有对上日文的字幕（%d，不放进游戏）\n\n" % len(lone_a))
    for a in lone_a: f.write("- %s %s %s\n" % (A[a]["file"], A[a]["start"], A[a]["text"][:80]))
    f.write("\n## 字幕里的译注（%d，不放进游戏）\n\n" % len(NOTES))
    for fl, st, t in NOTES: f.write("- %s %s %s\n" % (fl, st, t[:100]))
    f.write("\n## 相似度偏低的配对（%d，请抽查）\n\n" % len(low))
    for s, n, fi, si, b, t in sorted(low)[:200]: f.write("- %.2f %s #%d.%d\n  - 日：%s\n  - 粤：%s\n" % (s, n, fi, si, b[:80], t[:80]))
