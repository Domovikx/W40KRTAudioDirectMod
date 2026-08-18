# catalog_2 — параллельная система каталогизации

Извлечение и структурирование environment descriptions (и других категорий)
из игры Warhammer 40,000: Rogue Trader. Создана как параллельная catalog/
система с улучшенной архитектурой для воспроизводимости.

## Зачем catalog_2

- **`catalog/`** (существующий) — рабочая система, **не трогаем**.
- **`catalog_2/`** — параллельная, для разведки и экспериментов.
- Извлечения из DLL/BBP/Unity assets → `private/` (gitignore).
- Pipeline воспроизводимый — при обновлении игры достаточно re-extract.

## Структура

```
catalog_2/
├── raw/             # сырьё из игры (воспроизводимое)
├── tools/           # скрипты воспроизведения
├── manifests/       # версионированные срезы
└── README.md
```

```
private/             # ← gitignore
├── decompiled/      # *.cs файлы из Assembly-CSharp.dll
├── bbp_raw/         # raw dump из blueprints-pack.bbp
└── unity_raw/       # raw asset dumps
```

## Как воспроизвести

```bash
# 1. Извлечь из игры
python catalog_2/tools/extract_dll_types.py    # DLL → raw/dll_types.yaml (✔ работает)

# 2. Карта корпуса + максимизация (мапа — фундамент всего)
python catalog_2/tools/build_guid_map.py       # -> raw/guid_map.json (77 691 GUID)
python catalog_2/tools/build_trees.py          # L1b: деревья + блок-точная атрибуция
python catalog_2/tools/enrich_sound.py         # L2/L3: Sound.json спикеры + owner_hint
python catalog_2/tools/update_map_stats.py     # снапшот raw/guid_map_stats.yaml

# 3. ✅ Полная разбивка корпуса (77 691 GUID, без потерь)
python catalog_2/tools/build_partition.py   # -> people/*.yaml (12 файлов) + index.yaml
                                            # инвариант: сумма == 77691 == len(ruRU.json)
python -m pytest tests/test_catalog_2_partition.py   # инварианты: сумма/дубли/покрытие

# 4. TODO
python catalog_2/tools/extract_unity_assets.py # assets → raw/unity_text_assets.yaml
python catalog_2/tools/diff_catalog.py --prev manifests/2026-08-15.yaml
```

## Разбивка `people/` (полная, без потерь)

Каждый GUID из ruRU.json попадает ровно в один файл — сумма по файлам всегда
равна 77 691 (инвариант; ломается при обновлении игры → тесты ловят).

| Файл                            | Правило                                                             | GUID   |
| ------------------------------- | ------------------------------------------------------------------- | ------ |
| `VoicedDialog.yaml`             | GUID ∈ Sound.json (есть Wwise-ивент)                                | 5 089  |
| `DialogAnswer.yaml`             | bbp-роль `answer` (выборы игрока)                                   | 15 074 |
| `DialogCue.yaml`                | bbp-роль `cue` (реплики NPC)                                        | 24 808 |
| `Barks.yaml`                    | blueprint.owner ~ bark\|banter\|randomphrase                        | 1 936  |
| `Environment_Descriptions.yaml` | `env_scan.classify()` принял (A=447, B=1 764)                       | 2 211  |
| `UI.yaml`                       | класс UIStrings/UISettings/KeyBinding/ReasonStrings/GlossaryStrings | 1 994  |
| `Encyclopedia.yaml`             | класс Encyclopedia\*/BookPage                                       | 91     |
| `GameLog.yaml`                  | класс GameLog\*                                                     | 230    |
| `Objectives.yaml`               | dialog_owner Objective*/Obj*                                        | 639    |
| `Narration.yaml`                | текст содержит {n}                                                  | 1 203  |
| `Short.yaml`                    | len(text) < 40, без сигналов                                        | 12 574 |
| `Other.yaml`                    | остаток (markup, noise, без сигналов)                               | 11 842 |

