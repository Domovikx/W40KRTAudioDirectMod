---
name: russian-tts
description: Generate Russian voiceover WAV files for W40KRTAudioDirectMod. Supports 3 TTS engines: Silero (offline), Edge-TTS (online), SAPI (fallback).
---

# Russian TTS — единый доступ ко всем движкам

## Архитектура

```
russian-tts (SKILL.md) — точка входа
  │
  ├── tools/silero_tts.py   — Silero TTS (офлайн, PyTorch)
  │   Дока: tools/silero_tts.py (docstring)
  │   Конфиг: config/default.yaml → silero_*
  │
  ├── tools/edge_tts.py     — Edge TTS (онлайн, Azure Neural)
  │   Дока: tools/edge_tts.py (docstring)
  │   Конфиг: config/default.yaml → edge_*
  │
  └── (tools/sapi_tts.py)   — SAPI5 (запасной, Windows)
      Дока: —
      Конфиг: —
```

## Контракт (единый для всех движков)

```python
def generate(text: str, output: str, voice: str = "eugene") -> float:
    """
    Args:
        text    — очищенный текст без игровых тегов
        output  — путь до WAV файла
        voice   — имя голоса (зависит от движка)
    Returns:
        float   — длительность в секундах
    """
```

## Таблица движков

| Движок | Тип | Рус. голоса | Качество | Нужен интернет | Путь к доке |
|--------|-----|-------------|----------|----------------|-------------|
| **Silero** | Офлайн | 5 (2М+3Ж) | 🎯 Natural | Нет (кроме 1-го раза) | `tools/silero_tts.py` |
| **Gemini TTS** 🆕 | Онлайн | 30 (15М+15Ж) | 🎯 Premium | Да (+ прокси) | `tools/gemini_tts.py`, `.opencode/skills/gemini-tts/SKILL.md` |
| **Edge-TTS** | Онлайн | 2 (1М+1Ж) | 🎯 Neural | Да | `tools/edge_tts.py` |
| SAPI | Офлайн | 2 (1М+1Ж) | 🤖 Базовый | Нет | — |

## Где что лежит

| Что | Где |
|-----|-----|
| Конфиги | `config/default.yaml`, `config/characters.yaml` |
| Голоса персонажей | `config/characters.yaml` |
| Сгенерированные WAV | `Localization/{lang}/` |
| Генерация Silero | `python tools/silero_tts.py` |
| Генерация Edge-TTS | `python tools/edge_tts.py` |
| Агент-скил | `.opencode/skills/ssml-builder/`, `.opencode/skills/voice-casting/` |
| Справочник проекта | `AGENTS.md` |

## Как добавить новый движок

1. Создать `tools/{name}_tts.py` с функцией `generate(text, output, voice) -> float`
2. Добавить секцию в `config/default.yaml` под префиксом `{name}_*`
3. Обновить таблицу движков в этом файле
