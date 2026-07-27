# W40KRTAudioDirectMod — Техническая документация

## Статус генерации

- **Сгенерировано WAV:** ~169 (67 Кунрад + 102 Теодора)

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
3. **`BarkPlayer.Bark / BarkExploration`** (через `[HarmonyPatch]`, runtime) — ловит барки (всплывающие подписи при клике на объекты)
4. **GUID → WAV сопоставление** — если GUID текста есть в словаре, играет соответствующую WAV

#### Анти-флуд и авто-барки

- `OnTextSet` проверяет `Environment.StackTrace`: если вызов из `MapObjectOvertipsView` **без** `InteractionBarkPart.OnInteract` — это авто-барк от камеры (`UnitsProximityController`), звук НЕ играется
- `HandleBark` (из `BarkPlayer.Bark`) — всегда играет (только ручные клики)
- Per-GUID cooldown 10 секунд (`lastPlayedByGuid`)

### Определение спикера (каталог фраз)

**Двухстадийный метод в `generate_catalog.py::extract_speaker_from_event()`:**

1. **Primary (88.9%):** Парсинг Wwise event name из `Sound.json` — экстракция character-сегмента по паттерну префикса (BNTRS → segment[2], Companions → segment[1] + role→name map, PRL/CH1-3 → standalone token в сегментах, RMNC → search/fallback substring, и т.д.)
   - **Важно:** scene-start matching (PRL/CH1-3) НЕ используется — имя в названии сцены может быть subject'ом, а не speaker'ом (например, `PRL_TheodoraFirstConversation_*` — сцена РАЗГОВОРА с Теодорой, где спикеры: Абеляр, Эдельтрад и др.)
2. **Fallback (11.1%):** Парсинг `{n}...{/n}` narration blocks — поиск имени персонажа в начале блока, определение спикера по обращению к владельцу YAML + keyword fallback (синт-кож→Абеляр)

**Результат:** 4523/5089 (88.9%) фраз с точным speaker, 566 (11.1%) null (default = file owner). Null → narration fallback + default.

**Маппинг ролей Companions:** Smugler→Джаэ, Navigator→Кассия, Techpriest→Паскаль, Interrogator→Хайнрикс, Ranger→Йрлиет, Psyker→Идира, Sororitas→Арджента, Seneschal→Абеляр.

**Три категории фраз:**
1. **Sound.json events** (5089) — Wwise-ивент → маппинг через sound_keys
2. **Extra dialog** (ruRU-only, ~34319) — есть `"` или `{n}`, длина ≥50
3. **Описания окружения** (ruRU-only, ~N) — нет `"`, `{`, `<`, `[`, длина ≥50 → `catalog/people/Описания_окружения.yaml`

**Метаданные персонажей** — в каждом `catalog/people/*.yaml` (name, gender, role, sound_keys).

## Full ICL Pipeline (Qwen3-TTS Base + VoiceClone)

Генерация реплик через Voice Clone (Base модель + референс).
Маппинг speaker → voice reference — через `config/voices.yaml` (поле `characters:`).

```
Base model → create_voice_clone_prompt(ref_audio, x_vector_only_mode=True) → VoiceClonePromptItem
Base model → generate_voice_clone(text, prompt) → output/full_icl/{voice}/*.wav
```

Скрипт: `tools/qwen3_full_icl.py` — читает `config/voices.yaml` + `catalog/people/*.yaml` (формат с `parts: [{speaker, text_clean}]`).
Скилл: `.opencode/skills/qwen3-full-icl/SKILL.md`.

Фильтры: `--voice`, `--char`, `--guid guid1 guid2 ...`, `--force`.

Примеры:
```bash
# Все NPC
python tools/qwen3_full_icl.py --voice default_male

# Конкретные GUID
python tools/qwen3_full_icl.py --guid 000e97aa-... 001db7fa-... --force
```

Формат `catalog/people/*.yaml`:

```yaml
name: Kunrad Voigtvir
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
- Референсы голосов (оригинал англ.): `refs/samples_en/`
- Конфиги: `config/default.yaml`

## Ducking (приглушение)

Использует `AkSoundEngine.SetRTPCValue(string, float)` с реальными RTPC именами из игры:

- `"MusicLevel"` — громкость музыки
- `"DialogueLevel"` — громкость диалогов  
- `"VoiceLevel"` — громкость голосов
- `"SFXLevel"` — звуковые эффекты
- `"AmbienceLevel"` — окружение
- `"AudioLevel"` — мастер
- `"MuteEntity"` — мьют

Резерв: `AudioMuteManager.s_AllSoundMute` (static bool field, полный мьют).

SoundSettingsController (в `Code.dll`):
- `.ctor()` — без параметров
- `m_Settings` — `SoundSettings` (instance field)
- `SettingsToRealMasterVolume()` — читает m_Settings и применяет через Wwise
- `SettingsVoicesVolume(Single v)` — применяет голос напрямую

SoundSettings:
- Поля типа `SettingsEntityFloat`: `VolumeMaster`, `VolumeVoices`, `VolumeMusic`, `VolumeSfx`, `VolumeAmbience`, `VolumeVoicesDialogues`, `VolumeUI`, `VolumeAbilities`, `VolumeRangedWeapons`, `VolumeMeleeWeapons`, `VolumeHitsLevel`, `VolumeVoicesCharacterInGame`, `VolumeVoicesNpcInGame`

GameSettingsController НЕ имеет статического Instance. `get_SoundSettingsController`/`get_GameSettingsController` живут на неизвестном классе (не на `Kingmaker.Game`).

RTPCValues: static class со static string полями: `MuteEntity`, `PlaybackSpeed`, `CameraZoom`, `PartyBanterPositioning`, `WeatherIntensity`.

AudioMuteManager (static): `SetAllAudioMuteState()`, `SetMusicMuteState()`, `SetNoneState()`, `ToggleAllMute()`, `ToggleMusicMute()`, `UpdateState()`. Поля: `s_MusicMute`, `s_AllSoundMute`.

## Компиляция

```bash
compile.bat
```

Или вручную:

```bash
MANAGED="C:/Program Files (x86)/Steam/steamapps/common/Warhammer 40,000 Rogue Trader/WH40KRT_Data/Managed"
UMM="C:/Users/Domo/AppData/LocalLow/Owlcat Games/Warhammer 40000 Rogue Trader/UnityModManager"
csc -target:library -out:W40KRTAudioDirectMod.dll \
  -reference:"$MANAGED/netstandard.dll" \
  -reference:"$MANAGED/Newtonsoft.Json.dll" \
  -reference:"$MANAGED/UnityEngine.dll" \
  -reference:"$MANAGED/UnityEngine.CoreModule.dll" \
  -reference:"$MANAGED/UnityEngine.TextRenderingModule.dll" \
  -reference:"$MANAGED/UnityEngine.UI.dll" \
  -reference:"$MANAGED/UnityEngine.IMGUIModule.dll" \
  -reference:"$MANAGED/0Harmony.dll" \
  -reference:"$UMM/UnityModManager.dll" \
  Main.cs
```

## Голоса (config/voices.yaml)

21 голос — все оригинальные английские актёры из `refs/samples_en/`.

| Группа | Голоса |
|--------|--------|
| Компаньоны | `abelard`, `cassia`, `heinrix`, `pasqal`, `argenta`, `idira`, `jae`, `kibellah`, `yrliet`, `ulfar`, `marazhai`, `solomon` |
| Антагонисты | `kunrad`, `teodora`, `trazyn`, `edelthrad`, `eogann`, `manipulus` |
| NPC | `default_male`, `default_female` |
| Рассказчик | `wh40k_narrator` |