Порядок маршрутизации критичен (первое совпадение побеждает):
`voiced → answer → cue → bark → env → ui → enc → gamelog → objective →
narration → short → other`. env-записи обогащены из
guid_map (blueprint_owner, scenes) и несут `parts [{speaker: narrator,
text_clean}]` — готовы к озвучке. Остальные файлы lean (guid + text).

## Уроки: BBP parsing (что НЕ сработало)

`catalog_2/tools/parse_bbp.py` (удалён в Phase 6) пробежал-таки BBP, но **как
primary classifier бесполезен**:

- Сериализация BBP не хранит имена классов blueprint'ов как ASCII — type-id это FNV-1 hash
- Единственный «бесплатный» сигнал — asset-имя ноды (Cue*/Answer*/BookPage\_/etc)
- Для text-GUID ближайший preceding node в бинаре — почти всегда диалоговый предок, не владелец
- Пилот на 5306 narrow GUID: matched 2652, полезных категорий (BookPage/SequenceExit/
  Objective/Chapter/Page/Block/Transition/Item) — **117 (2.2%)**, остальное — noise/other/unmatched

**Вывод:** BBP name-prefix parsing — слабый second-pass signal, но НЕ primary classifier.
Primary должен приходить из: sound/wem database (event-name → blueprint), Unity text-asset dump,
или LLM few-shot. См. `review/resume_state.md` → "2026-08-15: catalog_2" для деталей.

## При обновлении игры

1. Steam update
2. Re-extract (шаги 1-2 выше)
3. `diffs/<new_date>_vs_PREV.yaml` — что нового
4. Обновить `manifests/latest.yaml`
5. Сгенерировать новые WAV через `tools/qwen3_full_icl.py --guid <new_guids>`

## Формат `people/Environment_Descriptions.yaml`

```yaml
- guid: 7a4156e5-...
  text: "оригинал из ruRU.json"
  text_clean: "нормализованный для TTS"
  category: InteractiveObject # из enum'а DLL (если найден)
  source_anchor: BBP # BBP / DLL / FALLBACK
  extraction_run: "2026-08-15_v1.4.3"
  parts:
    - speaker: narrator
      text_clean: "нормализованный"
```

## `source_anchor`

- **DLL** — тип из enum/класса Assembly-CSharp.dll (✔ `extract_dll_types.py` готов)
- **BBP** — найдено в blueprints-pack.bbp как blueprint с Description (⚠ слабый сигнал)
- **UNITY** — найдено в Unity text-asset (TODO)
- **FALLBACK** — эвристика из ruRU.json (нет подтверждения из игры)

## Манифесты

`manifests/<date>.yaml` содержит:

- версия игры (из assembly info)
- дата извлечения
- список raw файлов + sha256
- что попало в people/
- статистика по категориям

## Текущий статус

- Фаза 1 (DLL): ✅ готово — `raw/dll_types.yaml` (22 типа, 2026-08-15)
- Фаза 2 (BBP name-prefix): ❌ удалена (Phase 6) — слабый сигнал (~2% precision),
  история в `manifests/latest.yaml` и `docs/ENV_DESC_PIVOT.md`
- Фаза 3 (Unity assets): ✅ готово — `raw/guid_map.json` (77 691 GUID, см. выше)
- Фаза 4 (каталог): ✅ готово — `people/` (полная разбивка 77 691, инвариант суммы)
- Фаза 5 (максимизация мапы): ✅ готово — `tools/build_trees.py` (L1b: деревья
  12 895, атрибуция 51 449 GUID блок-точная) + `tools/enrich_sound.py` (L2:
  Sound.json → speaker 85.2%; L3: owner_hint 1 043). Дизайн: `docs/MAP_MAXIMIZATION.md`,
  тесты `tests/test_catalog_2_trees.py`
- Фаза 6 (декомпозиция + чистка): ✅ готово — `people/` 12 файлов (bark/gamelog/
  objective/narration/short), удалены Phase 2-тулы и их артефакты, тесты 61/61

## Что НЕ делать

- ❌ Не публиковать `private/`
- ❌ Не модифицировать игру
- ❌ Не трогать `catalog/` (обратная совместимость)
