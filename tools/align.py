import re,sys,collections
import os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scr import *
import opencc
_t2s=opencc.OpenCC("t2s")
def ass_lines(path):
    out=[]
    for k,l in enumerate(open(path,encoding="utf-8-sig")):
        if not l.startswith("Dialogue:"): continue
        p=l.rstrip("\r\n").split(",",9)
        txt=re.sub(r"\{[^}]*\}","",p[9]).replace("\\N","\n").replace("\\n","\n")
        out.append(dict(ln=k,start=p[1],end=p[2],style=p[3],text=txt))
    return out
def kinds(s):
    s=s.strip()
    return s[:1] if s[:1] in "「（『" else "n"
KAN=re.compile(r"[\u3400-\u9fff]")
def norm(s): return _t2s.convert(s)
def kset(s): return collections.Counter(KAN.findall(norm(re.sub(r"<R([^|]*)\|[^>]*>",r"\1",s))))
def ellipsis_only(s): return re.fullmatch(r"[「」『』（）…・\.！？!?　 \n。、～ー－]*",s) is not None and "…" in s
def sim(a,g):
    at=a.strip("\n 　"); gt=g.replace("\\k\\n","").replace("\\n","\n").strip("\n 　")
    s=0.0
    ka,kg=kinds(at),kinds(gt)
    s+=0.6 if ka==kg else -0.6
    if ellipsis_only(gt) or ellipsis_only(at):
        ca,cg=at.count("…"),gt.count("…")
        if ellipsis_only(gt) and ellipsis_only(at): return s+2.0-0.3*abs(ca-cg)
        return s-1.5
    A,G=kset(at),kset(gt)
    if A and G:
        inter=sum((A&G).values()); s+=4.0*inter/max(1,min(sum(A.values()),sum(G.values())))*0.5+2.0*inter/(sum(A.values())+sum(G.values()))*2
    la,lg=len(at.replace("\n","")),len(gt.replace("\n",""))
    s-=0.8*abs(np.log((la+3)/(lg+3)*0.9+1e-6))
    na,ng=at.count("\n"),gt.count("\n")
    s+=0.3 if na==ng else -0.2*min(3,abs(na-ng))
    return s
def align(A,G,gap=-1.2):
    n,m=len(A),len(G)
    S=np.zeros((n+1,m+1),np.float32); P=np.zeros((n+1,m+1),np.int8)
    S[:,0]=np.arange(n+1)*gap; S[0,:]=np.arange(m+1)*gap; P[1:,0]=1; P[0,1:]=2
    for i in range(1,n+1):
        ai=A[i-1]
        for j in range(1,m+1):
            d=S[i-1,j-1]+sim(ai,G[j-1]); u=S[i-1,j]+gap; l=S[i,j-1]+gap
            if d>=u and d>=l: S[i,j]=d; P[i,j]=0
            elif u>=l: S[i,j]=u; P[i,j]=1
            else: S[i,j]=l; P[i,j]=2
    i,j=n,m; pairs=[]
    while i>0 or j>0:
        p=P[i,j]
        if i>0 and j>0 and p==0: pairs.append((i-1,j-1)); i-=1; j-=1
        elif i>0 and (p==1 or j==0): pairs.append((i-1,None)); i-=1
        else: pairs.append((None,j-1)); j-=1
    return pairs[::-1], S[n,m]

# ---------- fast vectorised version ----------
def feats(texts, is_game):
    rows=[]
    for t in texts:
        x=t.replace("\\k\\n","").replace("\\n","\n") if is_game else t
        x=x.strip("\n 　")
        x2=re.sub(r"<R([^|]*)\|[^>]*>",r"\1",x)
        rows.append(dict(k=kinds(x),nl=x.count("\n"),ln=len(x.replace("\n","")),
            ell=ellipsis_only(x),ce=x.count("…"),ks=set(KAN.findall(norm(x2)))))
    return rows
def simmat(FA,FG):
    n,m=len(FA),len(FG)
    voc={}
    for F in (FA,FG):
        for f in F:
            for c in f["ks"]: voc.setdefault(c,len(voc))
    def mat(F):
        M=np.zeros((len(F),max(1,len(voc))),np.float32)
        for i,f in enumerate(F):
            for c in f["ks"]: M[i,voc[c]]=1
        return M
    MA,MG=mat(FA),mat(FG)
    inter=MA@MG.T; sa=MA.sum(1)[:,None]; sg=MG.sum(1)[None,:]
    ok=(sa>0)&(sg>0)
    S=np.where(ok,2*inter/np.maximum(1,np.minimum(sa,sg))+4*inter/np.maximum(1,sa+sg),0)
    ka=np.array([f["k"] for f in FA]); kg=np.array([f["k"] for f in FG])
    S=S+np.where(ka[:,None]==kg[None,:],0.6,-0.6)
    la=np.array([f["ln"] for f in FA],np.float32)[:,None]; lg=np.array([f["ln"] for f in FG],np.float32)[None,:]
    S=S-0.8*np.abs(np.log((la+3)/(lg+3)*0.9+1e-6))
    na=np.array([f["nl"] for f in FA])[:,None]; ng=np.array([f["nl"] for f in FG])[None,:]
    S=S+np.where(na==ng,0.3,-0.2*np.minimum(3,np.abs(na-ng)))
    ea=np.array([f["ell"] for f in FA])[:,None]; eg=np.array([f["ell"] for f in FG])[None,:]
    ca=np.array([f["ce"] for f in FA])[:,None]; cg=np.array([f["ce"] for f in FG])[None,:]
    both=ea&eg; one=ea^eg
    S=np.where(both,0.6*(ka[:,None]==kg[None,:])-0.6*(ka[:,None]!=kg[None,:])+2.0-0.3*np.abs(ca-cg),S)
    S=np.where(one,np.where(ka[:,None]==kg[None,:],0.6,-0.6)-1.5,S)
    return S.astype(np.float32)
def align_fast(FA,FG,gap=-1.2,free_end=False):
    S0=simmat(FA,FG); n,m=S0.shape
    try:
        from numba import njit
    except Exception: njit=None
    def dp(S0,gap,free_end):
        n,m=S0.shape
        S=np.zeros((n+1,m+1),np.float32); P=np.zeros((n+1,m+1),np.int8)
        for i in range(1,n+1): S[i,0]=i*gap; P[i,0]=1
        for j in range(1,m+1): S[0,j]=j*gap; P[0,j]=2
        for i in range(1,n+1):
            for j in range(1,m+1):
                d=S[i-1,j-1]+S0[i-1,j-1]; u=S[i-1,j]+gap; l=S[i,j-1]+gap
                if d>=u and d>=l: S[i,j]=d; P[i,j]=0
                elif u>=l: S[i,j]=u; P[i,j]=1
                else: S[i,j]=l; P[i,j]=2
        return S,P
    if njit: dp=njit(cache=False)(dp)
    S,P=dp(S0,gap,free_end)
    j=m
    if free_end: j=int(np.argmax(S[n,:]))
    i=n; pairs=[]
    while i>0 or j>0:
        p=P[i,j]
        if i>0 and j>0 and p==0: pairs.append((i-1,j-1)); i-=1; j-=1
        elif i>0 and (p==1 or j==0): pairs.append((i-1,None)); i-=1
        else: pairs.append((None,j-1)); j-=1
    return pairs[::-1], S0
