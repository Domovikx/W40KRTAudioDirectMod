# Environment Descriptions — PIVOT (2026-08-15)

Итоговая сводка по задаче «озвучка environment descriptions» (env-desc).
**Задача поставлена на паузу** — мы упираемся в фундаментальные ограничения
данных игры. Документ фиксирует что пробовали, что НЕ работает, и как
возобновить работу если приоритет вернётся.

## Контекст

- **Что такое env-desc:** не-диалоговый текст в игре (encyclopedia, books, notes,
  object descriptions, area poems etc). 5306 «кандидатов» в
  `catalog_2/raw/narrow_v2.yaml` (после фильтров: длина 80–400,
  нет `{g}`/`{pfwiki}`/`draft`/`bind`/иконок).
- **Цель:** добавить опциональную озвучку narrator-голосом для тех фраз,
  которые этого стоят (не дублировать UI/encyclopedia/credits/dialog_mf).
- **Каталог озвученных реплик** (`Localization/ruRU/{Character}/`)
  остаётся в приоритете — он int64-уже работает, ничего не сломано.

## Что сделано (3 захода)

### Заход 1 (2026-08-14): эвристики + нейро-классификация — ПРОВАЛ

- `tools/extract_non_dialog.py` → `catalog_2/raw/source.yaml` (29 658 строк)
- `tools/narrow_candidates.py` → `catalog_2/raw/narrow_v2.yaml` (5306) +
  `catalog_2/raw/dialog_mf_pending.yaml` (1115)
- `tools/classify_env_descriptions.py` (6 классов: flavor/world_lore/scene/
  interactive/npc_notes/item_desc) — **регексы + шаблоны** (УДАЛЁН)
- Сабагент-ревью 300 сэмплов → `_review_sampled.json` (УДАЛЁН)
  - scene 12/38 agree, interactive 18/32, world_lore 30/20
  - npc_notes 49/1 ✅, item_desc 44/6 ✅
- **Точность ~64% в среднем, провал для scene/interactive/world_lore.**
- Counter-examples в `review/counter_examples.yaml`.

**Вердикт:** автоматические эвристики по тексту не работают на этом домене.
Шум слишком большой, игра текстually неоднородна.

### Заход 2 (2026-08-15, утро): BBP якоря — ПРОВАЛ

Идея: если в `Bundles/blueprints-pack.bbp` (82 МБ) найти узел типа
`BlueprintEncyclopediaBlockText`/`BlueprintBookPage`/`BlueprintArea` для
каждого text-GUID, можно честно разметить категорию.

- `catalog_2/tools/extract_dll_types.py` ✅ → 22 типа в `catalog_2/raw/dll_types.yaml`
  (Code.dll, BlueprintEncyclopedia*, BlueprintBookPage, BlueprintArea и др.)
- `catalog_2/tools/parse_bbp.py` ⚠ — написан, протестирован
- Пилот на 5306 narrow_v2:
  - matched в BBP: 2652
  - полезные категории (BookPage/SequenceExit/Objective/Chapter/Page/Block/
    Transition/Item): **117 (2.2%)**
  - noise (Cue_/Answer_/Command*): 1586
  - other/unmatched: 3603

**Концептуальная причина провала:** BBP-сериализация НЕ хранит имена классов
blueprint'ов как ASCII. Type-id в бинаре — FNV-1 hash. Единственный
«бесплатный» сигнал — asset-имя узла (BookPage_/SequenceExit_/Objective_/
Cue_/Answer_/Command*). Для text-GUID ближайший preceding node в бинаре —
почти всегда **диалоговый** предок (Cue_/Answer_), не реальный owner
blueprint. Поэтому − ~60% matched = шум, и даже среди оставшихся 117 —
нужно чистить руками.

**Вердикт:** BBP name-prefix parsing — слабый second-pass signal, **НЕ**
primary classifier. Отчёт в docstring `catalog_2/tools/parse_bbp.py`.

### Заход 3 (2026-08-15, вечер): Wwise/Sound.json — ТУПИК

Идея: `Sound.json` (5089 entries, maps text-GUID → Wwise event-name) — это
индекс **озвученных** реплик. Через обратный поиск (event-name → wem-id →
blueprint-owner) можно протянуть привязку.

- Проверили: `narrow_v2 (5306 env-desc) ∩ Sound.json (5089) = 0`
- **env-desc by design не озвучены** — это противоположная выборка.
- Sound.json НЕ помогает отличить «env-desc стоит озвучить» от «не стоит».
- Зато он остаётся полезен для **Wem/wwise extraction of references** в
  другом контексте (методика 2026-08-10 для голосовых рефов).

**Вердикт:** тупик для env-desc. Sound.json НЕ даёт сигнала.

## Что НЕ делать (при возврате)

- ❌ **Не тратить время на регексы/LLM по самому тексту** — precision 64% в
  лучшем случае, ручная доразметка дороже чем выгода.
- ❌ **Не пытаться классифицировать через BBP name-prefix** — 2.2% precision,
  доказано физикой (диалоговое дерево доминирует в бинаре).
- ❌ **Не предполагать, что Sound.json/Wem dataset покроет env-desc** — там
  только озвученные реплики, противоположная выборка.
- ❌ **Не устраивать few-shot «по примерам»** — counter_examples.yaml
  показывает, что примеры врут: scene↔world_lore, interactive↔scene и т.п.
- ❌ **Не вливать catalog_2/ в master раньше времени** — Phase 1 (DLL) —
  единственное что работает; всё остальное — экспериментальный каркас.
- ❌ **Не плодить новые tools под каждый регекс** — паттерн «script → pilot →
  64% → удалить» повторяется, замедляет основную работу.

## Что работает (сохранить)

