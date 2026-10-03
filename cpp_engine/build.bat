@echo off
setlocal

echo [cpp_engine] Building fretboard_math shared library...

:: Check for g++ in PATH or scoop
where g++ >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set CXX=g++
) else if exist "%USERPROFILE%\scoop\apps\gcc\current\bin\g++.exe" (
    set "CXX=%USERPROFILE%\scoop\apps\gcc\current\bin\g++.exe"
) else (
    echo Error: g++ compiler not found.
    exit /b 1
)

echo Using compiler: %CXX%
cd /d "%~dp0"

%CXX% -O3 -Wall -Wextra -std=c++17 -shared -fPIC -DFRETENGINE_EXPORTS ^
    fretboard_math.cpp ^
    -Wl,--out-implib,libfretboard_math.a ^
    -o fretboard_math.dll

if %ERRORLEVEL% equ 0 (
    echo [cpp_engine] Build succeeded: %~dp0fretboard_math.dll
) else (
    echo [cpp_engine] Build failed with error code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

endlocal
