---
name: qwen3-full-icl
description: Generate TTS audio for dialog phrases using Qwen3-TTS Base model with voice cloning. Reads catalog YAML, resolves speaker→voice, generates per-part WAVs, concatenates into final per-phrase WAV.
---

# Qwen3-TTS Full ICL — Voice Clone генерация

Генерация диалоговых реплик через **Base модель** + **Full ICL** (In-Context Learning).
Голос клонируется из референса (WAV + TXT), созданного через VoiceDesign.

---

## Входной контракт

### 1. Референсы голосов — `config/voices.yaml`

```yaml
references:
  kunrad:                          # логическое имя (voice_name)
    wav: refs/kunrad_reference.wav
    txt: refs/kunrad_reference.txt
  wh40k_narrator:
    wav: refs/wh40k_narrator_reference.wav
    txt: refs/wh40k_narrator_reference.txt
  teodora:
    wav: refs/teodora_reference.wav
    txt: refs/teodora_reference.txt
```

Каждая запись = результат `tools/qwen3_voice_design.py`.

### 2. Фразы — `catalog/people/{Персонаж}.yaml`

```yaml
name: Kunrad Voigtvir
phrases:
  - guid: ca2ef6c0-...
    parts:
      - speaker: Kunrad_Voigtvir       # кто говорит — маппится через voices.yaml.characters
        text_clean: Прекрасное место для размышлений.
      - speaker: narrator               # специальное имя — маппится на wh40k_narrator
        text_clean: Взгляд приблизившегося...
      - speaker: Kunrad_Voigtvir
        text_clean: Отсюда открывается лучший вид...
```

**Правила маппинга speaker → voice_name:**
- speaker ищется в `voices.yaml.*.characters` (по совпадению имени)
- Если не найден → fallback на `wh40k_narrator`

### 3. Параметры генерации — `config/default.yaml`

```yaml
qwen3_base_model: Qwen/Qwen3-TTS-12Hz-1.7B-Base
qwen3_base_device: cpu
qwen3_base_dtype: float32
qwen3_base_temperature: 0.2
qwen3_base_top_p: 0.9
qwen3_base_repetition_penalty: 1.05
qwen3_base_max_new_tokens: 2048
```

---

## Выход

```
output/full_icl/{voice_name}/
  {guid}__1.wav     — часть 1
  {guid}__2.wav     — часть 2
  {guid}__3.wav     — если есть
  {guid}.wav        — склейка всех частей (конкатенация)
```

---

## Скрипты

### `tools/qwen3_full_icl.py` — батчевая генерация

```bash
python tools/qwen3_full_icl.py [--voice voice_name] [--char char_name] [--guid guid...] [--force]
```

- Без аргументов — все голоса из `config/voices.yaml`
- `--voice` — только указанный voice_name
- `--char` — только указанный персонаж
- `--guid guid1 guid2 ...` — только конкретные GUID (из `catalog/people/*.yaml`)
- `--force` — перегенерировать даже если WAV уже существует
- Пропускает уже сгенерированные WAV (idempotent, если без `--force`)

Примеры:
```bash
# Все NPC
python tools/qwen3_full_icl.py --voice default_male

# Конкретные GUID (с перезаписью)
python tools/qwen3_full_icl.py --guid 000e97aa-... 001db7fa-... --force
```

### `.opencode/skills/qwen3-full-icl/concat_parts.py` — склейка частей

Отдельный скрипт для конкатенации WAV-частей в один файл.
Используется если генерация шла порционно или нужно пересклеить.

```bash
python .opencode/skills/qwen3-full-icl/concat_parts.py output/full_icl/kunrad/
```

---

## Процесс (Full ICL)

```
1. VoiceDesign                    → refs/{voice_name}_reference.wav + .txt
   (tools/qwen3_voice_design.py)

2. create_voice_clone_prompt()   → VoiceClonePromptItem
   (ref_audio, ref_text, x_vector_only=False)

3. generate_voice_clone()         → output/full_icl/{voice}/{guid}__N.wav
   (text, voice_clone_prompt, language="Russian")

4. concat_parts.py                → output/full_icl/{voice}/{guid}.wav
   (склейка частей одной фразы)
```

---

## Рекомендации

| Параметр | Значение | Почему |
|----------|----------|--------|
| `x_vector_only_mode` | `false` | Full ICL — тембр + стиль из референса |
| `temperature` | 0.2–0.3 | Стабильность, голос не плавает между фразами |
| `top_p` | 0.9 | Умеренный отсев хвостов |
| `max_new_tokens` | 2048 | Короткие диалоговые реплики |
| `dtype` | float32 | Максимальное качество на CPU |

**Текст:** чистый русский, без ударений, без SSML, без разметки.
WH40k термины (Варп, Империум, Лекс Империалис) — стандартная транслитерация, модель знает.

---

## Референсы

- `docs/qwen3-tts.md` — полный справочник Qwen3-TTS
- `.opencode/skills/qwen3-voice-design/SKILL.md` — создание референса (VoiceDesign)
- `tools/qwen3_voice_design.py` — скрипт создания референса
- `tools/qwen3_full_icl.py` — батчевая генерация
- `config/voices.yaml` — конфиг референсов
- `catalog/people/*.yaml` — каталог фраз персонажей
