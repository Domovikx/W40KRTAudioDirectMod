# W40KRTAudioDirectMod — Замена английской озвучки на русскую AI-озвучку

Замена английских диалоговых реплик в Warhammer 40K: Rogue Trader на русскую озвучку (AI-голос / TTS).

## Статус генерации

- **Сгенерировано WAV:** ~150 (36 Кунрад + 76 Теодора + 40 Эдельтрад) — Qwen3-TTS (24000 Гц)

## Путь к игре

```
C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40,000 Rogue Trader
```

## Путь к моду

```
%userprofile%\AppData\LocalLow\Owlcat Games\Warhammer 40000 Rogue Trader\UnityModManager\W40KRTAudioDirectMod
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

## Full ICL Pipeline (Qwen3-TTS Base + VoiceClone)

Генерация реплик через Voice Clone (Base модель + референс).
Маппинг speaker → voice reference — через `config/voices.yaml` (поле `characters:`).

```
Base model → create_voice_clone_prompt(ref_audio, x_vector_only_mode=True) → VoiceClonePromptItem
Base model → generate_voice_clone(text, prompt) → output/full_icl/{voice}/*.wav
```

Скрипт: `tools/qwen3_full_icl.py` — читает `config/voices.yaml` + `catalog/people/*.yaml` (формат с `parts: [{speaker, text_clean}]`).
Склейка частей: `.opencode/skills/qwen3-full-icl/concat_parts.py`.
Скилл: `.opencode/skills/qwen3-full-icl/SKILL.md`.

Формат `catalog/people/*.yaml`:

```yaml
name: Кунрад Войгтвир
phrases:
  - guid: ...
    parts:
      - speaker: Kunrad Voigtvir # маппится через voices.yaml.characters
        text_clean: ...
      - speaker: narrator # специальное имя → wh40k_narrator
        text_clean: ...
```

Голоса: `config/voices.yaml` — каждый entry содержит `characters: [список спикеров]`.
Маппинг speaker → voice работает автоматически по совпадению имени спикера.

Выход: `output/full_icl/{voice_name}/{guid}__{N}.wav` + `{guid}.wav` (склейка).

## Референсы

- SpeechMod: `https://github.com/Osmodium/W40KRogueTraderSpeechMod`
- Full ICL: `.opencode/skills/qwen3-full-icl/SKILL.md`, `tools/qwen3_full_icl.py`
- Каталог фраз: `.opencode/skills/text-catalog/SKILL.md`, файлы в `catalog/people/`
- Голоса: `config/voices.yaml`, `catalog/people/*.yaml`
- Референсы голосов: `.opencode/skills/voice-ref-collect/SKILL.md`, `refs/samples/`
- Конфиги: `config/default.yaml`

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
