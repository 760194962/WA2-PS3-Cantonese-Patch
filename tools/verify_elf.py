import sys,struct,os
sys.path.insert(0,"/tmp/claude-0/-home-claude/24b8c192-2d1b-5076-95c3-12632b85b8bf/scratchpad/scripts")
import wa2_eboot3 as w
d=sys.argv[1]
elf=open(d+"/EBOOT.elf","rb").read()
ph=[struct.unpack(">IIQQQQQQ",elf[0x40+i*56:0x40+i*56+56]) for i in range(8)]
def va2off(va):
    for t,fl,off,vaa,pa,fs,ms,al in ph:
        if t==1 and fs and vaa<=va<vaa+fs: return va-vaa+off
pos=0x106edc; bad=n=0
while True:
    no,do,us,bs=struct.unpack(">4I",elf[pos:pos+16])
    if no==0: break
    name=w.cstr(elf,no-0x10000)
    if name[-4:-3]=="_": name=name[:-4]+"."+name[-3:]
    fo=va2off(do); data=w.elzma_decompress(elf[fo:fo+bs],us)
    f=d+"/"+name+".bin"
    if os.path.exists(f):
        n+=1
        if data!=open(f,"rb").read(): bad+=1; print("MISMATCH",name)
    pos+=16
print("verified",n,"bad",bad)
