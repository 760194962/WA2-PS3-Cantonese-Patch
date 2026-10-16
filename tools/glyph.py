import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import paths
FONTFILE=paths.GENSEN
def _hk_index():
    for i in range(10):
        try:
            f=ImageFont.truetype(FONTFILE,30,index=i)
            if f.getname()[0].endswith("HK"): return i
        except Exception: break
    return 0
HK=0
BG=(0x55,0x88,0xee)
YP=paths.YUPEARL
import functools
@functools.lru_cache(None)
def _cmap(weight):
    from fontTools.ttLib import TTFont
    return set(TTFont(YP%weight).getBestCmap())
def _masks_half(ch,font,cx,cy,stroke,maxw):
    # draw wide, squeeze horizontally if the glyph is wider than maxw, paste centred at cx
    m=Image.new("L",(120,40),0); ImageDraw.Draw(m).text((60,cy),ch,fill=255,font=font,anchor="mm")
    o=Image.new("L",(120,40),0); ImageDraw.Draw(o).text((60,cy),ch,fill=255,font=font,anchor="mm",stroke_width=stroke,stroke_fill=255)
    b=o.getbbox()
    if not b: return Image.new("L",(40,40),0),Image.new("L",(40,40),0)
    x0,x1=b[0],b[2]; w=x1-x0
    m=m.crop((x0,0,x1,40)); o=o.crop((x0,0,x1,40))
    if w>maxw:
        m=m.resize((maxw,40),Image.LANCZOS); o=o.resize((maxw,40),Image.LANCZOS); w=maxw
    M=Image.new("L",(40,40),0); O=Image.new("L",(40,40),0)
    px=int(round(cx-w/2)); M.paste(m,(px,0)); O.paste(o,(px,0))
    return M,O
