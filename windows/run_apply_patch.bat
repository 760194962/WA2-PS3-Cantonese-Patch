@echo off
setlocal
set "BASE=%~dp0"
set "PY="
for %%C in ("py -V:3.14" "py -3" "python" "python3" "py -V:3.11" "py -3.13" "py -3.12" "py -3.10") do (
  if not defined PY (
    %%~C -c "import lzma" >nul 2>nul && set "PY=%%~C"
  )
)
if not defined PY (
  for /d %%P in ("%LOCALAPPDATA%\Python\pythoncore-*" "%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if not defined PY (
      if exist "%%P\python.exe" (
        "%%P\python.exe" -c "import lzma" >nul 2>nul && set PY="%%P\python.exe"
      )
    )
  )
)
if not defined PY (
  echo [ERROR] No working Python 3 found.
  echo         Tip: run "py -0p" in a terminal, then check which paths really exist.
  goto :end
)
echo Using: %PY%
%PY% --version
echo.
%PY% "%BASE%patch_data_dar.py" "%BASE%.."
:end
echo.
echo Done. Press any key to close.
pause >nul
