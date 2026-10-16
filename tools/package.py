"""Turn a build dir (EBOOT.elf, 02309.elzma, 02309.size) into ready-to-copy files in output/:
     output/data.dar            -> disc location  (.../PS3_GAME/USRDIR/data.dar)
     output/ps3_npdrm_v3/update_patched/EBOOT.BIN -> /dev_hdd0/game/BLJM60571/USRDIR/EBOOT.BIN   (signed NPDRM UEXEC)
     output/rpcs3/EBOOT.BIN     -> RPCS3's PS3_GAME/USRDIR/EBOOT.BIN (decrypted ELF; use together with output/data.dar)
Never touches the game folder."""
import os, sys, struct, shutil, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
IDX = 2309
SIGN = ("--sce-type=SELF --compress-data=TRUE --skip-sections=TRUE --key-revision=01 --self-auth-id=1010000001000003 "
        "--self-app-version=0001000000000000 --self-add-shdrs=TRUE --self-vendor-id=01000002 --self-type=NPDRM "
        "--self-fw-version=0003004000000000 --np-license-type=FREE --np-real-fname=EBOOT.BIN --np-app-type=UEXEC "
        "--np-content-id=JP0761-BLJM60571_00-GAMEUPDATE000001").split()
def main(build, out=paths.OUTPUT):
    elf = os.path.join(build, "EBOOT.elf"); comp = open(os.path.join(build, "02309.elzma"), "rb").read()
    size = int(open(os.path.join(build, "02309.size")).read())
    for d in (os.path.join("ps3_npdrm_v3", "update_patched"), "rpcs3"): os.makedirs(os.path.join(out, d), exist_ok=True)
    dar = os.path.join(out, "data.dar")
    print("copying original data.dar ..."); shutil.copyfile(paths.ORIG_DAR, dar)
    with open(dar, "r+b") as f:
        f.seek(0x10 + IDX * 0x20); entry = f.read(0x20)
        osz = struct.unpack("<L", entry[:4])[0]
        assert osz == 9729984, "data.dar (bak) is not the original (entry %d size %d)" % (IDX, osz)
        f.seek(0, 2); flen = f.tell(); pad = (-flen) % 0x10
        f.write(b"\0" * pad); off = flen + pad; f.write(comp)
        f.seek(0x10 + IDX * 0x20); f.write(struct.pack("<LLQ", size, len(comp), off) + entry[16:])
    print("data.dar entry %d -> offset %d size %d zsize %d" % (IDX, off, size, len(comp)))
    shutil.copyfile(elf, os.path.join(out, "rpcs3", "EBOOT.BIN"))
    exe = os.path.join(paths.SCETOOL_DIR, "scetool.exe"); dst = os.path.abspath(os.path.join(out, "ps3_npdrm_v3", "update_patched", "EBOOT.BIN"))
    if os.path.exists(dst): os.remove(dst)
    subprocess.run([exe, *SIGN, "--encrypt", os.path.abspath(elf), dst], cwd=paths.SCETOOL_DIR, check=True, stdout=subprocess.DEVNULL)
    assert os.path.exists(dst), "scetool produced no EBOOT.BIN"
    open(os.path.join(out, "README.txt"), "w", encoding="utf-8").write(
        "PS3 实机：\n  data.dar        -> 光盘位置  .../PS3_GAME/USRDIR/data.dar （1.9GB，FTP 用二进制模式，核对大小 %d）\n"
        "  ps3_npdrm_v3/update_patched/EBOOT.BIN -> /dev_hdd0/game/BLJM60571/USRDIR/EBOOT.BIN\n两个文件必须一起换。\n\n"
        "RPCS3：data.dar 和 rpcs3/EBOOT.BIN 放进游戏文件夹 PS3_GAME/USRDIR/。\n" % os.path.getsize(dar))
    print("output ready:", out)
if __name__ == "__main__": main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(paths.WORK, "build"))