- ✅ `catalog_2/tools/extract_dll_types.py` — рабочий, извлекает 22 DLL-типа
  с description-полями. Полезно для любой будущей задачи по типам.
- ✅ `catalog_2/raw/dll_types.yaml` — артефакт.
- ✅ `catalog_2/README.md` — структура и статусы (для будущей сессии).
- ✅ `catalog_2/manifests/2026-08-15.yaml` — snapshot.
- ✅ `catalog_2/tools/parse_bbp.py` — с docstring-отчётом (не использовать
  как primary, но reproducible record «что пробовали»).
- ✅ `tools/extract_non_dialog.py` + `tools/narrow_candidates.py` — рабочий
  pipeline `narrow_v2.yaml`. Перезапускаемый, ~30 сек.
- ✅ `tests/test_extract_non_dialog.py` + `tests/test_narrow_candidates.py` —
  тесты регексов (31/31 проходят).
- ✅ `catalog_2/raw/narrow_v2.yaml` (5306) + `dialog_mf_pending.yaml` (1115) +
  `source.yaml` (29 658) — вход/промежуточные.
- ✅ `.gitignore` — `private/` (на будущее, для personal extracts).
- ✅ `.gitattributes` — `catalog_2/` добавлен в export-ignore (YAMLы не попадут
  в release).

## Что делать если вернёмся (3 перспективных пути)

Отсортированы по убыванию потенциальной пользы:

### Путь A — Unity text-asset dump (НАИБОЛЕЕ ВЕРОЯТЕН)

Извлечь **text-assets** из Unity bundles (`WH40KRT_Data/*` — там есть
`*.assets` файлы с MonoBehaviour сериализацией). Text-assets содержат
**прямые ссылки text-GUID → blueprint-GUID** (LocalizedString поля,
инлайненные в сериализацию). Это даст точный per-line blueprint-owner.

Артефакты:
- `MonoBehaviour` reader (UnityPy / AssetStudio / uTinyRipper)
- Маппинг: blueprint-GUID → type (через тот же DLL-типизатор)

Ожидаемая precision: **80–95%** для text-GUID'ов, присутствующих в
text-assets. Не все 5306 будут там (часть в BBP), но большинство — да.

### Путь B — Wwise wem-extraction-of-references (извлечь чужие ссылки)

Методика 2026-08-10 (Marazhai/Ulfar refs):
- `event-name` (из Sound.json) → FNV-1 32-bit hash → `CAkEvent.ulID` в .pck
- `CAkActionPlay` → `CAkSound` → `AkMediaInformation.sourceID`
- `sourceID` → wem-id → **bp-GUID** (через Unity assets)

Это и есть обратный путь: «у всех озвученных реплик bp-GUID — какие?»
Даёт **gold-set** для понимания, как игра линкует text → audio.
Но у env-desc озвучки нет → этот путь **не масштабируется** на них напрямую.
Полезен как инфраструктурный (инструменты, парсеры).

### Путь C — Few-shot с правильной разметкой (если A+B не сработают)

Только если Путь A/B вскроют, что precision по text-assets < 50%.
- Набрать вручную 300–500 эталонов с точной категорией из game data.
- Few-shot LLM с этими эталонами.
- **Внимание:** counter_examples.yaml доказывает, что «по тексту» мало
  сигнала — даже GPT-4 на 6 классах даст ~70% precision.

## Текущее состояние (что в git changes)

После cleanup 06.08.2026:

| Файл | Статус | Что делать |
|---|---|---|
| `.gitignore` | M | оставить (для `private/`) |
| `.gitattributes` | M | оставить (`catalog_2/` в export-ignore) |
| `catalog_2/` (README + manifest + 2 tool + raw/) | untracked | оставить как есть |
| `catalog_2/raw/source.yaml` (7.8 МБ) | untracked | оставить (перезапускаемый) |
| `catalog_2/raw/narrow_v2.yaml` (2 МБ) | untracked | оставить (вход для будущего) |
| `catalog_2/raw/dialog_mf_pending.yaml` (387 КБ) | untracked | оставить (отдельная задача) |
| `tools/extract_non_dialog.py` + `narrow_candidates.py` | untracked | оставить (перезапускаемые) |
| `tests/test_extract_non_dialog.py` + `test_narrow_candidates.py` | untracked | оставить (тесты) |
| `Localization/ruRU/Narrator/*.wav` (13) | staged (A) | оставить (TTS staging) |
| `docs/ENV_DESC_PIVOT.md` | untracked | оставить (этот документ) |

**Удалено в cleanup:**
- `bin/wwiser.pyz` (сломан)
- `private/` (пустые подпапки)
- `Localization/ruRU/Environment_Descriptions/_source.yaml`, `_narrow.yaml`, `_test_batch.yaml` (промежуточные, переехали в `catalog_2/raw/`)
- `tools/merge_classifications.py`, `tools/sample_few_shot.py` (от упавшего classifier)
- `catalog_2/people/`, `catalog_2/diffs/` (пустые)

## Куда идём сейчас

Приоритеты переключены:
1. **TTS-регенерация** (Marazhai 553, Ulfar 358, Eogann 203, Manipulus 204)
   — фоновые процессы живы, не трогать.
2. **gender-review/speaker-audit** для Generic_Male_NPC остатков (если есть).
3. **Сборка/тегирование** промежуточных релизов (DLL в git, git tag).

Env-desc — **off-priority до явного повторного запроса**.

## Связанные документы

- `catalog_2/README.md` — структура и статусы фаз
- `catalog_2/manifests/2026-08-15.yaml` — snapshot extract'а
- `review/counter_examples.yaml` — почему эвристики провалились
- `review/resume_state.md` — секции "2026-08-14" и "2026-08-15"
- `catalog_2/tools/parse_bbp.py` (docstring) — детальный отчёт BBP-пилота
