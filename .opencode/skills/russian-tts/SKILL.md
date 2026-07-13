---
name: russian-tts
description: Generate Russian voiceover WAV files using Windows SAPI TTS for the W40KRTAudioDirectMod. Uses PowerShell to invoke System.Speech.SpeechSynthesizer and saves PCM WAV files playable via winmm.dll PlaySound.
---

## What I do
- Generate Russian TTS audio WAV files for dialog lines in the W40K Rogue Trader mod
- Auto-adjust speaking rate to fit cutscene/dialog timing without pitch distortion
- Use Windows built-in SAPI voices (Microsoft Dmitry Online male, Microsoft Svetlana Online female)
- Place WAV files at `clips/{GUID}.wav` for automatic mod pickup

## How timing works
Cutscene texts have a fixed display duration. If audio is longer than the text display time, it gets cut off. The script auto-adjusts `Rate` (speaking speed) to fit:

1. Generate at normal speed (Rate=0)
2. Measure duration from WAV header
3. If too long, calculate optimal Rate
4. Regenerate with estimated Rate
5. Verify and iterate if needed

**Rate vs Duration guide** (Dmitry Online, ~35-40 chars text):
- Rate=0: normal (baseline)
- Rate=1: ~83% of baseline
- Rate=2: ~72% of baseline
- Rate=4: ~56% of baseline

**Rate only affects speed, NOT pitch** — no chipmunk effect.

## Voices available
- `Microsoft Dmitry Online` — male, ru-RU (formal/document narration)
- `Microsoft Svetlana Online` — female, ru-RU

## Usage
### Basic (fixed Rate):
```powershell
powershell -ExecutionPolicy Bypass -File "scripts/tts_wav.ps1" `
  -Text "текст для озвучки" `
  -Output "clips\93eaeadd-6adb-47aa-af0d-45e37840a92d.wav" `
  -Voice "Microsoft Dmitry Online" `
  -Rate 0
```

### With auto-timing (recommended):
```powershell
powershell -ExecutionPolicy Bypass -File "scripts/tts_wav.ps1" `
  -Text "текст" `
  -Output "clips\GUID.wav" `
  -Voice "Microsoft Dmitry Online" `
  -TargetDuration 8.5
```

Script will generate at Rate=0 first, measure duration, then auto-adjust Rate to hit ~8.5s.

## Finding target duration
Timings come from cutscene blueprints (.jbp — binary, not human-readable). Best way to measure:
1. Play the scene, check GameLogFull.txt timestamps between text appearances
2. Or generate at Rate=0, play in game, see if it cuts off, then adjust with -TargetDuration

## Mod integration
- WAV must be PCM 16-bit mono (any sample rate)
- Filename = dialog GUID + .wav
- Place in `clips/` folder next to the mod DLL
- Mod catches text display via `TMP_Text.set_text` prefix — no recompilation needed for new WAVs
