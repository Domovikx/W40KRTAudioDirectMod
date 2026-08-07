---
name: text-cleaner
description: "Clean raw game dialog text into TTS-ready text_clean. Handles all W40KRT markup patterns: {g|...}{/g}, {d|...}{/d}, {mf||}, {rt_mf||}, {n}...{/n}, outer quotes. Splits into multi-part structures for character speech + narrator blocks."
---

# text-cleaner — Очистка диалогового текста для TTS

## Назначение

Преобразует сырой `text_original` из `catalog/people/*.yaml` в чистый `text_clean`, готовый для подачи в TTS-движок.

## Что делает

| Паттерн | Пример | Результат |
|---------|--------|-----------|
| `{g\|Encyclopedia:...}текст{/g}` | `{g\|Encyclopedia:Emperor}Бога-Императора{/g}` | `Бога-Императора` |
| `{d\|Encyclopedia:...}текст{/d}` | `{d\|Encyclopedia:GreatDeed}смелость{/d}` | `смелость` |
| `{mf\|word1\|word2}` | `наследн{mf\|иков\|иц}` | `наследников` |
| `{mf\|\|word2}` | `герцог{mf\|\|иня}` | `герцог` |
| `{rt_mf\|word1\|word2}` | `{rt_mf\|его\|ее}` | `его` |
| `{n}...{/n}` | `{n}Кунрад кивает.{/n}` | → отдельная narrator-часть |
| `"текст".` (внешние кавычки ёлочки) | `"Прекрасное место".` | `Прекрасное место.` |
| `{name}` | `Вряд ли, {name}.` | `Вряд ли, {name}.` (сохраняется) |

## Использование

```python
from clean_text import clean_text, split_into_parts

# Простая очистка одной строки
cleaned = clean_text("{g|Encyclopedia:Emperor}Бога-Императора{/g}")
# -> "Бога-Императора"

# Разбивка на реплику + нарратор
parts = split_into_parts(
    '"{n}Кунрад смеется.{/n} "Ты готов?"',
    default_speaker="Kunrad Voigtvir"
)
# -> [
#   {"speaker": "narrator", "text_clean": "Кунрад смеется."},
#   {"speaker": "Kunrad Voigtvir", "text_clean": "Ты готов?"}
# ]
```

## Скрипты

### `scripts/clean_text.py`

Основной модуль: `clean_text()`, `split_into_parts()`.

### `scripts/test_clean_text.py`

62 тест-кейса, покрывающие:
- Все варианты `{g|...}{/g}` и `{d|...}{/d}`
- `{mf|...|...}` с пустыми формами, обеими формами, в середине слова
- `{rt_mf}` — runtime gender
- `{name}` placeholder
- Внешние кавычки: `\u201c...\u201d`, `\u00ab...\u00bb`, ASCII `"..."`
- Внутренние кавычки (`"Лорд-капитан"`) — сохраняются
- `{n}...{/n}` — сплит на narrator/character
- Множественные narrator-блоки
- Вложенные теги (g внутри n)
- Пробелы, переносы строк, пунктуация на границах тегов
- Реальные фразы из Kunrad Voigtvir.yaml

```bash
python -m pytest .opencode/skills/text-cleaner/scripts/test_clean_text.py -v
```

## Запуск на всём каталоге

```python
python .opencode/skills/text-cleaner/scripts/regenerate_text_clean.py
```
