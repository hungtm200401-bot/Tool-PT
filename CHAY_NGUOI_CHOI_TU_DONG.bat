@echo off
title PHONG THAN - AI NGUOI CHOI AM HIEU TU DONG CHOI GAME (V2.0)
cd /d "%~dp0"
echo =======================================================================
echo   PHONG THAN - HE THONG AI NGUOI CHOI AM HIEU TU DONG CHOI GAME (V2.0)
echo   Chuc nang:
echo     - Tu lam chuoi nhiem vu cot truyen (Bach Ly, Ngo That)
echo     - Tu tim duong den NPC va doi thoai
echo     - Tu danh quai tan thu, tung chieu thuc ID 2
echo     - Tu dong can thuoc va rut ve tiep te khi mau/mana duoi 50%%
echo     - Giam sat do hoa ngam chong den map
echo   Ket noi: LDPlayer emulator-5554 qua ADB E:\LDPlayer\LDPlayer9\adb.exe
echo =======================================================================

set PYTHON_BIN="C:\Users\ADMIN\AppData\Local\Programs\Python\Python312\python.exe"
if exist %PYTHON_BIN% (
    %PYTHON_BIN% main.py --agent
) else (
    python main.py --agent
)
echo.
echo =======================================================================
echo   PHIEN CHOI GAME KET THUC.
echo =======================================================================
pause
