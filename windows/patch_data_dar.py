#!/usr/bin/env python3
"""Apply the WHITE ALBUM2 Cantonese trial patch (1001 only) to a disc dump.
  python patch_data_dar.py <folder containing the 'WHITE ALBUM2 ...' disc folder>
  python patch_data_dar.py <same folder> --undo
Does: (1) appends the new font texture to data.dar and repoints index entry 2309 (original bytes kept),
      (2) backs up EBOOT.BIN as EBOOT.BIN.orig and installs the patched decrypted ELF as EBOOT.BIN."""
import sys, os, glob, struct, json, shutil, stat
HERE = os.path.dirname(os.path.abspath(__file__))
IDX = 2309
def main():
    if len(sys.argv) < 2: print(__doc__); return 1
    base = sys.argv[1]; undo = "--undo" in sys.argv
    cand = glob.glob(os.path.join(base, "WHITE ALBUM2*", "PS3_GAME", "USRDIR"))
    if not cand: print("disc folder not found under", base); return 1
    usr = cand[0]; dar = os.path.join(usr, "data.dar"); ebt = os.path.join(usr, "EBOOT.BIN"); orig = ebt + ".orig"
    undo_json = os.path.join(HERE, "undo.json")
    def writable(p):
        if os.path.exists(p): os.chmod(p, os.stat(p).st_mode | stat.S_IWRITE)
    if undo:
        if not os.path.exists(undo_json): print("no undo.json"); return 1
        u = json.load(open(undo_json))
        writable(dar)
        with open(dar, "r+b") as f:
            f.seek(0x10 + IDX * 0x20); f.write(bytes.fromhex(u["entry"])); f.truncate(u["len"])
        if os.path.exists(orig): writable(ebt); shutil.copyfile(orig, ebt)
        print("restored."); return 0
    comp = open(os.path.join(HERE, "02309.elzma"), "rb").read()
    size = int(open(os.path.join(HERE, "02309.size")).read())
    newelf = open(os.path.join(HERE, "EBOOT.elf"), "rb").read()
    writable(dar)
    with open(dar, "r+b") as f:
        f.seek(0x10 + IDX * 0x20); entry = f.read(0x20)
        osz, ozs, ooff = struct.unpack("<LLQ", entry[:16])
        if osz != 9729984 and not os.path.exists(undo_json):
            print("unexpected entry %d (size %d) - aborting" % (IDX, osz)); return 1
        f.seek(0, 2); flen = f.tell()
        if not os.path.exists(undo_json):
            json.dump({"entry": entry.hex(), "len": flen}, open(undo_json, "w"))
        else:
            flen = json.load(open(undo_json))["len"]      # re-apply: drop previously appended data
            f.truncate(flen)
        f.seek(flen)
        pad = (-flen) % 0x10; f.write(b"\0" * pad); off = flen + pad
        f.write(comp)
        ne = struct.pack("<LLQ", size, len(comp), off) + entry[16:]
        f.seek(0x10 + IDX * 0x20); f.write(ne)
    print("data.dar entry %d -> offset %d size %d zsize %d" % (IDX, off, size, len(comp)))
    if os.path.exists(ebt) and not os.path.exists(orig): shutil.copyfile(ebt, orig)
    writable(ebt); open(ebt, "wb").write(newelf)
    print("EBOOT.BIN replaced with patched ELF (original saved as EBOOT.BIN.orig)")
    return 0
if __name__ == "__main__": sys.exit(main())
