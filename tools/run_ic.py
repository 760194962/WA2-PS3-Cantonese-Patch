import sys,json,pickle,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from align import *
import paths
CHAIN="1001 1002 1003 1004 1005 1006 1007 1008 1008_020 1008_030 1008_031 1008_040 1008_050 1009 1009_020 1009_030 1010 1010_020 1010_030 1010_040 1010_050 1010_060 1010_070 1011 1011_020 1011_030 1012 1012_020 1012_030 1012_030_2 1013".split()
G=[]
for n in CHAIN:
    for i,t in lines(n): G.append((n,i,t))
FG=feats([g[2] for g in G],True)
print("game lines",len(G))
files=["White Album 2 (ic) - %02d.ass"%k for k in range(1,13)]
ptr=0; res={}
for f in files:
    A=[x for x in ass_lines(os.path.join(paths.ASS_DIR,f)) if not x["style"].startswith(("Prologue","Lyric","Note","Episode"))]
    lo=max(0,ptr-int(os.environ.get("BACK","0"))); hi=min(len(G),ptr+int(len(A)*1.5)+60)
    FA=feats([a["text"] for a in A],False)
    pairs,S0=align_fast(FA,FG[lo:hi],free_end=True)
    mt=[(a,lo+g) for a,g in pairs if a is not None and g is not None]
    last=max(g for a,g in mt)
    res[f]=dict(A=A,pairs=[(a,None if g is None else lo+g) for a,g in pairs],lo=lo,sims={a:float(S0[a,g]) for a,g in pairs if a is not None and g is not None})
    un_a=[a for a,g in pairs if a is not None and g is None]
    first=min(g for a,g in mt)
    gaps_g=(last+1-first)-len(mt)
    print(f[-9:],"A",len(A),"matched",len(mt),"unmatchedA",len(un_a),"gameSpan",first,last,"gameSkipped",gaps_g,G[first][0],G[last][0])
    ptr=last+1
pickle.dump((G,res),open(paths.ALIGN_PKL,"wb"))
