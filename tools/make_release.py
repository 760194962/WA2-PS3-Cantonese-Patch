"""Build the distributable patch kit: no game files, only what the user's own files need.
   python tools/make_release.py [version]      -> output/release/WA2_PS3_Cantonese_<version>/ and .zip
The EBOOT ships as a difference file against the official v1.01 update EBOOT (decrypted); the font goes in as the
compressed data.dar entry. tools/release/apply.py (copied into the kit) does the rest on the user's machine."""
import os, sys, struct, hashlib, lzma, shutil, zipfile, importlib.util
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

def wa2d_encode(src, dst, block=16):
    """COPY/INSERT/ZERO ops turning src into dst (see apply.wa2d_apply)."""
    idx = {}
    for o in range(0, len(src) - block + 1, block):
        k = src[o:o + block]
        if k != bytes(block): idx.setdefault(k, o)
    ops = bytearray(); lit = bytearray(); p = 0; n = len(dst)
    def flush():
        if lit: ops.extend(b"\x02" + struct.pack(">I", len(lit)) + lit); lit.clear()
    while p < n:
        if dst[p] == 0:                                   # zero run
            q = p
            while q < n and dst[q] == 0: q += 1
            if q - p >= 32: flush(); ops.extend(b"\x03" + struct.pack(">I", q - p)); p = q; continue
        so = idx.get(dst[p:p + block])
        if so is None:
            # the source block grid is 16-aligned; try the alignments the target position could have
            for d in range(1, block):
                s2 = idx.get(dst[p - d:p - d + block]) if p >= d else None
                if s2 is not None and src[s2 + d:s2 + d + 1] == dst[p:p + 1]: so = s2 + d; break
        if so is None or src[so:so + 8] != dst[p:p + 8]:
            lit.append(dst[p]); p += 1; continue
        ln = 0
        while p + ln < n and so + ln < len(src) and src[so + ln] == dst[p + ln]: ln += 1
        if ln < 24: lit.extend(dst[p:p + ln]); p += ln; continue
        flush(); ops.extend(b"\x01" + struct.pack(">II", so, ln)); p += ln
    flush()
    return (b"WA2D1" + hashlib.sha1(src).digest() + hashlib.sha1(dst).digest() + struct.pack(">I", len(dst))
            + lzma.compress(bytes(ops), preset=9))

README = """WHITE ALBUM2 幸せの向こう側（PS3 / BLJM60571）粵語化補丁 {ver}

內容：IC 全篇（二周目分支在內）同外傳「雪が解け、そして雪が降るまで」。
譯文採集自網上公開嘅粵語字幕影片；外傳譯文採集自 raymondsakura 嘅公開 YouTube 頻道。
PS3 版新增或改寫、而字幕冇嘅台詞（約 160 句）仍然係日文。

需要：
  - 已解鎖嘅 PS3（HEN 或 CFW），同文件版遊戲（BLJM60571）
  - 官方 1.01 更新（裝好之後 /dev_hdd0/game/BLJM60571/USRDIR/EBOOT.BIN 先會出現）
  - 電腦上有 Python 3（python.org，裝嗰陣勾選 Add to PATH）
  - scetool（連同佢嘅 data 文件夾），自行準備

步驟：
  1. 將遊戲文件夾入面 PS3_GAME/USRDIR/data.dar 複製到 input 文件夾
  2. 將 PS3 上 /dev_hdd0/game/BLJM60571/USRDIR/EBOOT.BIN（1.01 更新）複製到 input 文件夾
  3. 將 scetool.exe 同佢嘅 data 文件夾放入 scetool 文件夾
  4. 雙擊「安裝補丁.bat」
  5. 將 input\\data.dar 放返去遊戲文件夾 PS3_GAME/USRDIR/
     將 output\\EBOOT.BIN 放返去 /dev_hdd0/game/BLJM60571/USRDIR/
     兩個文件一定要一齊換。

注意：
  - FTP 傳 data.dar（約 1.9GB）請用二進制模式。
  - 舊存檔入面嘅回放記錄會顯示亂碼，屬正常；新顯示嘅句子唔受影響。
  - 想還原 data.dar：雙擊「還原data.dar.bat」。
  - RPCS3 未測試。
"""
BAT = r"""@echo off
chcp 65001 >nul
setlocal
set "BASE=%~dp0"
set "PY="
for %%C in ("py -3" "python" "python3") do (
  if not defined PY ( %%~C -c "import lzma" >nul 2>nul && set "PY=%%~C" )
)
if not defined PY (
  for /d %%P in ("%LOCALAPPDATA%\Programs\Python\Python3*" "%LOCALAPPDATA%\Python\pythoncore-*") do (
    if not defined PY ( if exist "%%P\python.exe" ( "%%P\python.exe" -c "import lzma" >nul 2>nul && set PY="%%P\python.exe" ) )
  )
)
if not defined PY ( echo [錯誤] 搵唔到 Python 3，請先安裝 python.org 嘅 Python 3。 & goto :end )
%PY% "%BASE%patch\apply.py" {args}
:end
echo.
pause
"""

def main(ver="v0.1"):
    B = os.path.join(paths.WORK, "build")
    src = open(paths.EBOOT_101, "rb").read(); dst = open(os.path.join(B, "EBOOT.elf"), "rb").read()
    kit = os.path.join(paths.OUTPUT, "release", "WA2_PS3_Cantonese_" + ver)
    if os.path.exists(kit): shutil.rmtree(kit)
    for d in ("patch", "input", "scetool", "output"): os.makedirs(os.path.join(kit, d))
    print("diffing EBOOT ..."); diff = wa2d_encode(src, dst)
    open(os.path.join(kit, "patch", "EBOOT.wa2d"), "wb").write(diff)
    for f in ("02309.elzma", "02309.size"): shutil.copyfile(os.path.join(B, f), os.path.join(kit, "patch", f))
    here = os.path.dirname(os.path.abspath(__file__))
    shutil.copyfile(os.path.join(here, "release", "apply.py"), os.path.join(kit, "patch", "apply.py"))
    # check the diff round-trips with the patcher's own decoder
    spec = importlib.util.spec_from_file_location("apply", os.path.join(kit, "patch", "apply.py")); ap = importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
    assert ap.wa2d_apply(src, diff) == dst
    open(os.path.join(kit, "說明.txt"), "w", encoding="utf-8-sig").write(README.format(ver=ver))
    open(os.path.join(kit, "安裝補丁.bat"), "w", encoding="utf-8", newline="\r\n").write(BAT.replace("{args}", ""))
    open(os.path.join(kit, "還原data.dar.bat"), "w", encoding="utf-8", newline="\r\n").write(BAT.replace("{args}", "--undo"))
    for d, t in (("input", "把 data.dar 同官方 1.01 更新嘅 EBOOT.BIN 放喺呢度。"), ("scetool", "把 scetool.exe 同佢嘅 data 文件夾放喺呢度。"),
                 ("output", "生成嘅 EBOOT.BIN 會喺呢度。")):
        open(os.path.join(kit, d, "放喺呢度.txt"), "w", encoding="utf-8-sig").write(t + "\n")
    z = kit + ".zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(kit):
            for f in files:
                p = os.path.join(root, f); zf.write(p, os.path.relpath(p, os.path.dirname(kit)))
    print("diff %d bytes; kit %s; zip %d bytes" % (len(diff), kit, os.path.getsize(z)))

if __name__ == "__main__": main(*sys.argv[1:2])
