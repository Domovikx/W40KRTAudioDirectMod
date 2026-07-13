# W40KRTAudioDirectMod — Замена английской озвучки на русскую AI-озвучку

Замена английских диалоговых реплик в Warhammer 40K: Rogue Trader на русскую озвучку (AI-голос / TTS).

## Путь к игре

```
C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40,000 Rogue Trader
```

## Путь к моду

```
%userprofile%\AppData\LocalLow\Owlcat Games\Warhammer 40000 Rogue Trader\UnityModManager\W40KRTAudioDirectMod
```

## Структура мода

```
W40KRTAudioDirectMod/
  Main.cs           — Исходник мода (C#)
  AGENTS.md         — Память проекта
  Info.json         — Манифест UnityModManager
  W40KRTAudioDirectMod.dll — Скомпилированный мод
  Settings.xml      — Настройки (Volume, Language)
  Localization/
    ruRU/           — WAV аудиофайлы для русского языка (названы по GUID)
    (другие языки — enGB/, deDE/, frFR/ и т.д.)
  .opencode/
    skills/
      russian-tts/  — Скил для генерации аудио
        SKILL.md
        scripts/tts_wav.ps1
```

## Как это работает

### Воспроизведение аудио

- Используется `winmm.dll mciSendString()` — играет WAV через Windows Multimedia API
- Поддерживается регулировка громкости
- Файл копируется во временную папку перед воспроизведением

### Выбор языка

- Язык задаётся в настройках (поле `Language` в Settings.xml, по умолчанию `ruRU`)
- WAV файлы ищутся в `Localization\{Language}\`
- JSON локализация игры: `{Language}.json`

### Отслеживание текста (триггеры)

1. **`DialogVM.HandleOnCueShow`** (через `[HarmonyPatch]`) — ловит GUID реплик в диалогах
2. **`TMP_Text.set_text`** (патч ставится на 1-м кадре в OnUpdate) — ловит ЛЮБОЙ текст на экране через TextMeshPro
3. **GUID → WAV сопоставление** — если GUID текста есть в словаре, играет соответствующую WAV

## Доступные языки в игре

- `ruRU`, `enGB`, `deDE`, `frFR`, `esES`, `jaJP`, `zhCN`, `trTR`

## Компиляция

```bash
MANAGED="C:/Program Files (x86)/Steam/steamapps/common/Warhammer 40,000 Rogue Trader/WH40KRT_Data/Managed"
UMM="C:/Users/Domo/AppData/LocalLow/Owlcat Games/Warhammer 40000 Rogue Trader/UnityModManager"

csc -target:library -out:W40KRTAudioDirectMod.dll \
  -reference:"$MANAGED/netstandard.dll" \
  -reference:"$MANAGED/UnityEngine.dll" \
  -reference:"$MANAGED/UnityEngine.CoreModule.dll" \
  -reference:"$MANAGED/UnityEngine.TextRenderingModule.dll" \
  -reference:"$MANAGED/UnityEngine.UI.dll" \
  -reference:"$MANAGED/UnityEngine.IMGUIModule.dll" \
  -reference:"$MANAGED/0Harmony.dll" \
  -reference:"$UMM/UnityModManager.dll" \
  Main.cs
```

## Генерация аудио

```powershell
powershell -ExecutionPolicy Bypass -File ".opencode/skills/russian-tts/scripts/tts_wav.ps1" `
  -Text "текст" -Output "Localization\ruRU\GUID.wav" `
  -Voice "Microsoft Dmitry Online" -TargetDuration 8.5
```

## Голоса SAPI (доступны в системе)

- `Microsoft Dmitry Online` — мужской, ru-RU
- `Microsoft Svetlana Online` — женский, ru-RU

## Референсы

- SpeechMod (исходники): `https://github.com/Osmodium/W40KRogueTraderSpeechMod`
- SpeechMod на Nexus: `https://www.nexusmods.com/warhammer40kroguetrader/mods/75`
