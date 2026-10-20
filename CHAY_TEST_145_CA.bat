@echo off
title KIEM THU HOI QUY TU DONG PHONG THAN (145 CA)
cd /d "%~dp0"
echo =======================================================================
echo   CHAY TOAN BO 145 CA KIEM THU HOI QUY (PYTHON UNITTEST)
echo   Yeu cau: 145/145 PASS, 0 FAIL, 0 ERROR
echo =======================================================================

set PYTHON_BIN="C:\Users\ADMIN\AppData\Local\Programs\Python\Python312\python.exe"
if exist %PYTHON_BIN% (
    %PYTHON_BIN% -m unittest discover -s tests -v
) else (
    python -m unittest discover -s tests -v
)
echo.
echo =======================================================================
echo   HOAN TAT KIEM THU HOI QUY.
echo =======================================================================
pause
