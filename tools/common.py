import re,struct,glob
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import paths
ELF=paths.EBOOT_BASE
SCR=paths.JP_DIR
TBL_N=2706
with open(ELF,"rb") as _f: _e=_f.read(0xCA2C)
TBL_OFF=0xFEDF0 if _e[0xCA28:0xCA2C]==bytes.fromhex("38600A92") else 0xFE3F0     # font table: v1.01 / v1.00
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
def ass_events(path):
    ev=[]
    for l in open(path,encoding="utf-8-sig"):
        if l.startswith("Dialogue:"):
            p=l.rstrip("\r\n").split(",",9)
            txt=re.sub(r"\{[^}]*\}","",p[9]).replace("\\N","\n").replace("\\n","\n")
            ev.append((p[1],p[2],p[3],txt))
    return ev
