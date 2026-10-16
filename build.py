"""One-shot build:  python build.py [out_dir]
   extract JP scripts (once) -> align IC ASS -> mapping -> EBOOT.elf / 02309.elzma / 02309.size -> verify"""
import os, sys, subprocess
ROOT = os.path.dirname(os.path.abspath(__file__)); T = os.path.join(ROOT, "tools")
sys.path.insert(0, T); import paths
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "out")
def run(*a): print(">>", " ".join(a)); subprocess.run([sys.executable, *a], check=True)
if not os.path.exists(os.path.join(paths.JP_DIR, "1001.txt")): run(os.path.join(T, "extract_jp.py"))
if not os.path.exists(paths.ALIGN_PKL) or "--realign" in sys.argv: run(os.path.join(T, "run_ic.py"))
run(os.path.join(T, "make_map.py"))
run(os.path.join(T, "build_yue3.py"), out)
run(os.path.join(T, "verify_elf.py"), out)
print("done ->", out)
