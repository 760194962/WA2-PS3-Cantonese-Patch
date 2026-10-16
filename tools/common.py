import re,struct,glob
BASE="/mnt/user-data/uploads/WA2 PS3 Cantonese Patch/"
ELF=glob.glob(BASE+"*/PS3_GAME/USRDIR/EBOOT.elf")[0]
ASS=BASE+"White Album 2 (ic) - 01_test (1).ass"
SCR="/tmp/claude-0/-home-claude/24b8c192-2d1b-5076-95c3-12632b85b8bf/scratchpad/work/jp_full/"
TBL_OFF=0xFE3F0; TBL_N=2706
def font_table(elf):
    out=[]
    for i in range(TBL_N):
        c=struct.unpack(">H",elf[TBL_OFF+2*i:TBL_OFF+2*i+2])[0]
        out.append(c)
    return out
def code2char(c):
    try:
        b=bytes([c]) if c<0x100 else struct.pack(">H",c)
        return b.decode("cp932")
    except Exception: return None
def ass_events(path=ASS):
    ev=[]
    for l in open(path,encoding="utf-8-sig"):
        if l.startswith("Dialogue:"):
            p=l.rstrip("\r\n").split(",",9)
            txt=re.sub(r"\{[^}]*\}","",p[9]).replace("\\N","\n").replace("\\n","\n")
            ev.append((p[1],p[2],p[3],txt))
    return ev
