# W40KRTAudioDirectMod — Техническая документация

## Правила для AI-агента

- **НИКОГДА не коммитить без явного разрешения пользователя.** Только explicit «коммить» / «commit» / «закоммитить». Редактировать, писать, компилировать — можно. `git commit` — только после review.
- По умолчанию все изменения остаются в рабочем дереве (staged или unstaged), не закоммиченными.

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

Схема «один класс контента = один семантический триггер»:

1. **Диалоги** — `DialogVM.HandleOnCueShow` (через `[HarmonyPatch]`) — ловит GUID реплик в диалогах
2. **Барки** — `BarkHandle..ctor` (runtime-патч в Load, постфикс с `string text`) — ровно один раз при СОЗДАНИИ барка (клик по объекту/NPC, скриптовые барки `ShowBark.RunAction`). Все пути барков проходят через этот конструктор — это единственная семантическая точка
3. **Не-барковый текст** — `TMP_Text.set_text` (патч ставится на 1-м кадре в OnUpdate) — журнал, кодекс, лог событий
4. **GUID → WAV сопоставление** — если GUID текста есть в словаре, играет соответствующую WAV

#### Анти-флуд (ре-рендеры, пан камеры)

- `OnTextSet` пропускает **любой барк-текст**: если в `Environment.StackTrace` есть `BarkBlockView` (все барковые TMP-установки идут через `Kingmaker.UI.MVVM.View.Bark.PC.BarkBlockView`) → SKIP. Это гасит повторные установки одного текста при пане камеры, ре-создании овертипов (`UnitOvertipsView`, `OvertipMapObjectInteractionView` и др.) — без перечисления имён вьюх
- `HandleBark` (из `BarkHandle..ctor`) — играет с per-GUID cooldown 10 секунд (`lastPlayedByGuid`)
- История: `BarkPlayer.Bark` патч не работал (фильтр `ReturnType == typeof(void)` + нерезолвимый параметр `____text`) — заменён на `BarkHandle..ctor`; хардкод `MapObjectOvertipsView` убран как избыточный
- Диагностика: `trigger_debug.log` (пересоздаётся при старте игры) — строки `BARK play/skip-cooldown`, `TEXT play/skip-barkdisplay/skip-cooldown`, `DIALOG cue`. Включение: `Main.TriggerLogEnabled = true` (в `Main.cs`, по умолчанию `false` — в проде выключено). Новые места логирования — просто `LogTrigger("...")`

### Определение спикера (каталог фраз)

**Двухстадийный метод в `generate_catalog.py::extract_speaker_from_event()`:**

1. **Primary (88.9%):** Парсинг Wwise event name из `Sound.json` — экстракция character-сегмента по паттерну префикса (BNTRS → segment[2], Companions → segment[1] + role→name map, PRL/CH1-3 → standalone token в сегментах, RMNC → search/fallback substring, и т.д.)
   - **Важно:** scene-start matching (PRL/CH1-3) НЕ используется — имя в названии сцены может быть subject'ом, а не speaker'ом (например, `PRL_TheodoraFirstConversation_*` — сцена РАЗГОВОРА с Теодорой, где спикеры: Абеляр, Эдельтрад и др.)
2. **Fallback (11.1%):** Парсинг `{n}...{/n}` narration blocks — поиск имени персонажа в начале блока, определение спикера по обращению к владельцу YAML + keyword fallback (синт-кож→Абеляр)

**Результат:** 4523/5089 (88.9%) фраз с точным speaker, 566 (11.1%) null (default = file owner). Null → narration fallback + default.

**Маппинг ролей Companions:** Smugler→Джаэ, Navigator→Кассия, Techpriest→Паскаль, Interrogator→Хайнрикс, Ranger→Йрлиет, Psyker→Идира, Sororitas→Арджента, Seneschal→Абеляр.

**Три категории фраз:**
1. **Sound.json events** (5089) — Wwise-ивент → маппинг через sound_keys
2. **Extra dialog** (ruRU-only, ~30630) — есть `"` или `{n}`, **без ограничений по длине**
3. **Ответы игрока** (ruRU-only, ~12221) — `BlueprintAnswer` из bbp → `catalog/people/Player_Answers.yaml` (`skip_voicing: true`, озвучка выключена оптом)

**Роли диалоговых GUID (answer/cue/unknown)** — `catalog/dialog_roles.yaml`, генерируется `tools/extract_dialog_roles.py` из `blueprints-pack.bbp`. Классификатор **байтовый**: в сериализации узла после 32-hex GUID идёт байт типа — `0x5B` = BlueprintAnswer (игрок), `0x45` = BlueprintCue (NPC). **Имя узла (`Answer_0001`) — не тип!** (фраза Абеляра в узле «Answer_5» с байтом `0x45` — cue). Правило: `0x45 в наборе → cue`; `0x5B → answer`; иначе unknown (в каталог, решает ревью). **Важно:** answer-фильтр применяется ТОЛЬКО к фразам без Sound.json event — озвученные реплики NPC могут сидеть в Answer-узлах (например, `TrazynOffer_Trazyn_01`), их нельзя удалять в Player_Answers.

