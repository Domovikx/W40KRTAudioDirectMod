@echo off
set MANAGED=C:\PROGRA~2\Steam\STEAMA~1\common\WARHAM~1\WH40KR~1\Managed
set MODDIR=C:\Users\Domo\AppData\LocalLow\OWLCAT~1\WARHAM~1\UNITYM~1\W40KRTAudioDirectMod
set UMMDIR=C:\Users\Domo\AppData\LocalLow\OWLCAT~1\WARHAM~1\UNITYM~1

C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe -target:library ^
  -out:"%MODDIR%\W40KRTAudioDirectMod.dll" ^
  -reference:"%MANAGED%\mscorlib.dll" ^
  -reference:"%MANAGED%\System.dll" ^
  -reference:"%MANAGED%\System.Core.dll" ^
  -reference:"%MANAGED%\UnityEngine.dll" ^
  -reference:"%MANAGED%\UnityEngine.CoreModule.dll" ^
  -reference:"%MANAGED%\UnityEngine.AudioModule.dll" ^
  -reference:"%MANAGED%\UnityEngine.UnityWebRequestModule.dll" ^
  -reference:"%MANAGED%\UnityEngine.UnityWebRequestAudioModule.dll" ^
  -reference:"%MANAGED%\0Harmony.dll" ^
  -reference:"%UMMDIR%\UnityModManager.dll" ^
  "%MODDIR%\Main.cs" 2>&1
