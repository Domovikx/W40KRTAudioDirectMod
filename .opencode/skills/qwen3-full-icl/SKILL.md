# Qwen3-TTS Full ICL — генерация реплик через Voice Clone

Генерация диалоговых реплик через **Base модель** с **Full ICL** (In-Context Learning) — voice clone по референсу.

## Pipeline

```
VoiceDesign → reference.wav + reference.txt  (1 раз на персонажа)
       ↓
Base model → create_voice_clone_prompt(ref_audio, ref_text, x_vector_only=False)
       ↓
Base model → generate_voice_clone(text, voice_clone_prompt)  ← для каждой фразы
```

## Конфигурация

`config/voices.yaml` — маппинг персонаж → файл референса:
```yaml
references:
  wh40k_narrator:
    wav: refs/wh40k_narrator_reference.wav
    txt: refs/wh40k_narrator_reference.txt
```

`config/default.yaml` → секция `qwen3_base_*`:
```yaml
qwen3_base_model: Qwen/Qwen3-TTS-12Hz-1.7B-Base
qwen3_base_device: cpu
qwen3_base_dtype: float32
qwen3_base_temperature: 0.2
```

## Скрипт

```bash
python tools/qwen3_full_icl.py
```

Читает `config/voices.yaml` + каталоги персонажей из `catalog/people/*.yaml`.
Генерирует WAV во `output/full_icl/{voice_name}/`.

## Рекомендации

| Параметр | Значение | Почему |
|----------|----------|--------|
| `x_vector_only_mode` | `false` | Full ICL — референс влияет и на тембр, и на стиль |
| `temperature` | 0.2–0.3 | Стабильность, голос не плавает между фразами |
| `top_p` | 0.9 | Умеренный отсев хвостов |
| `max_new_tokens` | 2048 | Для коротких фраз (диалоговые реплики) |
| `dtype` | float32 | Максимальное качество |

## Текст

- Никаких ударений, SSML, разметки — чистый русский текст
- WH40k термины (Варп, Империум) — стандартная транслитерация, модель знает
- Длинные фразы (>30с) разбивать на части черех `tools/qwen3_phrase_split.py`

## Референсы

- `docs/qwen3-tts.md` — полный справочник
- `tools/qwen3_voice_design.py` — создание референса
- `tools/qwen3_full_icl.py` — батчевая генерация