**Маппинг для игры** — `Localization/{lang}/mappings.json` (`tools/export_mappings.py`): нормализованные `parts[].text_clean` (+ целая фраза) → WAV. Исключает `skip_voicing`. Мод играет по **exact-match** после нормализации (снятие TMP-тегов, игровой разметки, внешних кавычек) — коллизии подстрок невозможны.

**Skip-флаги**: `skip_voicing: true` на уровне файла (Player_Answers.yaml) или фразы — `qwen3_full_icl.py` и `export_mappings.py` их уважают.

**Метаданные персонажей** — в каждом `catalog/people/*.yaml` (name, gender, role, sound_keys).

## Определение спикера (Speaker Detection Pipeline)

Трёхуровневая система определения, кто говорит фразу:

1. **BBP / event name → tree owner** (базовый спикер) — загружается из `catalog/bbp_speakers.yaml` (бинарные данные игры) или из `extract_speaker_from_event()` (Wwise event name). Даёт **владельца диалогового дерева** (кто контролирует сцену), но не всегда per-line спикера.

2. **Self-address validation** (`_text_addresses_owner()`) — проверяет, не обращается ли текст к детектированному спикеру по имени или титулу (например, `"Мастер шепотов, что творится..."` → адресуется Кунраду → значит Кунрад НЕ спикер). При срабатывании → сброс на `None`.

3. **Text analysis** (`detect_speaker()`) — парсит `{n}...{/n}` narration blocks: если блок начинается с имени персонажа (из `config/name_map.yaml`), этот персонаж — спикер.

4. **Manual overrides** (`config/speaker_overrides.yaml`) — для фраз, где pipeline падает (нет narration, self-address сработал, но настоящий спикер неопределим). GUID → точный speaker вручную.

**Итоговая точность:** ~99.9% (4 ручных оверрайда на весь каталог).

**Ограничение:** BlueprintCue в `.bbp` хранит только **tree owner**, не per-line speaker. Per-line спикер — runtime-концепция игрового DialogSystem (стейт-машина переходов Cue→Answer→Cue). Извлечь его из статичных данных невозможно — это фундаментальное ограничение движка.

**Маппинг русских имён** — `config/name_map.yaml` (ru_aliases + title_aliases).

### Работа с speaker_override

`speaker_override` на уровне part — единственный способ переопределить спикера для фраз, где pipeline падает.

**ВАЖНО:** `speaker_override` может быть установлен только вручную. Автоматические скрипты (`merge_speakers.py`, `generate_catalog.py`) НЕ ДОЛЖНЫ создавать или изменять `speaker_override`. BBP-данные (tree owner) не являются per-line speaker и НЕ ИСПОЛЬЗУЮТСЯ для `speaker_override`.

Процесс:
1. `python tools/merge_speakers.py` — полная пересборка каталога: бэкап → `generate_catalog.py` → union-merge (старые parts сохраняются, speaker из нового) → удаление ответов игрока из персональных файлов → `Player_Answers.yaml` → `index.yaml`. Сопоставляет файлы по внутреннему `name` (не по имени файла). Имеет echo-метки прогресса (6 фаз)
2. Если фраза требует ручного оверрайда — добавить `speaker_override` в part вручную
3. `speaker_override` проверяется через `tools/test_pipeline.py::test_text_clean_no_formatting`
4. `regenerate_text_clean.py` сохраняет `speaker` и `speaker_override` (перенос по text_clean при пересоздании parts)
5. Если оверрайды всё же потеряны — `python tools/restore_overrides.py` восстанавливает их из `catalog/people_orig` (эталон, не удалять!)

### Запуск аудита

```bash
# Одного файла
python tools/audit_speakers.py --file catalog/people/Kunrad_Voigtvir.yaml

# Всех (кроме Generic_Male_NPC — медленно)
for f in catalog/people/*.yaml; do
  [[ "$f" == *"Generic_Male_NPC"* ]] && continue
  python tools/audit_speakers.py --file "$f"
done
```

Subagent-флоу описан в `.opencode/skills/speaker-audit/SKILL.md`.

## Gender-review пайплайн (проверка рода М/Ж перед озвучкой)

Трёхступенчатый ручной процесс с сабагентами:

