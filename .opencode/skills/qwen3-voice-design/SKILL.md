# Qwen3-TTS VoiceDesign — создание эталонного голоса

Генерация уникального голосового референса через `Qwen3-TTS-12Hz-1.7B-VoiceDesign` для последующего использования в пайплайне Full ICL.

## Pipeline

```
[Текстовое описание голоса]  ← instruct (English, 1-3 предложения)
        ↓
[VoiceDesign модель]         ← generate_voice_design(text, instruct, language="Russian")
        ↓
[Референс]                   ← refs/{voice_name}_reference.wav + .txt
        ↓
[Base модель + Full ICL]     ← generate(text, references=[...]) — все реплики игры
```

## Скрипт

```bash
python tools/qwen3_voice_design.py [voice_name] [instruct.txt] [text.txt]
```

Параметры:
- `voice_name` — имя файла (без суффикса), по умолч. `wh40k_narrator`
- `instruct.txt` — файл с описанием голоса на английском
- `text.txt` — файл с русским текстом для озвучки (~30с = ~400-600 символов)

Если файлы не указаны — используются дефолтные (проповедь Империума, ~30с).

## Требования к instruct

Описание голоса на **английском**, коротко (1-3 предложения):
- Пол / возраст
- Тембр (chest resonance, bright, gravelly)
- Темп (slow, measured, fast)
- Эмоциональность (restrained, reverent, authoritative)

Плохо: `"Сделай голос как у диктора"`
Хорошо: `"Low male voice, age 45-55, chest resonance, slow measured pace, clear Imperial diction, restrained emotion with a hint of reverence and fatalism, like a voiceover in a documentary about war or a religious sermon. No accent, no hoarseness, no theatrical declamation."`

## Технические детали

- **Модель:** `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign`
- **Тип:** float32 (CPU)
- **Частота:** 48kHz
- **Выход:** WAV + TXT (для Full ICL)
- **Параметры генерации:** temp=0.3, top_p=0.9, rep_penalty=1.05, max_new_tokens=4096
