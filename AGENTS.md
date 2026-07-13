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
  AGENTS.md         — Этот файл (память проекта)
  Info.json         — Манифест UnityModManager
  W40KRTAudioDirectMod.dll — Скомпилированный мод
  clips/            — WAV аудиофайлы (названы по GUID)
  .opencode/
    skills/
      russian-tts/  — Скил для генерации аудио
        SKILL.md
        scripts/tts_wav.ps1
```

## Как это работает

### Воспроизведение аудио

- Используется `winmm.dll PlaySound()` — играет WAV через Windows Audio, в обход Unity
- `SND_ASYNC` — асинхронно (не блокирует игру)
- Unity AudioSource/AudioClip не используется — они сломаны в Unity 6000.0.641 (ReadOnlySpan, SetData=false)

### Отслеживание текста (триггеры)

Три перехвата ловят появление текста в диалогах и катсценах:

1. **`DialogVM.HandleOnCueShow`** (через `[HarmonyPatch]`) — ловит GUID реплик в диалогах
2. **`TMP_Text.set_text`** (патч ставится на 1-м кадре в OnUpdate) — ловит ЛЮБОЙ текст на экране через TextMeshPro
3. **GUID → WAV сопоставление** — если GUID текста есть в словаре, играет соответствующую WAV

### Почему не PostEvent?

Диалоговая озвучка НЕ играется через `AkSoundEngine.PostEvent(string, GameObject)`. Аудио загружено из Wwise SoundBank (.bnk) и воспроизводится через внутренний механизм. Мы перехватываем отображение текста на UI.

### GUID → Ивент

Маппинг в `Sound.json`:

```
WH40KRT_Data\StreamingAssets\Localization\Sound.json
```

Формат: `"GUID": { "Offset": 0, "Text": "EventName" }`

## Компиляция

```bash
MANAGED="C:/Program Files (x86)/Steam/steamapps/common/Warhammer 40,000 Rogue Trader/WH40KRT_Data/Managed"
UMM="C:/Users/Domo/AppData/LocalLow/Owlcat Games/Warhammer 40000 Rogue Trader/UnityModManager"

csc -target:library -out:W40KRTAudioDirectMod.dll \
  -reference:"$MANAGED/netstandard.dll" \
  -reference:"$MANAGED/UnityEngine.dll" \
  -reference:"$MANAGED/UnityEngine.CoreModule.dll" \
  -reference:"$MANAGED/0Harmony.dll" \
  -reference:"$UMM/UnityModManager.dll" \
  Main.cs
```

## Текущие диалоговые реплики

| GUID                                   | Текст (русский)                      | Сцена                 | WAV       |
| -------------------------------------- | ------------------------------------ | --------------------- | --------- |
| `93eaeadd-6adb-47aa-af0d-45e37840a92d` | Скрип, который издает сервочереп...  | Диалог с сервочерепом | ✅        |
| `36a60f39-1962-464e-8bdc-ea78e5559370` | Да будет известно, что волей моей... | Катсцена (документ)   | ✅ Rate=1 |
| `7d7fdde5-2ea2-4194-b0c5-b1b672268fbc` | ...быть ослепительным примером...    | Катсцена (документ)   | ✅ Rate=1 |
| `9e22eda7-5e0c-4bd0-aff6-5e535872b847` | ...возвыситься над невыразимыми...   | Катсцена (документ)   | ✅ Rate=0 |

## Генерация аудио

```powershell
# С авто-подбором длительности (рекомендуется):
powershell -ExecutionPolicy Bypass -File ".opencode/skills/russian-tts/scripts/tts_wav.ps1" `
  -Text "текст" -Output "clips\GUID.wav" `
  -Voice "Microsoft Dmitry Online" -TargetDuration 8.5

# Простая генерация:
powershell -ExecutionPolicy Bypass -File ".opencode/skills/russian-tts/scripts/tts_wav.ps1" `
  -Text "текст" -Output "clips\GUID.wav" `
  -Voice "Microsoft Dmitry Online" -Rate 1
```

### Как узнать TargetDuration

Запустить сцену, проверить тайминги в GameLogFull.txt между появлениями текста. Длительность = время*следующего*текста - время_текущего.

### Зависимость Rate от длительности (Dmitry Online)

- Rate=0: 100% (базово)
- Rate=1: ~83%
- Rate=2: ~72%
- Rate=4: ~56%

## Голоса SAPI (доступны в системе)

- `Microsoft Dmitry Online` — мужской, ru-RU (формальный, для документов)
- `Microsoft Svetlana Online` — женский, ru-RU

## Технические детали

- Unity: 6000.0.641
- Аудио: Wwise (.bnk файлы)
- UI: TextMeshPro (TMPro)
- Диалоги: `Kingmaker.Controllers.Dialog.DialogController`
- Барки катсцен: `CommandBarkEntity` → `BarkPlayer` (параметр `LocalizedString`, не `string`)
- Локализация: структура `Kingmaker.Localization.LocalizedString` с полем `Key` (GUID)
- Компилятор: .NET Framework 4.8 csc.exe (C# 5 — нет `?.`, `nameof`, `async/await`)
- Мод-менеджер: UnityModManager (форк Owlcat)

## Референсы

- SpeechMod (исходники): `https://github.com/Osmodium/W40KRogueTraderSpeechMod`
- SpeechMod на Nexus: `https://www.nexusmods.com/warhammer40kroguetrader/mods/75`
