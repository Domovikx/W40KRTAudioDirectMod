---
name: cosyvoice3
description: Generate Russian voiceover WAVs with Fun-CosyVoice3-0.5B voice cloning (cross-lingual, RL weights). Reads catalog YAML, resolves speaker→ref, batch-generates into Localization/{lang}/. Winner config, pitfalls, and docs references inside.
---

# Skill: cosyvoice3 — озвучка реплик CosyVoice 3 (voice clone)

Генерация WAV для мода через Fun-CosyVoice3-0.5B (zero-shot voice clone,
англ. реф актёра → русский текст). CV3 — кандидат на замену Q3-TTS
(статус и история: `docs/cosyvoice3.md`, план работ: `todo_ruRU_cosy.md`).

---

## Установка (готово)

- `C:\tools\cosyvoice3\` — repo `CosyVoice\`, venv `.venv\` (Python 3.10), модель
  `pretrained_models\Fun-CosyVoice3-0.5B\` (llm.pt = base, llm.rl.pt = RL)
- Запуск ВСЕГДА через venv: `C:\tools\cosyvoice3\.venv\Scripts\python.exe`

## Победный конфиг (2026-08-29, выбор пользователя по accent-демкам)

```
cross_lingual + RL (llm.rl.pt)
--flow-temp 1.2   (скрытый temperature flow-диффузии, сток кода 1.0; monkeypatch)
--cfg 0.9         (inference_cfg_rate, сток модели 0.7; правится в yaml-копии)
--sampling 0.5,10,0.15  (RAS top_p/top_k/tau_r; сток 0.8/25/0.1)
--tail-trim --s16 --seed 42
```

В `tools/cosyvoice3_demo.py` эти дефолты уже зашиты; `--no-tail-trim`,
`--no-s16` — выключить.

## Референсы голосов — `refs/samples_en_cosy/`

25 голосов: `{Speaker}.wav` (24kHz mono, ~4–10с чистой речи, без обрыва слов)
+ `{Speaker}.txt` (whisper-транскрипт, **нужен** для zero_shot;
cross_lingual не использует).

- Сборка: `python tools/build_cosy_refs.py` (idempotent; окна режет по whisper
  word-timestamps, защита от «двойных тейков» — случай Джаэ, когда 15с реф
  содержал один дубль дважды и кат рвал слово)
- Исходники: `refs/samples_en/` (оригинальные англ. голоса из игры)
- Имя файла = speaker с `_` вместо пробела; narrator → `Narrator.wav`

## Скрипты

### `tools/cosyvoice3_demo.py` — одна фраза (A/B, демки)

```bash
... cosyvoice3_demo.py --guid <guid> --char <char> [--mode cross_lingual|zero_shot|instruct2]
  [--text "..." --ref x.wav] [--flow-temp F] [--cfg C] [--sampling p,k,tau]
  [--base] [--seed N] [--speed S] [--single] [--lang-token ru] [--out file.wav]
```

Выход: `--out` (склейка) + `{out}__{N}.wav` (части; не класть в Localization!).

### `tools/cosyvoice3_batch.py` — очередь фраз → Localization (resumable)

```bash
... cosyvoice3_batch.py --char Kunrad_Voigtvir [--lang ruRU_cosy]
  [--guid g1 g2 ...] [--limit N] [--force]
