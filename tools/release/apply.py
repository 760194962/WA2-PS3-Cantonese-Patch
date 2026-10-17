#!/usr/bin/env python3
"""WHITE ALBUM2 幸せの向こう側 (PS3 / BLJM60571) Cantonese patch - user-side patcher.

Put into input\\ :  data.dar   (from the game folder  PS3_GAME\\USRDIR\\data.dar)
                    EBOOT.BIN  (from the official 1.01 update  /dev_hdd0/game/BLJM60571/USRDIR/EBOOT.BIN)
Put scetool.exe and its data folder into scetool\\ .
Then run 安裝補丁.bat (or: python patch\\apply.py). Results:
    input\\data.dar     patched in place (the original entry is saved in input\\data.dar.undo.json)
    output\\EBOOT.BIN   signed, for /dev_hdd0/game/BLJM60571/USRDIR/
    python patch\\apply.py --undo   restores input\\data.dar
Only the Python standard library is used."""
import os, sys, struct, json, hashlib, lzma, subprocess, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__)); KIT = os.path.dirname(HERE)
INP, OUT, SCE = os.path.join(KIT, "input"), os.path.join(KIT, "output"), os.path.join(KIT, "scetool")
IDX, ORIG_SIZE = 2309, 9729984            # data.dar entry 2309 = the font package; its original unpacked size
SIGN = ("--sce-type=SELF --compress-data=TRUE --skip-sections=TRUE --key-revision=01 --self-auth-id=1010000001000003 "
        "--self-app-version=0001000000000000 --self-add-shdrs=TRUE --self-vendor-id=01000002 --self-type=NPDRM "
        "--self-fw-version=0003004000000000 --np-license-type=FREE --np-real-fname=EBOOT.BIN --np-app-type=UEXEC "
        "--np-content-id=JP0761-BLJM60571_00-GAMEUPDATE000001").split()

def die(msg): print("\n[錯誤] " + msg); sys.exit(1)

# ---------------- EBOOT difference file (WA2D1) ----------------
# header: b"WA2D1", sha1(source ELF), sha1(target ELF), u32 target length; then an LZMA (xz) op stream:
#   0x01 COPY  u32 src_off, u32 len   |   0x02 INSERT u32 len, bytes   |   0x03 ZERO u32 len
def wa2d_apply(src, diff):
    if diff[:5] != b"WA2D1": die("差異文件格式唔啱")
    ssha, dsha, dlen = diff[5:25], diff[25:45], struct.unpack(">I", diff[45:49])[0]
    if hashlib.sha1(src).digest() != ssha: return None
    ops = lzma.decompress(diff[49:]); out = bytearray(); i = 0
    while i < len(ops):
        op = ops[i]; i += 1
        if op == 1: so, n = struct.unpack(">II", ops[i:i + 8]); i += 8; out += src[so:so + n]
        elif op == 2: n = struct.unpack(">I", ops[i:i + 4])[0]; i += 4; out += ops[i:i + n]; i += n
        elif op == 3: n = struct.unpack(">I", ops[i:i + 4])[0]; i += 4; out += bytes(n)
        else: die("差異文件損壞")
    if len(out) != dlen or hashlib.sha1(out).digest() != dsha: die("套用差異之後校驗失敗")
    return bytes(out)

