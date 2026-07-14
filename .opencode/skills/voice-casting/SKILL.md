---
name: voice-casting
description: Assign Silero TTS voices to W40KRT characters by role, gender, and personality. Reads config/characters.yaml, resolves voice by speaker name, falls back by gender.
---

# voice-casting

## Source of truth

**`config/characters.yaml`** — основной список. Если персонаж есть там — берём голос оттуда.

## Rule-based fallback

Если персонажа нет в `characters.yaml` (новый NPC, безымянный культист и т.д.):

| Если персонаж                            | Голос     |
| ---------------------------------------- | --------- |
| Мужчина, командир, воин, старик          | `eugene`  |
| Мужчина, учёный, техножрец, спокойный    | `aidar`   |
| Женщина, боевая, дерзкая, псайкер        | `xenia`   |
| Женщина, аристократка, навигатор, мягкая | `baya`    |
| Женщина, молодая, игривая, звонкая       | `kseniya` |

## Silero voices table

| Голос     | Пол | Характер                                 |
| --------- | --- | ---------------------------------------- |
| `eugene`  | M   | Командный, уверенный, военный            |
| `aidar`   | M   | Спокойный, размеренный, интеллектуальный |
| `xenia`   | Ж   | Энергичный, чёткий, эмоциональный        |
| `baya`    | Ж   | Тёплый, мягкий, бархатный                |
| `kseniya` | Ж   | Звонкий, высокий, молодёжный             |

## Usage in tts_engine.py

```python
voice = voice_for_speaker("Кунрад")  # → "eugene"
```

Функция читает `config/characters.yaml`. Если не находит — `eugene` (М) по умолчанию.
