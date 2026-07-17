---
name: qwen3-tts
description: Generate Russian voiceover WAV files via Alibaba Qwen3-TTS (локально, офлайн, 9 голосов).
---

# Qwen3-TTS — Alibaba Qwen3-TTS (локальный)

Полный справочник: `docs/qwen3-tts.md`

## Контракт

```python
def generate(text: str, output: str, voice: str = "Ryan", instruct: str = "", **gen_kwargs) -> float
```

- `text` — текст для озвучивания
- `output` — путь до WAV файла
- `voice` — имя голоса (см. `docs/qwen3-tts.md`)
- `instruct` — стиль/эмоция (опционально)
- `**gen_kwargs` — temperature, top_k, top_p, repetition_penalty, max_new_tokens
- return — длительность в секундах

## Использование

```python
from tools.qwen3_tts import generate
dur = generate("Привет мир", "speech.wav", voice="Ryan")
dur = generate("Текст", "out.wav", voice="Ryan", instruct="Thoughtful, low register", temperature=0.2)
```

## Архитектура

```
qwen3-tts (SKILL.md) — точка входа
  │
  ├── docs/qwen3-tts.md — полный справочник (голоса, параметры, сцены)
  │
  └── tools/qwen3_tts.py — Qwen3-TTS через qwen-tts (PyTorch)
      Модель: Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
      dtype: float32 (лучшее качество)
      Зависимости: qwen-tts, torch, soundfile
```

## Scene Presets

Параметры генерации по типам сцены — `config/default.yaml` → `qwen3_scene_presets`:

| Сцена | Temp | Когда |
|-------|------|-------|
| `narrator` | 0.2 | Закадровый нарратор |
| `dialog` | 0.2 | Диалоги NPC / Капитан |
| `combat` | 0.4 | Боевые реплики |
| `warp` | 0.65 | Варп-сущности |

## Формат

- Вход: текст (без ограничения длины)
- Выход: WAV 24000 Гц, 16-bit, mono