# ---------------- data.dar ----------------
def patch_dar(path):
    comp = open(os.path.join(HERE, "02309.elzma"), "rb").read()
    size = int(open(os.path.join(HERE, "02309.size")).read())
    undo = path + ".undo.json"
    with open(path, "r+b") as f:
        f.seek(0x10 + IDX * 0x20); entry = f.read(0x20)
        usz, zsz, off = struct.unpack("<LLQ", entry[:16])
        f.seek(0, 2); flen = f.tell()
        if usz == size and zsz == len(comp) and off + zsz <= flen:
            f.seek(off);
            if f.read(zsz) == comp: print("data.dar 已經係呢個版本嘅補丁，跳過。"); return
        if os.path.exists(undo):                               # patched by an older version: start from the original again
            u = json.load(open(undo)); entry = bytes.fromhex(u["entry"]); flen = u["len"]; f.truncate(flen)
            usz = struct.unpack("<L", entry[:4])[0]
        if usz != ORIG_SIZE: die("data.dar 唔係原版（第 %d 項大小 %d），請放入遊戲原本嘅 data.dar" % (IDX, usz))
        if not os.path.exists(undo): json.dump({"entry": entry.hex(), "len": flen}, open(undo, "w"))
        pad = (-flen) % 0x10; f.seek(flen); f.write(b"\0" * pad); off = flen + pad; f.write(comp)
        f.seek(0x10 + IDX * 0x20); f.write(struct.pack("<LLQ", size, len(comp), off) + entry[16:])
    print("data.dar 已打補丁（字庫追加喺第 %d 字節）。" % off)

def undo_dar(path):
    undo = path + ".undo.json"
    if not os.path.exists(undo): die("搵唔到 " + undo)
    u = json.load(open(undo))
    with open(path, "r+b") as f:
        f.seek(0x10 + IDX * 0x20); f.write(bytes.fromhex(u["entry"])); f.truncate(u["len"])
    os.remove(undo); print("data.dar 已還原。")

# ---------------- EBOOT ----------------
def scetool(*args):
    exe = os.path.join(SCE, "scetool.exe")
    if not os.path.exists(exe): die("請將 scetool.exe（連同佢嘅 data 文件夾）放入 scetool 文件夾")
    r = subprocess.run([exe, *args], cwd=SCE, capture_output=True, text=True, errors="replace")
    return r

def patch_eboot(path):
    raw = open(path, "rb").read(); tmp = tempfile.mkdtemp()
    try:
        if raw[:4] == b"\x7fELF": elf = raw
        elif raw[:4] == b"SCE\x00":
            dec = os.path.join(tmp, "EBOOT.elf"); scetool("--decrypt", os.path.abspath(path), dec)
            if not os.path.exists(dec): die("scetool 解密 EBOOT.BIN 失敗（scetool 嘅 data 文件夾齊唔齊？）")
            elf = open(dec, "rb").read()
        else: die("input\\EBOOT.BIN 唔係 PS3 嘅 EBOOT")
        new = wa2d_apply(elf, open(os.path.join(HERE, "EBOOT.wa2d"), "rb").read())
        if new is None: die("EBOOT.BIN 唔係官方 1.01 更新嘅版本。請先裝好官方 1.01 更新，用 /dev_hdd0/game/BLJM60571/USRDIR/EBOOT.BIN")
        src = os.path.join(tmp, "patched.elf"); open(src, "wb").write(new)
        os.makedirs(OUT, exist_ok=True); dst = os.path.join(OUT, "EBOOT.BIN")
        if os.path.exists(dst): os.remove(dst)
        scetool(*SIGN, "--encrypt", src, os.path.abspath(dst))
        if not os.path.exists(dst): die("scetool 簽名失敗")
        print("EBOOT.BIN 已生成：output\\EBOOT.BIN")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def main():
    dar, eb = os.path.join(INP, "data.dar"), os.path.join(INP, "EBOOT.BIN")
    if "--undo" in sys.argv: undo_dar(dar); return
    if not os.path.exists(dar): die("請將遊戲嘅 data.dar 放入 input 文件夾")
    if not os.path.exists(eb): die("請將官方 1.01 更新嘅 EBOOT.BIN 放入 input 文件夾")
    patch_eboot(eb)                       # EBOOT first: it checks the version before data.dar is touched
    patch_dar(dar)
    print("\n完成。將文件放返落 PS3：")
    print("  input\\data.dar     ->  遊戲文件夾  PS3_GAME/USRDIR/data.dar")
    print("  output\\EBOOT.BIN   ->  /dev_hdd0/game/BLJM60571/USRDIR/EBOOT.BIN")
    print("兩個文件一定要一齊換。")

if __name__ == "__main__": main()
