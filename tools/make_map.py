import pickle,sys,numpy as np,collections,re
import os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import paths
G,res=pickle.load(open(paths.ALIGN_PKL,"rb"))
cand={}   # g -> (sim, text, file)
div=[]
for f,r in res.items():
    pr=r["pairs"]
    v=np.array([r["sims"][a] if (a is not None and g is not None) else -1.2 for a,g in pr])
    k=25; w=np.convolve(v,np.ones(k)/k,mode="same")
    for idx,(a,g) in enumerate(pr):
        if a is None or g is None: continue
        if w[idx]<0.45: div.append((f,idx,g)); continue
        s=r["sims"][a]
        if g not in cand or s>cand[g][0]: cand[g]=(s,r["A"][a]["text"],f,a)
# ep07 concert scene: PC shows overlay chatter (named styles) that PS3 doesn't have, which threw
# the global alignment off -> realign that stretch locally against 1008 fields 441..488
from align import feats as _f, align_fast as _af
r7=res[[k for k in res if "07.ass" in k][0]]; A7=r7["A"]
named=("Io","Takeya","JK","Tomo","Takahiro","Akina")
As=[(k,A7[k]) for k in range(276,330) if A7[k]["style"] not in named]
Gs=[j for j,g in enumerate(G) if g[0]=="1008" and 441<=g[1]<=488]
pr7,S7=_af(_f([a["text"] for k,a in As],False),_f([G[j][2] for j in Gs],True),gap=-1.0,free_end=True)
fix=0
for a,g in pr7:
    if a is None or g is None: continue
    cand[Gs[g]]=(9.0,As[a][1]["text"],"07 local",As[a][0]); fix+=1
print("ep07 concert realigned",fix)
# second playthrough (other IC branches): align against still-unmapped game lines
from align import ass_lines, feats, align_fast
U=[j for j in range(len(G)) if j not in cand]
A2=[x for x in ass_lines(os.path.join(paths.ASS_DIR,"White Album 2 (ic) 2nd run.ass")) if not x["style"].startswith(("Prologue","Lyric","Note","Episode"))]
pr,S0=align_fast(feats([a["text"] for a in A2],False),feats([G[j][2] for j in U],True),gap=-0.8)
v=np.array([float(S0[a,g]) if (a is not None and g is not None) else -1.2 for a,g in pr])
w=np.convolve(v,np.ones(25)/25,mode="same"); add=0
for idx,(a,g) in enumerate(pr):
    if a is None or g is None or w[idx]<0.45: continue
    cand[U[g]]=(float(S0[a,g]),A2[a]["text"],"2nd run",a); add+=1
print("2nd run added",add)
# resulting mapping per script
tmap=collections.defaultdict(dict)
for g,(s,t,f,a) in cand.items():
    n,i,_=G[g]; tmap[n][i]=t
print("mapped",len(cand),"of",len(G),"diverged-rejected",len(div))
unm=[(j,G[j]) for j in range(len(G)) if j not in cand]
print("unmapped game lines",len(unm))
pickle.dump((G,dict(tmap),unm,div),open(paths.MAP_PKL,"wb"))
per=collections.Counter(G[j][0] for j in range(len(G))); pm=collections.Counter(n for n in (G[g][0] for g in cand))
print({n:(pm[n],per[n]) for n in per})
