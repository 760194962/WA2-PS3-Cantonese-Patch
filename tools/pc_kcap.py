"""Unpack a PC (Leaf) KCAP archive, e.g. the PC version's script.pak.
   python tools/pc_kcap.py "WHITE ALBUM2/script.pak" work/pc_jp
Header: "KCAP", u32, u32, u32 count; entries of 0x2C bytes: u32 compressed, name[24], u32 x2 (timestamp), u32 offset,
u32 size. Compressed data: u32 packed size, u32 unpacked size, then LZSS (4 KiB window, start 0xFEE, flags LSB first)."""
import os, sys, struct

def lzss(src, usize):
    win = bytearray(4096); wp = 0xFEE; out = bytearray(); i = 0
    while len(out) < usize and i < len(src):
        flags = src[i]; i += 1
        for b in range(8):
            if len(out) >= usize or i >= len(src): break
            if flags >> b & 1:
                c = src[i]; i += 1; out.append(c); win[wp] = c; wp = (wp + 1) & 0xFFF
            else:
                lo, hi = src[i], src[i + 1]; i += 2
                off = lo | (hi & 0xF0) << 4; ln = (hi & 0x0F) + 3
                for k in range(ln):
                    c = win[(off + k) & 0xFFF]; out.append(c); win[wp] = c; wp = (wp + 1) & 0xFFF
    return bytes(out)

def entries(d):
    assert d[:4] == b"KCAP", "not a KCAP archive"
    n = struct.unpack("<I", d[12:16])[0]
    for k in range(n):
        e = d[16 + k * 0x2C:16 + (k + 1) * 0x2C]
        comp = struct.unpack("<I", e[:4])[0]; name = e[4:28].split(b"\0")[0].decode("cp932")
        off, size = struct.unpack("<II", e[36:44])
        yield name, comp, off, size

def read(d, comp, off, size):
    raw = d[off:off + size]
    if not comp: return raw
    psize, usize = struct.unpack("<II", raw[:8])
    return lzss(raw[8:8 + psize], usize)

if __name__ == "__main__":
    d = open(sys.argv[1], "rb").read(); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
    n = 0
    for name, comp, off, size in entries(d):
        open(os.path.join(out, name), "wb").write(read(d, comp, off, size)); n += 1
    print("extracted", n, "files to", out)
