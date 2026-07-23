---
name: text-catalog
description: Generate and query the per-character dialog phrase catalog from game localization files.
---

# text-catalog — Каталог диалоговых реплик

## Структура `catalog/`

```
catalog/
  people/              # один YAML на персонажа (мета + фразы)
    Кунрад_Войгтвир.yaml
    Теодора_фон_Валанциус.yaml
    Абеляр_Версериан.yaml
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

Перегенерирует `catalog/people/*.yaml` и `catalog/index.yaml`. Идемпотентно.
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

Ожидается: 5089 записей, 0 неопознанных.

## Формат `people/*.yaml`

```yaml
name: Кунрад Войгтвир
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
  - name: Кунрад Войгтвир
    gender: M
    role: Мастер шепотов
    total_phrases: 67
  - name: Теодора фон Валанциус
    ...
```

## Правила маппинга (GUID → персонаж)

1. Для каждого ивента в Sound.json: ищем все `sound_keys`, входящие в имя ивента
2. Сортируем: **по убыванию длины** ключа, затем **по возрастанию позиции** в имени
3. Берём победителя; если ни один не подошёл → `NPC (по умолчанию)`
4. Fallback идёт только на неподходящие ивенты (пустые `sound_keys` у персонажа не считаются)

## Как добавить нового персонажа

Добавить в `catalog/people/` новый YAML с полями `name`, `sound_keys` и запустить `generate_catalog.py`:

```yaml
name: "НовыйПерс"
gender: M
role: "его роль"
sound_keys: ["NewKey"]
```

Затем: `python generate_catalog.py` → все фразы подхватятся.
