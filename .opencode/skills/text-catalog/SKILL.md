---
name: text-catalog
description: Generate and query the per-character dialog phrase catalog from game localization files.
---

# text-catalog — Каталог диалоговых реплик

## Структура `catalog/`

```
catalog/
  people/              # один YAML на персонажа (мета + фразы)
    Kunrad_Voigtvir.yaml
    Theodora_von_Valancius.yaml
    Abelard_Werserian.yaml
    ...
  index.yaml           # сводка: имена, роли, количество фраз
```

Каждый файл в `people/` самодостаточен — содержит мету (пол, роль) и массив phrases. Исходный текст из `ruRU.json` **не меняется** (никаких чисток, обрезок, кроме `< 3` символов).

## Источники данных (для генерации)

| Источник | Путь | Что даёт |
|----------|------|----------|
| `Sound.json` | `WH40KRT_Data/StreamingAssets/Localization/Sound.json` | GUID → имя_ивента (5089 записей) |
| `ruRU.json` | `WH40KRT_Data/StreamingAssets/Localization/ruRU.json` | GUID → сырой текст |

Мета для генерации берётся из уже существующих `catalog/people/*.yaml`.

## CLI

### Генерация каталога

```bash
python .opencode/skills/text-catalog/scripts/generate_catalog.py
```

Перегенерирует `catalog/people/*.yaml` и `catalog/people/index.yaml`. Идемпотентно.
`--verify-only` — только проверить суммы, не писать файлы.

### Просмотр и статистика (catalog.py)

```bash
# Статистика: сколько реплик у каждого, сколько сгенерировано WAV
python .opencode/skills/text-catalog/scripts/catalog.py --stats

# Список всех персонажей
python .opencode/skills/text-catalog/scripts/catalog.py --chars

# Реплики одного персонажа
python .opencode/skills/text-catalog/scripts/catalog.py --char Кунрад

# Только несгенерированные
python .opencode/skills/text-catalog/scripts/catalog.py --char Кунрад --todo

# Экспорт в JSON
python .opencode/skills/text-catalog/scripts/catalog.py --json export.json
```

### Проверка суммы

```bash
python .opencode/skills/text-catalog/scripts/generate_catalog.py --verify-only
```

Ожидается: 5089 Sound.json + 34319 extra dialog + N description = итого ~39408+.

## Формат `people/*.yaml`

```yaml
name: Kunrad Voigtvir
gender: M
role: Мастер шепотов
sound_keys:
  - Kunrad
total_phrases: 67
phrases:
  - guid: ca2ef6c0-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    event: PRL_KunradIntroduction_01
    text: "Прекрасное место для размышлений... {n}...{/n} ..."
  - guid: ...
    event: PRL_KunradIntroduction_ArbitesReaction_32
    text: "..."
```

## Формат `index.yaml`

```yaml
generated: "2026-07-14"
total_characters: 25
total_phrases: 5089
unassigned: 0
characters:
  - name: Kunrad Voigtvir
    gender: M
    role: Мастер шепотов
    total_phrases: 67
  - name: Theodora von Valancius
    ...
```

## Правила маппинга (GUID → персонаж)

1. Для каждого ивента в Sound.json: ищем все `sound_keys`, входящие в имя ивента
2. Сортируем: **по убыванию длины** ключа, затем **по возрастанию позиции** в имени
3. Берём победителя; если ни один не подошёл → `Generic Male NPC`
4. Fallback идёт только на неподходящие ивенты (пустые `sound_keys` у персонажа не считаются)

## Категории фраз

В каталоге три источника фраз:

| Категория | Источник | Фильтр | Пример |
|-----------|----------|--------|--------|
| **Sound.json events** | `Sound.json` | Есть Wwise-ивент → маппинг через `sound_keys` | `PRL_TheodoraFirstConversation_01` |
| **Extra dialog** (ruRU-only) | `ruRU.json` | Нет Sound.json, есть `"` или `{n}`, длина ≥50 | Реплики NPC без озвучки |
| **Descriptions** (окружение) | `ruRU.json` | Нет Sound.json, нет `"`, `{`, `<`, `[`, длина ≥50 | "Массивный стол для переговоров..." |

## Как добавить нового персонажа

Добавить в `catalog/people/` новый YAML с полями `name`, `sound_keys`, `doc:` и запустить `generate_catalog.py`:

```yaml
name: "НовыйПерс"
gender: M
role: "его роль"
sound_keys: ["NewKey"]
```

Затем: `python generate_catalog.py` → все фразы подхватятся.
