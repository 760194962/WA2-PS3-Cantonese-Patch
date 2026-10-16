"""Extract the Japanese scripts (*.txt / *.bnr) from the original decrypted EBOOT into WORK/jp_full."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths, wa2_eboot3 as w
os.makedirs(paths.JP_DIR, exist_ok=True)
elf = open(paths.EBOOT_ORIG, "rb").read()
n = 0
for pos, name, doff, usize, bsize in w.entries(elf):
    data = w.elzma_decompress(elf[doff:doff + bsize], usize)
    open(os.path.join(paths.JP_DIR, name), "wb").write(data); n += 1
print("extracted", n, "resources to", paths.JP_DIR)
