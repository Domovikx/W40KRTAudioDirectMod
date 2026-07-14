# W40KRTAudioDirectMod — Замена английской озвучки на русскую AI-озвучку

Замена английских диалоговых реплик в Warhammer 40K: Rogue Trader на русскую озвучку (AI-голос / TTS).

## Статус генерации

- **Сгенерировано WAV:** ~150 (36 Кунрад + 76 Теодора + 40 Эдельтрад)
- **Движок:** Silero v5_5_ru (48kHz) | **Активный бэкенд:** silero

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

## TTS Engine Architecture

Справочник движков: `.opencode/skills/russian-tts/SKILL.md`

| Движок | Тип | Голоса | Дока | Конфиг |
|--------|-----|--------|------|--------|
| **Silero** 🏆 | Офлайн | 5 (2М+3Ж) | `tools/silero_tts.py` | `config/default.yaml` → `silero_*` |
| **Edge-TTS** | Онлайн | 2 (1М+1Ж) | `tools/edge_tts.py` | `config/default.yaml` → `edge_*` |
| SAPI | Офлайн | 2 (1М+1Ж) | — | `config/default.yaml` → `sapi_*` |

Активный бэкенд: `config/default.yaml` → `backend`.

### Распределение голосов

См. `config/characters.yaml` (полный список, rationale, возраст, характер).

| Голос | Пол | Характер | Кому |
|-------|-----|----------|------|
| `eugene` | М | Командный | Абеляр, Маражай, Ульфар, Соломон |
| `aidar` | М | Спокойный | **Кунрад**, Хайнрикс, Паскаль, Эдельтрад |
| `xenia` | Ж | Энергичный | **Теодора**, Идира, Арджента, Кибелла |
| `baya` | Ж | Тёплый | Кассия, Йрлиет |
| `kseniya` | Ж | Звонкий | Джаэ |

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

## Референсы

- SpeechMod: `https://github.com/Osmodium/W40KRogueTraderSpeechMod`
- Движки: см. `.opencode/skills/russian-tts/SKILL.md`
- SSML: см. `.opencode/skills/ssml-builder/SKILL.md`
- Голоса: см. `config/characters.yaml`
- Конфиги: см. `config/default.yaml`
