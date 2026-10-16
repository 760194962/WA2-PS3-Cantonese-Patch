#!/usr/bin/env python3
# Python 3 port of the extract/decompress logic from kid23/WHITE_ALBUM2 build/wa2_eboot_tool.py
import struct, sys, os, lzma

EBOOT_OFFSET = 0x10000          # virtual address -> file offset in the decrypted ELF
INDEX = 0x10765C                # file offset of the resource index table (from the repo)

def dec_block(params5, comp, usize):
    hdr = params5 + struct.pack("<Q", usize)
    return lzma.LZMADecompressor(format=lzma.FORMAT_ALONE).decompress(hdr + comp, max_length=usize)

def elzma_decompress(buf, usize):
    pos, out = 0, bytearray()
    nblocks = (usize + 0xFFFF) // 0x10000
    for _ in range(nblocks):
        bu, bc = struct.unpack("<II", buf[pos:pos+8])
        params = buf[pos+8:pos+13]
        out += dec_block(params, buf[pos+0x10:pos+0x10+bc], bu)
        pos += (bc + 0x1f) // 0x10 * 0x10
    return bytes(out)

def cstr(buf, off):
    e = buf.index(b"\0", off)
    return buf[off:e].decode("ascii", "replace")

def find_table_start(elf):
    """Walk backwards from the repo's INDEX constant to the real start of the resource table."""
    def valid(p):
        n, d, u, b = struct.unpack(">4I", elf[p:p+16])
        if not (EBOOT_OFFSET <= n < len(elf) + EBOOT_OFFSET and EBOOT_OFFSET <= d < len(elf) + EBOOT_OFFSET and 0 < u < 0x2000000 and 0 < b < 0x2000000):
            return False
        nm = cstr(elf, n - EBOOT_OFFSET)
        return 0 < len(nm) <= 16 and nm.replace("_", "").replace(".", "").isalnum()
    pos = INDEX
    while valid(pos - 0x10): pos -= 0x10
    return pos

def entries(elf):
    pos = find_table_start(elf)
    while True:
        name_off, data_off, usize, bsize = struct.unpack(">4I", elf[pos:pos+0x10])
        if name_off == 0: break
        name = cstr(elf, name_off - EBOOT_OFFSET)
        if name[-4:-3] == "_": name = name[:-4] + "." + name[-3:]
        yield pos, name, data_off - EBOOT_OFFSET, usize, bsize
        pos += 0x10

if __name__ == "__main__":
    elf = open(sys.argv[1], "rb").read()
    out = sys.argv[2]; os.makedirs(out, exist_ok=True)
    n = bad = 0
    for pos, name, doff, usize, bsize in entries(elf):
        try:
            data = elzma_decompress(elf[doff:doff+bsize], usize)
            assert len(data) == usize, (len(data), usize)
            open(os.path.join(out, name), "wb").write(data)
            n += 1
        except Exception as e:
            bad += 1; print("FAIL", hex(pos), name, usize, bsize, repr(e)[:100])
    print("entries ok", n, "failed", bad)
