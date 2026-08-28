# CosyVoice 3.0 — локальный TTS-пайплайн (voice clone)

Модель: `FunAudioLLM/Fun-CosyVoice3-0.5B-2512` (Alibaba, Apache 2.0, релиз 12.2025).
Zero-shot voice cloning, 9 языков (включая русский), cross-lingual (англ. референс → рус. текст).
Наш кейс: референсы — оригинальные англ. голоса актёров из игры (`refs/samples_en/`), текст — русский.

## Установка (готово 2026-08-28)

- Repo + venv + модель: `C:\tools\cosyvoice3\` (~10 ГБ)
  - `CosyVoice\` — исходники (main, 2026-08)
  - `.venv\` — Python 3.10 (torch 2.3.1 CPU, transformers 4.51.3, onnxruntime 1.18)
  - `pretrained_models\Fun-CosyVoice3-0.5B\` — веса
- Запуск: `C:\tools\cosyvoice3\.venv\Scripts\python.exe tools/cosyvoice3_demo.py`

## Скрипт

`tools/cosyvoice3_demo.py` — single-part / multi-part (speaker→ref, склейка с `--gap`),
все флаги: `--guid --char --text --ref --speed --instruct --sampling --rl --base --single --out`.

## Рычаги качества (по субъективному рейтингу 2026-08-28)

| Рычаг | Описание | Итог |
|-------|----------|------|
| **RL-веса** | `llm.rl.pt` — пост-тренировка reward-model. Default в скрипте | **Лучший single-голос** |
| **Multi-part + реф на голос** | части фразы = отдельный прогон со своим рефом (speech + narrator) | **Лучший общий результат** |
| instruct2 | `--instruct angry/sad/happy/loud/soft/fast/slow` — эмоции/темп | angry — не зашло |
| sampling | `--sampling top_p,top_k,tau_r` — правка RAS-семплера в yaml | 0.9/50 — не зашло |
| speed | `--speed 0.5–2.0` — пост-интерполяция mel | не пробовали |
| Референс | 3–10с чистой речи; тишина/музыка в рефе портят тембр | главный ручной рычаг |

### RL vs Base

В `pretrained_models\Fun-CosyVoice3-0.5B\` лежат оба LLM: `llm.pt` (base) и `llm.rl.pt`.
Скрипт делает hardlink-копию модель-дира (`Fun-CosyVoice3-0.5B_rl`) и меняет
`llm.pt ← llm.rl.pt` (base сохраняется как `llm.base.pt`). `--base` — обратный выбор.

### Язык

- Явного `language=` параметра НЕТ (в отличие от Qwen3-TTS). Один мультиязычный LLM,
  язык выводится из текста; русский — один из 9 языков обучения.
- Токенизатор имеет спец-токены языков (`<|en|>`, `<|ru|>`, `allowed_special='all'`) —
  можно подставлять в текст вручную (в CV2 это было штатно, в CV3-примерах не используется).
- Instruction-промпт (`infer2`/префикс) — свободный текст, список в
  `cosyvoice/utils/common.py` — только подсказки. Можно пробовать «Please say it in Russian».

### Референсы CV3

`refs/samples_en_cosy/` — 10с, 24kHz mono, нарезаны из `refs/samples_en/` (ffmpeg -ss 2.5 -t 10).
Референсы под каждого спикера добавлять туда: `{Speaker}.wav` (пробел → `_`), нарратор — `Narrator.wav`.

## Технические заметки

- Префикс `You are a helpful assistant.<|endofprompt|>` — обязателен для CV3 (из-за него
  text_normalize сам отключается; для русского дополнительно передаём `text_frontend=False`)
- wetext на этой машине падает (403 с modelscope) → frontend выключен, для русского не критично
- CPU: загрузка модели ~10с, генерация RTF ~7–15 (одна реплика 0.5–2 мин).
  Для батча — грузить модель один раз на процесс, не на фразу
- `speech_tokenizer_v3.onnx` лимит: промпт ≤ 30с (в коде)
- ttsfrd — только Linux; не нужен
- Демки: `refs/samples_en_demo_cosy/` (победители: RL-сингл + multi-voice),
  Q3-демки — `refs/samples_en_demo_q3/`

## Следующие шаги (если переходим на CV3)

1. Батчевый скрипт по образцу `qwen3_full_icl.py`: один процесс, модель RL,
   рефы из `refs/samples_en_cosy/`, выход `output/cosyvoice3/{voice}/`
2. Референсы всех голосов в `refs/samples_en_cosy/`
3. Сравнение пайплайнов по времени и качеству на 5–10 фразах, потом решение о миграции
