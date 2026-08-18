# MAP_MAXIMIZATION — максимизация guid_map (2026-08-17)

**Статус: РЕАЛИЗОВАНО (Phase 5, 92/92 тестов).** Это документ-дизайн; фактические
числа — в `catalog_2/manifests/latest.yaml` (phase_5_map_max).

## Цель

guid_map.json — фундамент всего (partition, спикеры, тесты). Расширяем ровно
там, где в данных есть сигналы. Для unvoiced dialog (39 875 GUID) per-line
спикера в данных НЕТ (движок считает спикера runtime) — потолок, документирован.

## Слои

### L1b — деревья диалогов (bbp node-parse) — ГОТОВО

**Источник:** `Bundles/blueprints-pack.bbp` (82 МБ).

**Парсер (v0.0.2):** границы блоков — по ВСЕМ заголовкам вида
`name 32hex-asset type_byte` (383 968 блоков: Cue_/Answer_/BookPage_ +
cutscene-ноды Command*/gate + прочие blueprint'ы *Page/*Root и т.д.).
Текстовые ссылки — голые `$<guid>`; `$FieldName$<guid>` исключены.
Текст-GUID = только те, что есть в guid_map (ruRU) — остальное (11869) —
foreign-ссылки на ассеты (stats).

**Деревья = непрерывные runs диалоговых блоков** (12 895 деревьев,
41 583 уникальных текст-GUID). Любой недиалоговый заголовок разбивает run —
детерминированно, задокументированно. tree_id = asset первого блока run'а
(+ `#n` при коллизии — 1 случай в корпусе).

**Обогащение guid_map → bbp-слой (51 449 GUID, 41 583 диалоговых):**

```json
"tree_id":   "9381472f4fe34e0dbbbe17bffb7faa14",   // run-корень (asset)
"node_seq":  2,                                     // позиция в run'е
"node_prev": "7a37edc3a8c04b6c870e456597270857",   // последний компакт-GUID блока (raw)
"node_aux":  "df918c2d635446e8ba6cba0123d2cb6e",   // предпоследний (raw, семантика не определена)
"node_lit":  ["Лидер Радикалов (мужчина)", "..."]  // литералы блока (<=8)
```

Атрибуция **блок-точная** и перезаписывает windowed-значения старого парсера
(587 исправлений); при недиалоговой атрибуции стейл-tree-поля удаляются.

**Валидация (tests/test_catalog_2_trees.py, 9 тестов):**

1. СУММА: unique(text_guids по деревьям) == unique(текст-GUID в диалоговых
   блоках ∩ guid_map) == 41 583 — якорь апдейта игры (своё подмножество)
2. Нет дублей text_guids внутри дерева; нет дублей tree_id
3. Принадлежность: все text_guids ∈ guid_map.json (⊂ ruRU 77 691)
4. per-tree: nodes == len(node_order) == cues+answers+books
5. Кросс-валидация: answer-набор (15 073) идентичен старому парсеру и
   партиции DialogAnswer — два независимых парсера согласны
6. L2/L3: sound-слой полный (event+speaker), owner_hint непустые

### L2 — Sound.json events (voiced 5 089) — ГОТОВО

**Источник:** `WH40KRT_Data/StreamingAssets/Localization/Sound.json`
(`{"strings": {guid: {Text: event}}}`).

В guid_map: `sound: {"event": "...", "speaker": "..."}` — спикер через порт
`extract_speaker_from_event` из v1 (85.2% — 4 338/5 089). camelCase-prefix-match
(«AbelardRecruit»→Абеляр) только для диалоговых префиксов (BNTRS,
CompanionDialogue, OfficialPropos, BS, Trazyn*, ArbitesAfterSex...);
**PRL/CH1-3/RMNC — имена сцен (subject, не спикер) — exact-match только**.
Спелл-варианты: Pascal→Паскаль, Solomorne/Solomorn→Соломон.
Остаточные miss: PRL/CH-сцены, Trazyn:Ancestor, BNTRS:DLC3 edge.

### L3 — префиксы спикеров (owner-паттерны) — ГОТОВО

`owner_hint` — токен-матчинг `blueprint.owner` против имён персонажей и ролей
(1 043 GUID: `JaeBurntEmperor_bark`→Джаэ и т.п.).

## Порядок реализации (выполнен)

1. `docs/MAP_MAXIMIZATION.md` — этот документ
2. `catalog_2/tools/build_trees.py` — нод-парсер + деревья + обогащение мапы
3. `catalog_2/tools/enrich_sound.py` — L2 + L3 слой
4. `tests/test_catalog_2_trees.py` — 9 тестов
5. Прогон набора — 92/92
6. Манифест latest.yaml (phase_5_map_max)

## Ожидаемые vs фактические числа

| Метрика | Ожидание | Факт |
|---------|----------|------|
| Нод-блоков | 55 380 (диалог.) | 383 968 (все заголовки) |
| unique текст-GUID в нодах | 68 954 (грубый замер) | 41 583 диалог + 9 923 недиалог |
| Деревьев | ~4 538 (грубая оценка) | 12 895 (cutscene-ноды дробят) |
| role cue / answer | 33 956 / 18 056 (байты) | 27 582 / 15 073 (+8 045 unknown) |
| Спикер из Sound.json | 88.9% (v1) | 85.2% (4 338/5 089) |

Отклонения объяснены: байт-счётчики считали ПОЗИЦИИ, не уникальные GUID;
v1-процент считался на своём подмножестве.

## Известные тупики (проверено на бинаре)

- Имён спикеров в bbp нет: 0.9% hit-rate, и это dev-комментарии квестов
  («Переместить Соломона...») — не сигнал
- Поля `$Speaker`/`$Text`/`$Description` рядом с текст-GUID не найдены
  (ссылки голые `$GUID` внутри нод)
- Формат `Answer_N (guid)\n<буквальный текст>` — всего 2 вхождения, не основной
- wwiser/Wwise — сломан, для спикеров не нужен
- Семантика G1/G2 (prev/aux) — не определена, храним raw
- `node_lit` — кандидат в спикеры, требует отдельной валидации
- Границы деревьев: run'ы ломаются на cutscene-нодах — фрагментация
  задокументирована; перестройка в «1 диалог = 1 дерево» требует
  blueprint-boundary сигнала, которого в данных нет