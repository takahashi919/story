@echo off
chcp 65001 > nul

set BASE=%USERPROFILE%\OneDrive\Documents\anime_seisaku

mkdir "%BASE%" 2>nul
mkdir "%BASE%\references" 2>nul
mkdir "%BASE%\stories" 2>nul
mkdir "%BASE%\progress" 2>nul
mkdir "%BASE%\exports\docx" 2>nul

echo [OK] Folder created: %BASE%

if exist "%~dp0CLAUDE.md" (
    copy "%~dp0CLAUDE.md" "%BASE%\CLAUDE.md" > nul
    echo [OK] CLAUDE.md copied
) else (
    echo [!!] CLAUDE.md not found
)

if exist "%~dp0progress_note.md" (
    copy "%~dp0progress_note.md" "%BASE%\progress\progress_note.md" > nul
    echo [OK] progress_note.md not found
)

echo.
echo Setup complete!
echo Location: %BASE%
echo.
pause
