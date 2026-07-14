---
name: ssml-builder
description: Enrich cleaned Russian dialog text with SSML tags (prosody, break, emphasis) for TTS generation via System.Speech.SpeechSynthesizer.SpeakSsml(). Handles rate-to-prosody conversion, pause insertion, and keyword emphasis for W40KRT mod.
---

# ssml-builder

## What I do

- Take cleaned dialog text + voice config → return SSML-marked string
- Add `<prosody rate="+N%">` based on `rate` param (Rate 2 = +40%)
- Insert `<break time="...ms"/>` after sentences for controlled pause length
- Add `<emphasis level="moderate">` on key terms (Warp, Geller Field, Warrant, etc.)
- Ensure valid SSML that .NET SpeakSsml() can consume

## SSML Rules (Critical!)

### DO use:

- `<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="ru-RU">`
- `<prosody rate="+N%">` — N = rate × 20 (Rate 2 → +40%)
- `<break time="200ms"/>` — between sentences, after `.` `!` `?` `...`
- `<emphasis level="moderate">keyword</emphasis>` — sparingly, only key terms
- `<emphasis level="strong">` — rarely, for dramatic moments

### DO NOT use:

- `lang="ru-RU"` without `xml:` prefix — causes "Invalid element" error
- Unclosed tags or invalid XML entities

## Rate → Prosody mapping

| Rate | Prosody | Notes           |
| ---- | ------- | --------------- |
| 0    | `+0%`   | Default speed   |
| 1    | `+20%`  | Slightly fast   |
| 2    | `+40%`  | **Recommended** |
| 3    | `+60%`  | Fast            |
| 4    | `+80%`  | Very fast       |

## Pause strategy

- End of sentence (`.!?`): `<break time="{pause_ms}ms"/>` where pause_ms is 100-200ms by default
- Ellipsis (`...`): `<break time="300ms"/>` (longer, trailing off)
- Between clauses (`,`): no break, natural SAPI pause is enough

## Emphasis strategy

Only apply emphasis to:

- **Proper nouns**: `Варп`, `Поле Геллера`, `Патент`, `Имматериум`, `Астрономикон`
- **Critical actions**: `предательство`, `убита`, `бунт`, `еретик`
- **Character names** (first mention): use `level="moderate"`
- Do NOT overuse — 1-2 emphasis per sentence max

## Input format (from staging/preview.yaml)

```yaml
guid: "3e99ad83-..."
text_clean: "Я не получал сообщений из инженариума о сбоях в Поле Геллера..."
voice: "Microsoft Dmitry Online"
rate: 2
pause_ms: 150
```

## Output format (update preview.yaml in-place)

```yaml
guid: "3e99ad83-..."
text_clean: "..."
ssml: '<speak version="1.0" ...>...</speak>'
status: "draft"
```

## Example

### Input:

```
text_clean: "Что? Теодора... мертва? Нет! Этого не могло произойти!"
rate: 2
pause_ms: 150
```

### Output SSML:

```xml
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="ru-RU">
  <prosody rate="+40%">
    Что?<break time="150ms"/>
    Теодора...<break time="300ms"/>
    мертва?<break time="150ms"/>
    Нет!<break time="150ms"/>
    Этого не могло произойти!
  </prosody>
</speak>
```
