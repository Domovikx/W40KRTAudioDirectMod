# План генерации TTS

**Приоритет:** Sound.json (5089 фраз с Wwise event'ами). ruRU-only (34319) — после.

## Статус

- ✅ Теодора (99) — готова
- ✅ Кунрад (66) — готов
- ⬜ Остальные Sound.json: **4924 фразы**

## Очередь (Sound.json, по убыванию)

| #   | Персонаж               | Голос          | Фраз | Время (~) |
| --- | ---------------------- | -------------- | ---- | --------- |
| 1   | Solomon Antar          | solomon        | 486  | ~9ч       |
| 2   | Cassia Orsellio        | cassia         | 440  | ~8ч       |
| 3   | Heinrix van Calox      | heinrix        | 410  | ~7.5ч     |
| 4   | Kibellah               | kibellah       | 400  | ~7ч       |
| 5   | Yrliet Lanaeviss       | yrliet         | 329  | ~6ч       |
| 6   | Marazhai Aezyrraesh    | marazhai       | 325  | ~6ч       |
| 7   | Pasqal Haneumann       | pasqal         | 319  | ~6ч       |
| 8   | Ulfar                  | ulfar          | 286  | ~5ч       |
| 9   | Sister Argenta         | argenta        | 264  | ~5ч       |
| 10  | Abelard Werserian      | abelard        | 255  | ~4.5ч     |
| 11  | Jae Heydari            | jae            | 248  | ~4.5ч     |
| 12  | Idira Tlass            | idira          | 247  | ~4.5ч     |
| 13  | Generic Male NPC       | default_male   | 227  | ~4ч       |
| 14  | Smuggler               | default_male   | 175  | ~3ч       |
| 15  | Manipulus              | manipulus      | 175  | ~3ч       |
| 16  | Eogann                 | eogann         | 104  | ~2ч       |
| 17  | Theodora von Valancius | teodora        | 99   | ✅        |
| 18  | Psyker (NPC)           | default_male   | 91   | ~1.5ч     |
| 19  | Narrator (NARR)        | wh40k_narrator | 16   | ~20м      |
| 20  | Kunrad Voigtvir        | kunrad         | 66   | ✅        |
| 21  | Seneschal (NPC)        | default_male   | 63   | ~1ч       |
| 22  | Trazyn                 | trazyn         | 63   | ~1ч       |
| 23  | Arbites (NPC)          | default_male   | 1    | ~1м       |

## Команда для одного персонажа

```bash
python tools/qwen3_full_icl.py --char "Имя Персонажа"
```

## Повторная генерация

Скрипт **игнорирует уже существующие WAV** (idempotent). Можно прерывать и продолжать.
