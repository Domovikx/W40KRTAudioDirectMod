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
python catalog_2/tools/parse_bbp.py            # BBP → raw/bbp_env_desc.yaml ⚠ слабый сигнал
                                              # (см. ниже "Уроки: BBP parsing")

# 2. Не-диалоговый pipeline (для env-desc экспериментов)
python tools/extract_non_dialog.py             # ruRU.json → catalog_2/raw/source.yaml
python tools/narrow_candidates.py              # → catalog_2/raw/narrow_v2.yaml + dialog_mf_pending.yaml

# 3. TODO
python catalog_2/tools/extract_unity_assets.py # assets → raw/unity_text_assets.yaml
python catalog_2/tools/build_catalog.py        # raw/* → people/Environment_Descriptions.yaml
python catalog_2/tools/diff_catalog.py --prev manifests/2026-08-15.yaml
```

## Уроки: BBP parsing (что НЕ сработало)

`catalog_2/tools/parse_bbp.py` пробежал-таки BBP, но **как primary classifier бесполезен**:

- Сериализация BBP не хранит имена классов blueprint'ов как ASCII — type-id это FNV-1 hash
- Единственный «бесплатный» сигнал — asset-имя ноды (Cue_/Answer_/BookPage_/etc)
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
  category: InteractiveObject        # из enum'а DLL (если найден)
  source_anchor: BBP                 # BBP / DLL / FALLBACK
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
- Фаза 2 (BBP): ⚠ инструмент готов, но сигнал слабый (~2% precision) — отчёт в docstring `parse_bbp.py`
- Фаза 3 (Unity assets): ⏳ запланировано
- Фаза 4 (каталог): ⏳ запланировано (заблокировано: нужен working primary classifier)

## Что НЕ делать

- ❌ Не публиковать `private/`
- ❌ Не модифицировать игру
- ❌ Не трогать `catalog/` (обратная совместимость)
