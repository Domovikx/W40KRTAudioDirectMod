# План генерации TTS

**Приоритет:** Sound.json (5089 фраз с Wwise event'ами). ruRU-only (34319) — после.

## Статус

- ✅ Кунрад (68) — готов, все 7 speaker_override валидны
- 🔄 Теодора (102) — 52/102 (+50), 12 speaker_override
- ⬜ Остальные Sound.json: ~4919 фраз

## Очередь (Sound.json, по убыванию)

| #   | Персонаж                 | Голос          | Фраз | Overrides | Статус    |
| --- | ------------------------ | -------------- | ---- | --------- | --------- |
| 1   | Solomon Antar            | solomon        | 486  | 0         | ⬜        |
| 2   | Cassia Orsellio          | cassia         | 440  | 21        | ⬜        |
| 3   | Heinrix van Calox        | heinrix        | 410  | 0         | ⬜        |
| 4   | Kibellah                 | kibellah       | 400  | 3         | ⬜        |
| 5   | Yrliet Lanaeviss         | yrliet         | 329  | 8         | ⬜        |
| 6   | Marazhai Aezyrraesh      | marazhai       | 325  | 11        | ⬜        |
| 7   | Pasqal Haneumann         | pasqal         | 319  | 2         | ⬜        |
| 8   | Ulfar                    | ulfar          | 286  | 0         | ⬜        |
| 9   | Sister Argenta           | argenta        | 264  | 3         | ⬜        |
| 10  | Abelard Werserian        | abelard        | 255  | 1         | ⬜        |
| 11  | Jae Heydari              | jae            | 248  | 1         | ⬜        |
| 12  | Idira Tlass              | idira          | 247  | 1         | ⬜        |
| 13  | Generic Male NPC         | default_male   | 227  | 30        | ⬜        |
| 14  | Smuggler                 | default_male   | 175  | 0         | ⬜        |
| 15  | Manipulus                | manipulus      | 175  | 0         | ⬜        |
| 16  | Eogann                   | eogann         | 104  | 0         | ⬜        |
| 17  | Theodora von Valancius   | teodora        | 102  | 12        | 🔄 52/102 |
| 18  | Psyker (NPC)             | default_male   | 91   | 0         | ⬜        |
| 19  | Narrator (NARR)          | wh40k_narrator | 16   | 0         | ⬜        |
| 20  | Kunrad Voigtvir          | kunrad         | 68   | 7         | ✅        |
| 21  | Seneschal (NPC)          | default_male   | 63   | 0         | ⬜        |
| 22  | Trazyn                   | trazyn         | 63   | 7         | ⬜        |
| 23  | Environment Descriptions | —              | 1    | 0         | ⬜        |

## Команда для одного персонажа

```bash
python tools/qwen3_full_icl.py --char "Abelard Werserian"
```

## Повторная генерация

Скрипт **игнорирует уже существующие WAV** (idempotent). Можно прерывать и продолжать.
Если были изменены speaker_override — старые кэш-части удалить вручную из `output/full_icl/`.
