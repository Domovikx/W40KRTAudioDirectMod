---
name: voice-ref-collect
description: Download YouTube clips of voice actors, find clean speech segments, and save reference WAVs to refs/samples/
---

# Voice Reference Collection

Сбор референсных аудиообразцов дикторов для Full ICL пайплайна.

## Workflow

1. Найти YouTube-ролик с голосом диктора (интервью, аудиокнига, дубляж)
2. Скачать WAV: `python .opencode/skills/voice-ref-collect/scripts/dl_ref.py <url> "<Actor Name>"`
3. Проанализировать RMS, найти чистый участок без музыки
4. Обрезать: `python .opencode/skills/voice-ref-collect/scripts/dl_ref.py <url> "<Actor Name>" --from <сек> --dur <сек>`
5. Файл сохраняется в `refs/samples/<Actor Name>.wav`

## Критерии

- Длина: 12–17 секунд чистой речи
- Без наложенной музыки
- Без обрезанных слов в начале/конце
- Естественный тембр голоса (не шепот, не крик)

## Формат

- WAV, 48kHz (native YouTube), 16-bit, mono
- Имя файла: `{Имя Фамилия}.wav` (с пробелом)
- Путь: `refs/samples/`

## Пример

```bash
# Шаг 1: скачать целиком
python .opencode/skills/voice-ref-collect/scripts/dl_ref.py \
  "https://www.youtube.com/watch?v=3Fu6tNZvRes" \
  "Никита Прозоровский"

# Шаг 2: проанализировать RMS (на слух или скриптом)
python .opencode/skills/voice-ref-collect/scripts/dl_ref.py \
  "https://www.youtube.com/watch?v=3Fu6tNZvRes" \
  "Никита Прозоровский" --from 19.78 --dur 15.6
```
