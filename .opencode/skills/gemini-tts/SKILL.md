---
name: gemini-tts
description: Generate Russian voiceover WAV files via Google Gemini 3.1 Flash TTS (30 voices, online, proxy-friendly).
---

# Gemini TTS — Google Gemini 3.1 Flash TTS Preview

## Контракт (Python)

```python
def generate(text: str, output: str, voice: str = "Kore", proxy: str = "") -> float:
    """
    Args:
        text    — очищенный текст без игровых тегов
        output  — путь до WAV файла
        voice   — имя голоса Gemini (см. таблицу ниже)
        proxy   — HTTP прокси ("http://ip:port" или "")
    Returns:
        float   — длительность в секундах
    """
```

## Python CLI скрипт

`.opencode/skills/gemini-tts/scripts/gemini_tts.py`

```bash
python .opencode/skills/gemini-tts/scripts/gemini_tts.py \
    --text "Привет" --output speech.wav --voice Kore
python .opencode/skills/gemini-tts/scripts/gemini_tts.py \
    --text "Привет" --output speech.wav --voice Kore \
    --proxy http://47.253.201.85:7890
```

## Архитектура

```
gemini-tts (SKILL.md) — точка входа
  │
  └── tools/gemini_tts.py   — Gemini TTS через google.genai
      Контракт: generate(text, output, voice, proxy) -> float
      Зависимости: google.genai (уже установлен)
      Дока: tools/gemini_tts.py (docstring)
```

## 30 голосов Gemini

### Мужские (15)

| Голос | Характер | Кому подходит |
|-------|----------|---------------|
| `Algenib` | Gravelly (хриплый) | Ульфар, Абеляр, Маражай — суровые, грубые |
| `Algieba` | Smooth (плавный) | Дипломаты, обходительные |
| `Alnilam` | Firm (твёрдый) | Соломон, Хайнрикс — авторитет |
| `Charon` | Informative (информативный) | Хайнрикс — чёткий, холодный |
| `Enceladus` | Breathy (с придыханием) | Интимные сцены, шёпот |
| `Fenrir` | Excitable (возбуждённый) | Маражай — энергичный, хищный |
| `Iapetus` | Clear (чистый) | Паскаль — чёткий, техничный |
| `Orus` | Firm (твёрдый) | Соломон, Хайнрикс — аналог Alnilam |
| `Puck` | Upbeat (жизнерадостный) | Молодые солдаты, NPC |
| `Rasalgethi` | Informative (информативный) | Инквизиция, доклады |
| `Sadachbia` | Lively (живой) | Энергичные персонажи |
| `Sadaltager` | Knowledgeable (знающий) | **Кунрад** — мудрый, коварный |
| `Schedar` | Even (ровный) | **Паскаль** — монотонный, машинный |
| `Umbriel` | Easy-going (расслабленный) | **Эдельтрад** — тихий, неуверенный |
| `Zubenelgenubi` | Casual (непринуждённый) | Кунрад — вкрадчивый, светский |

### Женские (15)

| Голос | Характер | Кому подходит |
|-------|----------|---------------|
| `Achernar` | Soft (мягкий) | Кассия, нежные моменты |
| `Aoede` | Breezy (лёгкий) | **Джаэ** — игривая, быстрая |
| `Autonoe` | Bright (яркий) | Молодые, задорные |
| `Callirrhoe` | Easy-going (спокойный) | Йрлиет — меланхоличная |
| `Despina` | Smooth (плавный) | Кибелла — тихая, скользкая |
| `Erinome` | Clear (чистый) | Сестра Арджента — чёткая |
| `Gacrux` | Mature (зрелый) | **Идира** — уставшая, циничная |
| `Kore` | Firm (твёрдый) | **Теодора** — властная, командная |
| `Laomedeia` | Upbeat (энергичный) | Арджента — пламенная |
| `Leda` | Youthful (юный) | Кассия — молодая, ранимая |
| `Pulcherrima` | Forward (напористый) | **Идира** — дерзкая |
| `Sulafat` | Warm (тёплый) | Кассия — добрая, нежная |
| `Vindemiatrix` | Gentle (нежный) | Йрлиет — мягкая, печальная |
| `Zephyr` | Bright (яркий) | Молодые NPC |

## Рекомендуемое распределение по персонажам