1. **2-3 триера параллельно** (`.opencode/agents/gender-trier.md`, read-only) читают один YAML построчно, сверяют род реплик (русская грамматика: «я сказала», «я рада», «Контрабандистка…» в наррации) с полом голоса спикера (`config/voices.yaml` → `gender`). Возвращают JSON `[{guid, part, status: OK|REVIEW, note}]`.
2. **Merge**: кандидаты = union по триерам.
3. **Ревьюер-антипод** (`.opencode/agents/gender-reviewer.md`) перепроверяет каждого кандидата, подтверждает (ставит в YAML `review_gender: REVIEW` + `review_note` на фразе) или отклоняет. В JSON возвращает `suggested_speaker` (правильного спикера, если определим).

**Фикс найденного:** человек (или оркестратор после ресерча по GUID) ставит `speaker_override: <правильный спикер>` на part (НЕ на `speaker`!), снимает `review_gender`/`review_note`. Если WAV для фразы уже сгенерированы — добавить на фразу `need_regen: true`.

**`need_regen`** — фраза-уровневое поле: генератор пересоздаёт все части + склейку этой фразы (работает как per-phrase `--force`) и **автоматически снимает флаг** после успешной генерации (пишет YAML обратно, формат как у merge_speakers). При ошибке генерации флаг сохраняется. Если часть пропущена фильтром `--voice` — склейка НЕ пересобирается, флаг сохраняется (иначе склейка была бы неполной).

**Флаги на фразе:** `review_gender: REVIEW` (подозрение, блокировки генерации НЕТ — только информирует), `need_regen: true` (пересгенерить WAV), `review_note` (причина). Оба переживают `merge_speakers.py` (фразы сохраняются целиком).

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

## Дедупликация GUID (один GUID = один файл)

Каждая фраза (GUID) должна жить ровно в одном файле каталога. Дубли критичны: генератор делает два WAV (разные голоса), а `export_mappings.py` берёт первый по алфавиту каталог — играет не тот голос.

Защита (3 уровня):

- `tools/dedup_catalog.py` — удаляет дубли GUID из `Generic_Male_NPC.yaml` (keep per-char копии). `--dry-run` для просмотра.
- `tools/test_pipeline.py::test_no_duplicate_guids` — каждый GUID строго в одном файле (fail со списком).
- `tools/merge_speakers.py` — после union-merge выполняет dedup-фазу (keep: свежая маршрутизация generate_catalog > per-char файл > первый) и в конце прогоняет `test_no_duplicate_guids` (пересборка падает при дублях).
- `tools/export_mappings.py` — печатает WARNING, если у GUID WAV в 2+ каталогах (симптом дубля/мусора).

Причина дублей (археология 2026-08): union-merge никогда не удалял фразы из старых файлов — при улучшении детекции спикера фраза добавлялась в per-char файл, но оставалась в Generic-дампе (161 дубль: Eogann 103, Seneschal 42, Psyker 6, Sister 6, Smuggler 4).

## Релизный процесс

### Как пользователь получает мод

Пользователь жмёт **Code → Download ZIP** на GitHub и получает чистый архив. Никаких ручных ZIP, никаких скриптов упаковки.

### Как это работает

- `.gitattributes` содержит `export-ignore` для всех dev-файлов
- GitHub при генерации «Download ZIP» использует `git archive`, который уважает `export-ignore`
- В архиве остаются только: `Info.json`, `Settings.xml`, `W40KRTAudioDirectMod.dll`, `Localization/ruRU/`

### Что исключено из Download ZIP

Директории: `.opencode/`, `.vscode/`, `catalog/`, `config/`, `docs/`, `Python/`, `refs/`, `review/`, `tests/`, `tools/`, `assets/`
Файлы: `AGENTS.md`, `plan.md`, `compile.bat`, `Main.cs`, `W40KRTAudioDirectMod.csproj`, `.gitignore`, `.gitattributes`, `*.log`, `*.cache`, `*.txt`, `STATUS.md`

### Структура для пользователя (после распаковки)

```
%userprofile%\AppData\LocalLow\Owlcat Games\Warhammer 40000 Rogue Trader\UnityModManager\
  W40KRTAudioDirectMod\
    Info.json
    Settings.xml
    W40KRTAudioDirectMod.dll
    Localization\
      ruRU\
        mappings\          (20 JSON)
        Abelard_Werserian\ (403 WAV)
        ...
```

### Порядок выпуска версии

1. `TriggerLogEnabled = false` в `Main.cs` (в проде всегда false)
2. Обновить версию в `Info.json`
3. Актуализировать `README.md` (бейджи, статус озвучки)
4. `compile.bat` — пересобрать DLL
5. `git add W40KRTAudioDirectMod.dll` (DLL трекается в git для релиза)
6. Коммит + `git tag vX.Y.Z`
7. `git push --tags`
8. GitHub Release: changelog + ссылка на Download ZIP
9. (опционально) Создать/обновить страницу на Nexus Mods
