@echo off
title KIEM CHUNG HANH VI GIAI DOAN 3 (PILOT LDPLAYER)
cd /d "%~dp0"
echo =======================================================================
echo   CHAY PHIEN KIEM CHUNG HANH VI GIAI DOAN 3 (P3-01, P3-02, P3-09)
echo   Ket noi LDPlayer emulator-5554 qua ADB E:\LDPlayer\LDPlayer9\adb.exe
echo   Kiem tra: GameState, 2 Quest Cocos UI, Ngưỡng tự dùng thuốc 50%%
echo =======================================================================

set PYTHON_BIN="C:\Users\ADMIN\AppData\Local\Programs\Python\Python312\python.exe"
if exist %PYTHON_BIN% (
    %PYTHON_BIN% scripts\run_phase3_behavior_sessions.py
) else (
    python scripts\run_phase3_behavior_sessions.py
)
echo.
echo =======================================================================
echo   HOAN TAT PHIEN KIEM CHUNG. Xem JSON tai reports\phase3_runs\
echo =======================================================================
pause
