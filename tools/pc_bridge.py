"""Recover subtitle lines for PS3 fields the direct alignment missed, using the PC script as a bridge.
The subtitles follow the PC version. Where the PS3 version cut or rewrote a scene (e.g. the 1012_030 night scene),
the PS3 lines that survived unchanged sit between many PC-only cues and the direct PS3 alignment loses them.
So: align the subtitles to the PC script (1:1 text), then copy a cue to every still-untranslated PS3 field whose
Japanese is identical to a matched PC line in the same script (nearest by position).
   python tools/pc_bridge.py      (needs work/pc_jp from tools/pc_kcap.py)  -> work/pc_bridge.pkl"""
import os, sys, re, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from align import ass_lines, feats, align_fast
import scr, paths
PC_DIR = os.path.join(paths.WORK, "pc_jp")
CHAIN = [n for n in "1001 1002 1003 1004 1005 1006 1007 1008 1008_020 1008_030 1008_031 1008_040 1008_050 1009 1009_020 1009_030 1010 1010_020 1010_030 1010_040 1010_050 1010_060 1010_070 1011 1011_020 1011_030 1012 1012_020 1012_030 1012_030_2 1013".split()]
def load(d, n):
    p = os.path.join(d, n + ".txt")
    return [x.decode("cp932", "replace") for x in open(p, "rb").read().split(b",")] if os.path.exists(p) else None
P = []                                     # PC text lines in story order: (script, field, text)
for n in CHAIN:
    t = load(PC_DIR, n)
    if t: P += [(n, i, t[i]) for i in range(4, len(t)) if scr.is_text(t[i])]
FP = feats([p[2] for p in P], True)
_, TMAP, _, _ = pickle.load(open(paths.MAP_PKL, "rb"))
out = {}; ptr = 0; got = 0
for k in range(1, 13):
    A = [a for a in ass_lines(os.path.join(paths.ASS_DIR, "White Album 2 (ic) - %02d.ass" % k))
         if not a["style"].startswith(("Prologue", "Lyric", "Note", "Episode"))]
    starts = {}
    for a in A: starts[a["start"]] = starts.get(a["start"], 0) + 1
    A = [a for a in A if not (a["text"].startswith("（") and starts[a["start"]] > 1)]     # translator's notes
    lo, hi = ptr, min(len(P), ptr + int(len(A) * 1.5) + 60)
    pairs, S0 = align_fast(feats([a["text"] for a in A], False), FP[lo:hi], free_end=True)
    pc_cue = {lo + g: a for a, g in pairs if a is not None and g is not None and S0[a, g] > 0.5}
    ptr = max(pc_cue) + 1
    for pg, a in pc_cue.items():
        n, pi, jt = P[pg]
        ps3 = load(paths.JP_DIR, n)
        if ps3 is None: continue
        cand = [i for i, x in enumerate(ps3) if x == jt and i not in TMAP.get(n, {})]
        if not cand: continue
        i = min(cand, key=lambda i: abs(i / len(ps3) - pi / len(load(PC_DIR, n))))
        if i in out.get(n, {}): continue
        out.setdefault(n, {})[i] = A[a]["text"]; got += 1
# reviewed by hand (work/pc_bridge_review.md): wrong matches, and lines from the PC adult scene whose wording does not
# fit the toned-down PS3 context (left Japanese until retranslated); punctuation-only lines stay as the Japanese
WRONG = {("1007", 659), ("1007", 660), ("1007", 661), ("1007", 662), ("1008_020", 9), ("1008_020", 19),
         ("1008_020", 23), ("1008_020", 33), ("1010_020", 119)}
ASK = {("1012_030", k) for k in (597, 658, 662, 688, 697, 703, 705, 765, 786, 794, 796)}
for n in list(out):
    for i in list(out[n]):
        jt = load(paths.JP_DIR, n)[i]
        if (n, i) in WRONG or (n, i) in ASK or re.fullmatch(r"[「」…\s]*", jt): del out[n][i]
out = {n: v for n, v in out.items() if v}
got = sum(map(len, out.values()))
pickle.dump(out, open(os.path.join(paths.WORK, "pc_bridge.pkl"), "wb"))
print("PC lines", len(P), "recovered PS3 fields", got, {n: len(v) for n, v in out.items()})
