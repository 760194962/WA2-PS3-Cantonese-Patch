"""All locations in one place.  Set WA2_DATA (materials folder) and optionally WA2_WORK,
or write them into config.json next to the repo root:  {"data_dir": "E:/WA2 PS3 Cantonese Patch"}

Expected layout of the materials folder (DATA):
  WHITE ALBUM2 [BLJM60571]/PS3_GAME/USRDIR/EBOOT.elf   original v1.00 EBOOT, decrypted (6,964,168 bytes)
  dar_dump/02309.bin                                   original font package (data.dar entry 2309, decompressed)
  ic_ass/*.ass                                         Cantonese subtitle files (ic)
  fonts/YuPearl-Medium.ttf (tw build) ...              俊羽圓體 tw/*.ttf
  fonts/GenSenRounded2TC-M.otf                         源泉圓體 (fallback for glyphs YuPearl lacks)
"""
import os, json, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_cfg = {}
if os.path.exists(os.path.join(ROOT, "config.json")):
    _cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
DATA = os.environ.get("WA2_DATA") or _cfg.get("data_dir") or ROOT   # default: the repo folder itself holds the materials
WORK = os.environ.get("WA2_WORK") or _cfg.get("work_dir") or os.path.join(ROOT, "work")
os.makedirs(WORK, exist_ok=True)
def _one(pat):
    m = glob.glob(pat)
    if not m: raise SystemExit("missing: " + pat)
    return m[0]
EBOOT_ORIG = os.path.join(DATA, "WHITE ALBUM2 [BLJM60571]", "PS3_GAME", "USRDIR", "EBOOT.elf")
if not os.path.exists(EBOOT_ORIG):                   # the disc EBOOT is optional once the v1.01 one is in place
    EBOOT_ORIG = (glob.glob(os.path.join(DATA, "*", "PS3_GAME", "USRDIR", "EBOOT.elf")) or [None])[0]
# the patch is built on the official v1.01 update EBOOT (decrypted with scetool, see windows/decrypt_101.bat) when it is
# there; WA2_EBOOT=1.00 forces the disc EBOOT. Both carry identical scripts and font tables.
EBOOT_101 = os.path.join(ROOT, "cantonese_patch", "update_101", "EBOOT_101.elf")
EBOOT_BASE = EBOOT_ORIG if os.environ.get("WA2_EBOOT") == "1.00" or not os.path.exists(EBOOT_101) else EBOOT_101
if EBOOT_BASE is None: raise SystemExit("missing: the decrypted EBOOT (" + EBOOT_101 + " or the disc EBOOT.elf)")
FONT_PKG = os.path.join(DATA, "dar_dump", "02309.bin")
ASS_DIR = os.path.join(DATA, "ic_ass")
FONT_DIR = os.path.join(DATA, "fonts")
_yp = [os.path.join(FONT_DIR, "YuPearl-%s.ttf"), os.path.join(FONT_DIR, "YuPearl-1.011", "tw", "YuPearl-%s.ttf")]
YUPEARL = _yp[0] if os.path.exists(_yp[0] % "Medium") else _yp[1]
GENSEN = os.path.join(FONT_DIR, "GenSenRounded2TC-M.otf")
if not os.path.exists(GENSEN):                      # download once (OFL font, ButTaiwan/gensen-font)
    try:
        import urllib.request
        os.makedirs(FONT_DIR, exist_ok=True)
        urllib.request.urlretrieve("https://github.com/ButTaiwan/gensen-font/raw/master/otf/TC/GenSenRounded2TC-M.otf", GENSEN)
    except Exception as e:
        print("could not fetch GenSenRounded2TC-M.otf:", e, "- put it in", FONT_DIR)
JP_DIR = os.path.join(WORK, "jp_full") + os.sep          # extracted Japanese scripts (extract_jp.py)
ALIGN_PKL = os.path.join(WORK, "ic_align.pkl")
MAP_PKL = os.path.join(WORK, "ic_map.pkl")
TOOLS = os.path.dirname(os.path.abspath(__file__))
LZENC = os.path.join(TOOLS, "lzenc.exe" if os.name == "nt" else "lzenc")
SCETOOL_DIR = os.path.join(ROOT, "cantonese_patch", "scetool")          # scetool.exe + its data folder
ORIG_DAR = os.path.join(ROOT, "data.dar (bak)")                          # untouched original data.dar (1,913,230,288 bytes)
OUTPUT = os.path.join(ROOT, "output")                                    # what you copy to the PS3 / RPCS3