def _compose(m,o):
    f=np.asarray(m,np.float32)/255; ot=np.asarray(o,np.float32)/255
    sh=np.roll(np.roll(ot,2,0),2,1); sh=np.asarray(Image.fromarray((sh*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)),np.float32)/255
    H,W=np.asarray(m).shape
    ys=np.arange(H)[:,None]
    t=np.clip((ys-4)/30.0,0,1)
    top=np.array([255,255,255],np.float32); bot=np.array([176,224,208],np.float32)
    fillc=top[None,None,:]*(1-t[...,None])+bot[None,None,:]*t[...,None]
    fillc=np.broadcast_to(fillc,(H,W,3))
    dark=np.array([43,52,59],np.float32)
    # layer composite (straight alpha): shadow < outline < fill
    A_sh=sh*0.33; A_o=ot*0.9; A_f=f*1.0
    rgb=np.zeros((H,W,3),np.float32); a=np.zeros((H,W),np.float32)
    for col,al in ((dark,A_sh),(dark,A_o),(None,A_f)):
        c=fillc if col is None else col[None,None,:]
        na=al+a*(1-al)
        rgb=np.where(na[...,None]>0,(c*al[...,None]+rgb*a[...,None]*(1-al[...,None]))/np.maximum(na[...,None],1e-6),rgb)
        a=na
    
    q=lambda v:np.clip(np.rint(v/17),0,15).astype(np.uint16)
    A=q(a*255); R=q(rgb[...,0]); G=q(rgb[...,1]); B=q(rgb[...,2])
    bg=A==0
    R=np.where(bg,BG[0]//17,R);G=np.where(bg,BG[1]//17,G);B=np.where(bg,BG[2]//17,B)
    return ((A<<12)|(R<<8)|(G<<4)|B).astype(np.uint16)

def render_strip(text,size=27,cy=19,weight="Medium",stroke=2,tmin=1.5,tmax=3.5,tdef=2.0,P=29,dup=1):
    """Render a Latin run with even letter spacing and cut it into glyph cells.
    Reverse-engineered: the engine draws the whole 40px cell but advances full-width
    glyphs by size+spacing = 29 atlas px, so cell k shows strip columns [29k, 29k+29)
    in its middle (cols M..M+29) plus `dup` px of the neighbours for texture filtering."""
    M=(40-P)//2
    font=ImageFont.truetype(YP%weight,size,layout_engine=ImageFont.Layout.BASIC)
    def put(im,stk,track):
        d=ImageDraw.Draw(im); x=40.0
        for ch in text:
            d.text((x,cy),ch,fill=255,font=font,anchor="lm",stroke_width=stk,stroke_fill=255)
            x+=font.getlength(ch)+track
    def bbox(track):
        im=Image.new("L",(40*len(text)+120,40),0); put(im,stroke,track); return im.getbbox()
    gaps=max(1,len(text)-1)
    b0=bbox(0.0); base=b0[2]-b0[0]
    n=max(1,-(-(base+int(tdef*gaps))//P))
    if n>1 and base+tmin*gaps<=(n-1)*P-4: n-=1
    target=n*P-5
    track=min(tmax,max(tmin,(target-base)/gaps)) if len(text)>1 else 0
    b=bbox(track); w=b[2]-b[0]; scale=min(1.0,(n*P-3)/w)
    def draw(stk,dx):
        im=Image.new("L",(40*len(text)+120,40),0); put(im,stk,track)
        im=im.crop((b[0],0,b[2],40))
        if scale<1: im=im.resize((max(1,int(im.width*scale)),40),Image.LANCZOS)
        out=Image.new("L",(n*P+40-P,40),0); out.paste(im,(M+(n*P-im.width)//2+dx,0)); return out
    # slide the word inside its slack so the slice boundaries cut through as little ink as possible
    o0=draw(stroke,0); slack=max(0,n*P-(o0.getbbox()[2]-o0.getbbox()[0]) if o0.getbbox() else 0)
    best=(1e18,0)
    for dx in range(-min(3,slack//2),min(3,slack-slack//2)+1):
        a=np.asarray(draw(stroke,dx),np.float32)
        cost=sum(a[:,M+k*P-1:M+k*P+1].sum() for k in range(1,n))
        best=min(best,(cost+abs(dx)*0.01,dx))
    dx=best[1]
    full=_compose(draw(0,dx),draw(stroke,dx))
    bgv=full[0,0]
    cells=[]
    for k in range(n):
        c=np.full((40,40),bgv,np.uint16)
        lo=M+k*P
        c[:,M:M+P]=full[:,lo:lo+P]
        c[:,M-dup:M]=full[:,lo-dup:lo]
        c[:,M+P:M+P+dup]=full[:,lo+P:lo+P+dup]
        if k==0: c[:,0:M]=full[:,0:M]
        if k==n-1: c[:,M+P:]=full[:,lo+P:lo+P+(40-M-P)]
        cells.append(c)
    return cells

def render_cell(ch,size=30,cx=20,cy=19,weight=None,stroke=2,half=False,maxw=40):
    W=40
    if weight and ord(ch) in _cmap(weight):
        font=ImageFont.truetype(YP%weight,size)
    else:
        font=ImageFont.truetype(FONTFILE,size,index=HK)
    if half or maxw<40:
        m,o=_masks_half(ch,font,cx,cy,stroke,maxw)
    else:
        m=Image.new("L",(W,W),0); ImageDraw.Draw(m).text((cx,cy),ch,fill=255,font=font,anchor="mm")
        o=Image.new("L",(W,W),0); ImageDraw.Draw(o).text((cx,cy),ch,fill=255,font=font,anchor="mm",stroke_width=stroke,stroke_fill=255)
    return _compose(m,o)
def cell_to_rgba(c):
    return np.stack([((c>>8)&15)*17,((c>>4)&15)*17,(c&15)*17,((c>>12)&15)*17],-1).astype(np.uint8)


def render_packed(text,size=27,cy=19,weight="Medium",stroke=2,track=1.0,cap=38):
    """Whole letters per 40px cell (no letter crosses a cell edge), each group centred.
    Robust against the engine's exact glyph pitch."""
    font=ImageFont.truetype(YP%weight,size,layout_engine=ImageFont.Layout.BASIC)
    def ink(ch):
        im=Image.new("L",(80,40),0); ImageDraw.Draw(im).text((20,cy),ch,fill=255,font=font,anchor="lm",stroke_width=stroke,stroke_fill=255)
        b=im.getbbox(); return (b[0]-20,b[2]-20) if b else (0,int(font.getlength(ch)))
    groups=[[]]; used=0
    for ch in text:
        adv=font.getlength(ch); l,r=ink(ch)
        need=(used+track if groups[-1] else 0)+ (r-l if ch!=" " else adv)
        if groups[-1] and need>cap:
            groups.append([]); used=0
            if ch==" ": continue
        if groups[-1]: used+=track
        groups[-1].append((ch,used,l)); used+=(r-l if ch!=" " else adv)
    groups=[g for g in groups if g]
    cells=[]
    for grp in groups:
        last=grp[-1]; l,r=ink(last[0]); w=int(round(last[1]+(r-l)))
        off=(40-w)/2
        def draw(stk):
            im=Image.new("L",(40,40),0); d=ImageDraw.Draw(im)
            for ch,x,l in grp:
                if ch!=" ": d.text((off+x-l,cy),ch,fill=255,font=font,anchor="lm",stroke_width=stk,stroke_fill=255)
            return im
        cells.append(_compose(draw(0),draw(stroke)))
    return cells


def render_prop(ch,size=27,cy=19,weight="Medium",stroke=2,pen=5,track=1):
    """Half-width (1-byte) glyph for the patched engine: the engine draws the 40px cell at pen-5, so the glyph's
    pen origin sits at x=`pen` inside the cell and the advance (returned, atlas px) is the font's own advance + track."""
    if ord(ch) in _cmap(weight): font=ImageFont.truetype(YP%weight,size,layout_engine=ImageFont.Layout.BASIC)
    else: font=ImageFont.truetype(FONTFILE,size,index=HK)
    m=Image.new("L",(40,40),0); ImageDraw.Draw(m).text((pen,cy),ch,fill=255,font=font,anchor="lm")
    o=Image.new("L",(40,40),0); ImageDraw.Draw(o).text((pen,cy),ch,fill=255,font=font,anchor="lm",stroke_width=stroke,stroke_fill=255)
    cell=_compose(m,o)
    # The dialogue renderer (EBOOT 0x3e21c callers) centres each glyph's ink box on a fixed slot; the generic one (0x263c) just
    # draws the cell at pen-5. Make the ink box symmetric about x=12 (= pen+7 for a half slot) with one near-invisible
    # pixel, so both place the glyph origin (x=5) exactly at the pen.
    a=(cell>>12)&15; cols=np.nonzero(a.any(0))[0]
    if len(cols):
        L,R=int(cols[0]),int(cols[-1])
        if (L+R)/2<12 and 24-L>R: cell[20,min(39,24-L)]=(1<<12)|(2<<8)|(3<<4)|3
        elif (L+R)/2>12 and 24-R<L: cell[20,max(0,24-R)]=(1<<12)|(2<<8)|(3<<4)|3
    return cell, font.getlength(ch)+track