| Персонаж | Голос Gemini | Почему |
|----------|-------------|--------|
| **Теодора** | `Kore` (F, Firm) | Властная женщина, командует флотом. Kore — женский твёрдый, идеально |
| **Кунрад** | `Sadaltager` (M, Knowledgeable) | Коварный манипулятор, говорит тихо и опасно. Знающий, вкрадчивый |
| **Абеляр** | `Algenib` (M, Gravelly) | Старый военный, суровый. Хриплый, командный |
| **Эдельтрад** | `Umbriel` (M, Easy-going) | Испуганный юноша. Расслабленный, тихий |
| **Идира** | `Gacrux` (F, Mature) | Уставшая, циничная. Зрелый женский |
| **Хайнрикс** | `Charon` (M, Informative) | Холодный инквизитор. Чёткий, информативный |
| **Арджента** | `Laomedeia` (F, Upbeat) | Пламенная сестра битвы. Энергичный, напористый |
| **Паскаль** | `Schedar` (M, Even) | Техножрец, монотонный. Ровный, без эмоций |
| **Джаэ** | `Aoede` (F, Breezy) | Хитрая, игривая. Лёгкий, быстрый голос |
| **Кассия** | `Sulafat` (F, Warm) + `Leda` (F, Youthful) | Юная навигатор. Тёплая + юная |
| **Йрлиет** | `Vindemiatrix` (F, Gentle) + `Callirrhoe` (F, Easy-going) | Меланхоличная аэльдари. Нежный |
| **Маражай** | `Fenrir` (M, Excitable) | Хищный друкари. Возбуждённый, динамичный |
| **Ульфар** | `Algenib` (M, Gravelly) + `Orus` (M, Firm) | Космодесантник. Хриплый, мощный |
| **Соломон** | `Orus` (M, Firm) | Арбитр, законник. Твёрдый |
| **Кибелла** | `Despina` (F, Smooth) | Ассасин, тихая. Плавная, скользящая |

## Лимиты (бесплатный ключ)

- **~5 RPM** — не более 5 запросов в минуту
- Если превысить — 429 `RESOURCE_EXHAUSTED`
- Ждать минимум **20-25 секунд** между вызовами
- Сброс квоты: ~1 минута после последнего запроса
- Платный: PayGo ~1000 RPM

## Прокси

Обязателен для Беларуси (геоблок). Использовать:

```bash
# Через env var (автоматически)
export HTTPS_PROXY="http://ip:port"

# Или параметром скрипта (--proxy)
python .opencode/skills/gemini-tts/scripts/gemini_tts.py \
    --text "..." --output "..." --voice Kore \
    --proxy http://ip:port
```

Свежие прокси: https://proxyscrape.com/free-proxy-list

## Формат

- Вход: текст (не более ~5000 символов)
- Выход: WAV 24000 Гц, 16-bit, mono
- Внутренний формат: L16 PCM (конвертируется в WAV в Python SDK)

## Важно

- Только **1 запрос за раз**. Никакого параллельного вызова.
- После каждого вызова — пауза 25 сек (дефолт в скрипте).
- API ключ: через `$env:GEMINI_API_KEY` или `config/default.yaml → gemini_api_key`

---

## Подготовка текста для Gemini TTS

Gemini — LLM-модель, а не обычный TTS. Она понимает **контекст, эмоции и персонажа**.
Текст готовится иначе, чем для Silero или SAPI.

### 1. Формат промпта (структура)

```
Synthesize speech for the performance defined below.
The profile, scene, and performance notes are direction only.
Do NOT speak them.
Speak ONLY the lines under #### TRANSCRIPT.

# AUDIO PROFILE: Имя
## "Характеристика в кавычках"

## SCENE: Где и что происходит
2-3 предложения: обстановка, настроение, поза персонажа.

### PERFORMANCE
Style: <эмоциональный регистр, тон>
Pace: <темп речи>
Accent: <акцент, обычно русский>

### CONTEXT
1-2 предложения: кто этот персонаж и почему звучит именно так.

#### TRANSCRIPT
<текст реплики с audio tags через запятые>
```

**Это НЕ нужно вводить каждый раз вручную.** Агент opencode собирает промпт автоматически из `config/characters.yaml` + `--character` параметра.

### 2. Что делает агент автоматически

Агент перед отправкой текста в Gemini:

1. Берёт фразу (сырой текст из игры)
2. Определяет персонажа (GUID → имя из чьего-то маппинга)
3. Берёт `gemini_voice` из `config/characters.yaml`
4. Собирает промпт по шаблону (Audio Profile, Scene, Performance)
5. Оборачивает текст в `#### TRANSCRIPT`
6. Отправляет в `tools/gemini_tts.py` как параметр `text` (весь промпт целиком)

