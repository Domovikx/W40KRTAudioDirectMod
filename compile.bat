@echo off
set MANAGED=C:\PROGRA~2\Steam\STEAMA~1\common\WARHAM~1\WH40KR~1\Managed
set MODDIR=C:\Users\Domo\AppData\LocalLow\OWLCAT~1\WARHAM~1\UNITYM~1\W40KRTAudioDirectMod
set UMMDIR=C:\Users\Domo\AppData\LocalLow\OWLCAT~1\WARHAM~1\UNITYM~1

C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe -target:library -nologo ^
  -out:"%MODDIR%\W40KRTAudioDirectMod.dll" ^
  -reference:"%MANAGED%\netstandard.dll" ^
  -reference:"%MANAGED%\Newtonsoft.Json.dll" ^
  -reference:"%MANAGED%\UnityEngine.dll" ^
  -reference:"%MANAGED%\UnityEngine.CoreModule.dll" ^
  -reference:"%MANAGED%\UnityEngine.IMGUIModule.dll" ^
  -reference:"%MANAGED%\UnityEngine.TextRenderingModule.dll" ^
  -reference:"%MANAGED%\UnityEngine.UI.dll" ^
  -reference:"%MANAGED%\0Harmony.dll" ^
  -reference:"%UMMDIR%\UnityModManager.dll" ^
  "%MODDIR%\Main.cs"
