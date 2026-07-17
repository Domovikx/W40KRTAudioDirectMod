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
| **Qwen3-TTS** 🏆 | Офлайн | 9 (5М+4Ж) | `tools/qwen3_tts.py` | `config/default.yaml` → `qwen3_*` |
| **Silero** | Офлайн | 5 (2М+3Ж) | `tools/silero_tts.py` | `config/default.yaml` → `silero_*` |
| **Gemini TTS** | Онлайн | 30 (15М+15Ж) | `tools/gemini_tts.py` | `config/default.yaml` → `gemini_*` |
| **Edge-TTS** | Онлайн | 2 (1М+1Ж) | `tools/edge_tts.py` | `config/default.yaml` → `edge_*` |
| SAPI | Офлайн | 2 (1М+1Ж) | — | `config/default.yaml` → `sapi_*` |

Активный бэкенд: `config/default.yaml` → `backend` (silero | gemini | edge | sapi | qwen3).

### Gemini voices распределение

См. `config/characters.yaml` → поле `gemini_voice`. Ключевые пары: Ключевые пары:
- `Kore` (F, Firm) → Теодора
- `Sadaltager` (M, Knowledgeable) → Кунрад
- `Algenib` (M, Gravelly) → Абеляр
- `Charon` (M, Informative) → Хайнрикс
- `Orus` (M, Firm) → Ульфар, Соломон
- `Schedar` (M, Even) → Паскаль
- `Gacrux` (F, Mature) → Идира
- `Laomedeia` (F, Upbeat) → Арджента
- `Aoede` (F, Breezy) → Джаэ
- `Sulafat` (F, Warm) → Кассия

### Qwen3 voices распределение

См. `.opencode/skills/qwen3-tts/SKILL.md`. Ключевые пары:
- `Ryan` (M, Dynamic) → **Кунрад**, Паскаль, Хайнрикс
- `Dylan` (M, Youthful) → Эдельтрад
- `Vivian` (F, Bright) → **Теодора**, Арджента
- `Serena` (F, Warm) → Кассия
- `Sohee` (F, Rich) → Джаэ
- `Uncle_Fu` (M, Mellow) → Абеляр, Ульфар

### Распределение голосов (Silero)

См. `config/characters.yaml`.

| Голос | Пол | Характер | Кому |
|-------|-----|----------|------|
| `eugene` | М | Командный | Абеляр, Маражай, Ульфар, Соломон |
| `aidar` | М | Спокойный | Кунрад, Хайнрикс, Паскаль, Эдельтрад |
| `xenia` | Ж | Энергичный | Теодора, Идира, Арджента, Кибелла |
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

## Full ICL Pipeline (Qwen3-TTS Base + VoiceClone)

Генерация реплик через Voice Clone (Base модель + референс от VoiceDesign).

```
VoiceDesign → refs/{voice}_reference.wav + .txt  (tools/qwen3_voice_design.py)
Base model → create_voice_clone_prompt() → VoiceClonePromptItem
Base model → generate_voice_clone(text, prompt) → output/full_icl/{voice}/*.wav
```

Скрипт: `tools/qwen3_full_icl.py` — читает `config/voices.yaml` + `catalog/people/*.yaml`.
Скилл: `.opencode/skills/qwen3-full-icl/SKILL.md`.
Дока: `docs/qwen3-tts.md` → раздел Full ICL Pipeline.

## Референсы

- SpeechMod: `https://github.com/Osmodium/W40KRogueTraderSpeechMod`
- Движки: см. `.opencode/skills/russian-tts/SKILL.md`, `.opencode/skills/gemini-tts/SKILL.md`
- SSML: см. `.opencode/skills/ssml-builder/SKILL.md`
- VoiceDesign: см. `.opencode/skills/qwen3-voice-design/SKILL.md`
- Full ICL: см. `.opencode/skills/qwen3-full-icl/SKILL.md`
- Голоса: см. `catalog/people/*.yaml`
- Конфиги: см. `config/default.yaml`, `config/voices.yaml`
- Каталог фраз: см. `.opencode/skills/text-catalog/SKILL.md`, файлы в `catalog/people/`
