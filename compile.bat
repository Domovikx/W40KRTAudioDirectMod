@echo off
setlocal enabledelayedexpansion

set MANAGED=C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40,000 Rogue Trader\WH40KRT_Data\Managed
set UMM=C:\Users\Domo\AppData\LocalLow\Owlcat Games\Warhammer 40000 Rogue Trader\UnityModManager
set CSC="C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

%CSC% -nologo -target:library -out:W40KRTAudioDirectMod.dll -reference:"%MANAGED%\netstandard.dll" -reference:"%MANAGED%\Newtonsoft.Json.dll" -reference:"%MANAGED%\UnityEngine.dll" -reference:"%MANAGED%\UnityEngine.CoreModule.dll" -reference:"%MANAGED%\UnityEngine.TextRenderingModule.dll" -reference:"%MANAGED%\UnityEngine.UI.dll" -reference:"%MANAGED%\UnityEngine.IMGUIModule.dll" -reference:"%MANAGED%\0Harmony.dll" -reference:"%UMM%\UnityModManager.dll" Main.cs

if errorlevel 1 (
    echo Compilation failed
    pause
    exit /b
)

echo.
echo ===== Compiled successfully! =====
echo.
if exist "W40KRTAudioDirectMod.dll.cache" del "W40KRTAudioDirectMod.dll.cache"
pause
