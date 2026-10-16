@echo off
setlocal
rem update-only (HEN refuses disc-folder EBOOTs: 80010009). v3: sign with key revision 01 (FW 3.40-era NPDRM keys, same parameters as scetool\eboot_fix.bat),
rem so the signature is fully valid and HEN does not need to bypass anything.
set "BASE=%~dp0"
if not exist "%BASE%scetool\scetool.exe" (echo [ERROR] put scetool.exe and its data folder into "%BASE%scetool\" & goto :end)
set "PAT=%BASE%EBOOT.elf"
set "OUT=%BASE%ps3_npdrm_v3"
if not exist "%OUT%\update_patched" mkdir "%OUT%\update_patched"
set "COMMON=--sce-type=SELF --compress-data=TRUE --skip-sections=TRUE --key-revision=01 --self-auth-id=1010000001000003 --self-app-version=0001000000000000 --self-add-shdrs=TRUE --self-vendor-id=01000002 --self-type=NPDRM --self-fw-version=0003004000000000 --np-license-type=FREE --np-real-fname=EBOOT.BIN"
set "UPD=--np-app-type=UEXEC --np-content-id=JP0761-BLJM60571_00-GAMEUPDATE000001"
pushd "%BASE%scetool"
echo === update_patched
scetool.exe %COMMON% %UPD% --encrypt "%PAT%" "%OUT%\update_patched\EBOOT.BIN"
popd
echo.
dir /s "%OUT%\*.BIN"
:end
echo.
echo Press any key to close.
pause >nul
