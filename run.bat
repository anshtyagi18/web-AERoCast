@echo off
setlocal enabledelayedexpansion
title AeroCast Launcher

cd /d "%~dp0"
if exist "AeroCast\run.bat" (
    cd AeroCast
    call run.bat
) else (
    call run.bat
)