```

- Модель грузится один раз (~15–25с), ~1 мин/фраза на CPU
- Пишет только склейку: `Localization/{lang}/{char}/{guid}.wav` (s16, 24kHz)
- Пропускает существующие WAV (без `--force`); обрыв процесса = просто перезапуск
- Конфиг зашит в константы `FLOW_TEMP/CFG_RATE/SAMPLING` в начале файла

### После генерации

```bash
python tools/export_mappings.py --lang ruRU_cosy   # mappings/*.json
python -m pytest tools/test_pipeline.py -q         # проверки (орфаны и пр.)
```

## Грабли

| Симптом | Причина | Фикс |
|---|---|---|
| Мод не играет / искажения | CV3 пишет float32, `mciSendString` ждёт PCM s16 | `--s16` (или `ffmpeg -c:a pcm_s16le`) |
| Правка сэмплинга «протекает» во все модель-диры | старый `hardlink_tree` линковал и yaml | `link_tree`: yaml копируется, веса — hardlink |
| Вздох/дыхание в конце реплики | CV3 умеет `[breath]`, дорисовывает сам | `--tail-trim` СЕЙЧАС ВЫКЛЮЧЕН (резал слова, напр. `ca2ef6c0`); сырьё — `output/cosyvoice3/raw/`, детектор артефактов — TODO (`todo_ruRU_cosy.md`) |
| Шипение в голосе | яркость тембра CV3 >8кГц (+4 дБ к рефу), НЕ шум в паузах | EQ `highshelf=f=8000:g=-6:t=q` (постпроцесс) |
| «Импровизация» | RAS top_p/top_k + flow-temperature | `--flow-temp 1.3` + `0.9,50,0.1` — победный |
| Консоль — кракозябры | cp1251 vs utf-8, только в логе | косметика, текст модели передаётся корректно |
| `CausalConditionalCFM.forward() got unexpected keyword 'prompt_len'` | сигнатура CV3-декодера: `(mu, mask, n_timesteps, temperature, spks, cond, streaming)` | wrapper в `patch_flow_temperature` |

## Документация CV3 (что читать)

- README модели: https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512
- Репозиторий: https://github.com/FunAudioLLM/CosyVoice (`example.py` — канонические вызовы, `[breath]`-токен)
- Офиц. HF Space (эталонный инференс): https://huggingface.co/spaces/FunAudioLLM/Fun-CosyVoice3-0.5B/blob/main/app.py
  (base-модель, zero_shot/instruct2, seed+speed+stream, prompt ≤10с, текст ≤200 симв.)
- vllm-omni конфиг (полная карта параметров): https://docs.vllm.ai/projects/vllm-omni/en/latest/api/vllm_omni/transformers_utils/configs/cosyvoice3/

**Температуры в API нет.** Ручки: RAS (`top_p 0.8`, `top_k 25`, `win_size 10`,
`tau_r 0.1` — в yaml), flow (`inference_cfg_rate 0.7`, скрытый `temperature=1.0`
в `flow_matching.py` — пробрасывается monkeypatch'ем), HiFT (`nsf_alpha 0.1`,
`nsf_sigma 0.003`), `min/max_token_text_ratio 2/20`, `speed`, `seed`.

### Что за что отвечает (3 каскада: LLM → flow → HiFT)

- **`--flow-temp` (t)** — температура диффузии flow-каскада: масштаб стартового
  шума. Ниже (0.5–0.7) = стабильнее интонация, меньше импровизации; выше (1.3+)
  = живее, но уводит в чуждые паттерны → **акцент + нестабильность**. Сток кода 1.0
- **`--cfg` (c)** — CFG-сила flow: насколько выход прижимается к рефу/тексту.
  Ниже 0.7 = голос плавает; выше = стабильнее тембр/произношение, при перегибе
  артефакты. Сток модели 0.7
- **RAS (LLM-каскад, `--sampling p,k,tau`)** — выбор токенов речи: `top_p`
  nucleus-порог, `top_k` потолок кандидатов (ниже оба = детерминированнее
  произношение), `tau_r`×`win_size` — бан повторяющихся токенов (выше = меньше
  «заиканий», больше случайности). Сток 0.8/25/0.1
- Прочее: `seed`, `--base`/RL-веса, `speed`, `--tail-trim` (обрезка вздохов),
  `--s16` (pcm для mciSendString)

**Про акцент:** русский — ~3% датасета (слабейший из 9 языков, 1.5B не выйдет).
Помогает слабо всё кроме: ниже temp/выше cfg (B/C/D-оси) и русский реф вместо
английского (zero_shot, монолингвальный клон). A/B-демки и разбор:
`refs/samples_en_demo_cosy/accent/README.md`.

## Структура выхода (языковая папка)

```
Localization/ruRU_cosy/          # Language=ruRU_cosy в UMM
  Kunrad_Voigtvir/{guid}.wav     # s16 24kHz mono, склейка частей (gap 0.25с)
  mappings/Kunrad_Voigtvir.json  # export_mappings.py
output/cosyvoice3/raw/{char}/    # нетронутое сырьё генерации (для детектора артефактов)
```

## Референсы

- `docs/cosyvoice3.md` — полная история экспериментов (шипение, температура, A/B)
- `todo_ruRU_cosy.md` — план озвучки (Phase 1 Kunrad → Phase 2 образцы)
- `refs/samples_en_demo_cosy/` — утверждённые демки
- `tools/build_cosy_refs.py` — сборка рефов
- Q3-пайплайн (текущий основной): `.opencode/skills/qwen3-full-icl/SKILL.md`