### 3. Audio tags — управление эмоциями

Теги ставятся **внутрь текста** в квадратных скобках. Только на английском, но работают с любым языком.

**Документированные теги:**

| Эмоция | Тег |
|--------|-----|
| Удивление | `[amazed]` |
| Плач | `[crying]` |
| Любопытство | `[curious]` |
| Возбуждение | `[excited]` |
| Вздох | `[sighs]` |
| Восхищённый вдох | `[gasp]` |
| Хихиканье | `[giggles]` |
| Смех | `[laughs]` |
| Озорство | `[mischievously]` |
| Паника | `[panicked]` |
| Сарказм | `[sarcastic]` |
| Серьёзность | `[serious]` |
| Крик | `[shouting]` |
| Усталость | `[tired]` |
| Дрожь | `[trembling]` |
| Шёпот | `[whispers]` |

**Темп:**
`[very fast]`, `[slow]`, `[short pause]`, `[long pause]`

**Дополнительные (200+):**
`[determination]`, `[enthusiasm]`, `[awe]`, `[nervousness]`, `[frustration]`,
`[anger]`, `[annoyance]`, `[amusement]`, `[aggression]`, `[neutral]`,
`[warmly]`, `[thoughtfully]`, `[gently]`, `[cheerfully]`, `[soft laugh]`

### 4. Правила расстановки тегов

1. **Одна эмоция на фразу** — не больше 1-2 тегов короче.
2. **Запятые между теговыми клаузами** — не ставь точки.
   - ✅ `[вздыхает] Я устала от всего этого, [тихо] но надо идти дальше.`
   - ❌ `[вздыхает] Я устала. [тихо] Но надо идти.`
3. **Многоточие (`...`)** — для естественной паузы (1-2 на реплику).
4. **Тире (`—`)** — для микропаузы в мысли.
5. **Теги в начале фразы** задают общий тон.
6. **Не ставь два тега подряд** — между ними должен быть текст.

### 5. Примеры для персонажей

#### Теодора (приказ):
```
Style: Firm, commanding. She does not negotiate, she dictates.
Pace: Measured, deliberate. Pauses land like hammer blows.

#### TRANSCRIPT
Выполните приказ, [short pause] или я найду того, кто его выполнит.
```

#### Кунрад (интрига):
```
Style: Quiet, manipulative. Every word is a chess move.
Pace: Slow, with deliberate pauses. The silence is part of the threat.

#### TRANSCRIPT
Вы уверены, что хотите знать правду? [short pause] [тихо] Некоторые истины лучше оставить погребёнными.
```

#### Абеляр (доклад):
```
Style: Gruff, professional. Old soldier reporting to his commander.
Pace: Steady, no rush. He's done this a thousand times.

#### TRANSCRIPT
Лорд-капитан, [short pause] инженариум докладывает: поле Геллера стабильно, [short pause] варп-двигатели в норме.
```

#### Джаэ (хитрость):
```
Style: Playful, mischievous. She's enjoying this.
Pace: Bouncy, with quick rhythm.

#### TRANSCRIPT
[смеётся] О, я знаю пару трюков, которые вас удивят, [short pause] [игриво] если, конечно, у вас хватит смелости попробовать.
```

### 6. Чего НЕ надо делать

- **Не пиши "тихо", "монотонно", "ровно"** в Style/Pace — Gemini читает это буквально и звучит плоско.
  ✅ `"Голос понижен на октаву, но полный чувства"` вместо `"тихо"`.
- **Не цитируй слова из текста** в описании стиля — Gemini может их прочитать вслух.
- **Не используй SSML** (`<prosody>`, `<break>`) — Gemini их не понимает, используй audio tags.
- **Не ставь точки между тегами** — звучит рублено. Используй запятые.
- **Не оставляй сырые игровые теги** — `[formal]`, `[female]`, `[b]` HTML и BB-коды надо удалить.

### 7. Очистка текста от игровой разметки

Cырой текст из `{Language}.json` содержит игровую разметку. Агент перед отправкой должен:

1. Удалить HTML: `<b>`, `<i>`, `<color=...>`, `<size=...>`
2. Удалить BB-коды: `[b]`, `[i]`, `[formal]`, `[female]`
3. Удалить лишние пробелы и переносы строк
4. Заменить игровые плейсхолдеры: `{name}` → `лорд-капитан` и т.д.

Вспомогательная функция в `tools/text_clean.py` (будет создана при необходимости).
