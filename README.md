# W40KRT Audio Direct Mod

**Русская AI-озвучка для Warhammer 40,000: Rogue Trader**

Замена английской диалоговой озвучки на русскую через AI-генерацию (TTS) с голосовым клонированием. Работает через Unity Mod Manager — перехватывает текст диалогов и воспроизводит соответствующие WAV-файлы.

<p align="center">
  <img src="assets/portraits/0001/Fulllength.png" alt="Rogue Trader Portrait" width="400">
</p>

[![Version](https://img.shields.io/badge/version-0.0.1-blue)](Info.json)
[![Phrases](https://img.shields.io/badge/фраз%20в%20каталоге-39.408-blueviolet)](catalog/people/index.yaml)
[![Сгенерировано](https://img.shields.io/badge/WAV%20в%20игре-168-success)](Localization/ruRU/)
[![Персонажи](https://img.shields.io/badge/персонажей-25-orange)](catalog/people/)
[![Voice](https://img.shields.io/badge/голосов-20-lightgrey)](config/voices.yaml)
[![.NET](https://img.shields.io/badge/.NET-4.8.1-512BD4)](W40KRTAudioDirectMod.csproj)
[![UMM](https://img.shields.io/badge/Unity%20Mod%20Manager-0.25.0-green)](Info.json)

---

## О моде

Мод заменяет английскую озвучку диалогов в **Warhammer 40,000: Rogue Trader** на русскую, сгенерированную нейросетью **Qwen3-TTS Base** через механизм Voice Clone (Full ICL).

Каждый персонаж говорит голосом профессионального актёра дубляжа — голос клонирован по референсным записям дикторов.

### Как это работает

1. **Harmony-патчи** перехватывают `DialogVM.HandleOnCueShow` и `TMP_Text.set_text`
2. GUID диалоговой реплики сопоставляется с WAV-файлом в `Localization/ruRU/`
3. WAV воспроизводится через `winmm.dll mciSendString()` с регулировкой громкости
4. На время реплики приглушаются музыка и звуки (ducking) через Wwise RTPC

### Особенности

- Работает с любыми диалогами — сюжетными, побочными, случайными
- Настройка громкости озвучки в меню мода
- Регулировка приглушения игры (duck level) 0–100%
- Опция полного отключения английской озвучки
- Автоматический плавный возврат громкости после реплики

---

## Установка

1. Установите [Unity Mod Manager](https://www.nexusmods.com/site/mods/21) (v0.25+)
2. Скачайте последний релиз `W40KRTAudioDirectMod.dll`
3. Поместите в папку `%userprofile%\AppData\LocalLow\Owlcat Games\Warhammer 40000 Rogue Trader\UnityModManager\W40KRTAudioDirectMod\`
4. Скопируйте папку `Localization/ruRU/` туда же (содержит WAV-файлы озвучки)
5. Запустите игру через Unity Mod Manager

### Настройки

Параметры сохраняются в `Settings.xml`:

| Параметр | По умолчанию | Описание |
|---|---|---|
| `Volume` | 100 | Громкость озвучки (%) |
| `Language` | ruRU | Языковая папка для WAV |
| `DuckLevel` | 50 | Приглушение игры (%) |
| `MuteEnglishVoice` | true | Выключить английскую озвучку |

---

## Персонажи и актёры

| Персонаж | Актёр дубляжа | Фраз в каталоге |
|---|---|---|
| Narrator (Narrator) | Сергей Чонишвили | 4 374 |
| Abelard Werserian | Михаил Пшеничный | 403 |
| Heinrix van Calox | Никита Прозоровский | 410 |
| Pasqal Haneumann | Александр Клюквин | 408 |
| Sister Argenta | Елена Соловьёва | 382 |
| Idira Tlass | Аглая Шиловская | 412 |
| Cassia Orsellio | Анастасия Лапина | 656 |
| Jae Heydari | Ирина Киреева | 248 |
| Yrliet Lanaeviss | Лина Иванова | 329 |
| Kibellah | Ольга Голованова | 579 |
| Kunrad Voigtvir | Всеволод Кузнецов | 67 |
| Theodora von Valancius | Наталья Казначеева | 102 |
| Solomon Antar | Олег Куценко | 607 |
| Ulfar | Алексей Мясников | 358 |
| Marazhai Aezyrraesh | Сергей Чихачёв | 553 |
| Edelthrad | Иван Литвинов | — |
| Eogann | Андрей Кравец | 207 |
| Manipulus | Владимир Антоник | 204 |
| Trazyn | Вадим Медведев | 66 |
| Generic Male NPC | Денис Некрасов | 28 661 |

> **Всего:** 25 персонажей, 21 голос, 39 408 фраз в каталоге

---

## Сбор английских референсов (English Voice Samples)

### Что это

`refs/samples_en/` содержит английские голосовые образцы (WAV, ~16 сек) для всех персонажей. Используются как референс для Voice Clone — из оригинальной английской озвучки игры.

### Метод поиска

Английская озвучка диалогов хранится в `.pck` файлах игры (Wwise Audio Packages) в формате RIFF/WAVE.

**Цепочка маппинга:**

```
enGB.json (GUID → English text)
  → catalog/people/*.yaml (GUID → speaker)
    → Whisper ASR (аудио → текст)
      → text matching → speaker identification
```

**Процесс:**

1. Извлечение RIFF/WAVE структур из `WH40KRT_Main_Dialogues.pck`, `WH40KRT_DLC3_Dialogues.pck` и других `.pck` файлов
2. Конвертация через `vgmstream-cli.exe` (Custom Vorbis → PCM WAV)
3. Транскрибация через Whisper `tiny.en`
4. Сравнение транскрибированного текста с enGB.json через word overlap
5. Определение персонажа через catalog YAML (GUID → speaker)
6. Склеивание лучших клипов до ~16 секунд, нормализация -23dB RMS

**Скрипты:**
- `tools/filter_noncompanion.py` — фильтрация WAV компаньонов
- `tools/identify_dialog.py` — Whisper + text matching (Main_Dialogues)
- `tools/find_eogann_trazyn.py` — поиск по DLC-диалогам
- `tools/extract_main_dialogues.py` — извлечение RIFF из Main_Dialogues.pck

### Источники диалогов

Все английские диалоги находятся в `.pck` файлах в формате RIFF/WAVE (Wwise Custom Vorbis, 48000Hz, 1ch):

| PCK файл | Размер | RIFF-клипов | Персонажи |
|---|---|---|---|
| `WH40KRT_Main_Dialogues.pck` | 660 MB | 2 644 | Все основные диалоги |
| `WH40KRT_DLC3_Dialogues.pck` | 135 MB | 586 | Eogann, Trazyn (DLC3) |
| `WH40KRT_NARR_PRL.pck` | 92 MB | 586 | Kunrad, Theodora (пролог) |
| `WH40KRT_NARR_CH01-05.pck` | ~520 MB | 2 773 | Chapter-специфичные диалоги |
| `WH40KRT_NARR_DLC1.pck` | 232 MB | 562 | DLC1 |

Всего обработано **~7 000 RIFF/WAVE клипов**, идентифицировано **~1 900** (остальное SFX).

---

## Статус референсов

### English refs (`refs/samples_en/`) — статус по персонажам

| Персонаж | RU актёр | RU sample | EN sample | Длительность |
|---|---|---|---|---|
| Narrator | Сергей Чонишвили | ✅ | ❌ * | — |
| Abelard Werserian | Михаил Пшеничный | ✅ | ✅ | 16s |
| Heinrix van Calox | Никита Прозоровский | ✅ | ✅ | 15s |
| Pasqal Haneumann | Александр Клюквин | ✅ | ✅ | 16s |
| Sister Argenta | Елена Соловьёва | ✅ | ✅ | 16s |
| Idira Tlass | Аглая Шиловская | ✅ | ✅ | 16s |
| Cassia Orsellio | Анастасия Лапина | ✅ | ✅ | 16s |
| Jae Heydari | Ирина Киреева | ✅ | ✅ | 15s |
| Yrliet Lanaeviss | Лина Иванова | ✅ | ✅ | 16s |
| Kibellah | Ольга Голованова | ✅ | ✅ | 16s |
| Kunrad Voigtvir | Всеволод Кузнецов | ✅ | ✅ | 16s |
| Theodora von Valancius | Наталья Казначеева | ✅ | ✅ | 16s |
| Solomon Antar | Олег Куценко | ✅ | ✅ | 16s |
| Ulfar | Алексей Мясников | ✅ | ✅ | 16s |
| Marazhai Aezyrraesh | Сергей Чихачёв | ✅ | ✅ | 20s |
| Edelthrad | Иван Литвинов | ✅ | ✅ | 16s |
| Eogann | Андрей Кравец | ✅ | ✅ | 16s |
| Manipulus | Владимир Антоник | ✅ | ✅ | 20s |
| Trazyn | Вадим Медведев | ✅ | ✅ | 16s |
| Generic Male NPC | Денис Некрасов | ✅ | ❌ | — |
| Generic Female NPC | Елена Чебатуркина | ✅ | ❌ | — |

> * Narrator — английские narration-блоки принадлежат разным персонажам сцены, отдельного диктора нет

**Итого:** 18/21 голосов имеют английские референсы ✅, 3缺失 (Narrator, default_male, default_female)

### Сгенерировано WAV

| Персонаж | Сгенерировано WAV |
|---|---|
| Kunrad Voigtvir | 66 |
| Theodora von Valancius | 99 |
| Narrator | 2 |
| Generic Male NPC | 1 |
| **Итого в игре** | **168** |

Также сгенерировано ~514 демо-файлов в `output/full_icl/` (в разработке).

---

## Технические детали

- **Язык:** C# (.NET 4.8.1)
- **Мод-менеджер:** Unity Mod Manager
- **Патчинг:** Harmony 2.x
- **Аудио:** winmm.dll / Wwise RTPC (SetRTPCValue)
- **TTS-модель:** Qwen3-TTS-12Hz-1.7B-Base (Full ICL / Voice Clone)
- **Голосовые референсы:** 22 образца профессиональных актёров дубляжа
- **Каталог фраз:** авто-парсинг из локализационных JSON + Wwise event names
- **Определение спикера:** двухстадийный алгоритм (Wwise events → narration fallback)

### Компиляция из исходников

```bash
compile.bat
```

Или через MSBuild:

```bash
msbuild W40KRTAudioDirectMod.csproj
```

---

## Структура репозитория

```
W40KRTAudioDirectMod/
├── Main.cs                     # Основной код мода (патчи, воспроизведение, ducking)
├── W40KRTAudioDirectMod.csproj # MSBuild проект
├── compile.bat                 # Сценарий компиляции
├── Info.json                   # Метаданные мода
├── Settings.xml                # Настройки
├── Localization/ruRU/          # WAV-файлы озвучки
├── catalog/people/             # Каталог фраз по персонажам (YAML)
├── config/
│   ├── default.yaml            # Конфигурация TTS
│   └── voices.yaml             # Маппинг голосов и актёров
├── tools/                      # Python-скрипты генерации
│   ├── qwen3_full_icl.py       # Основная генерация через Qwen3-TTS Voice Clone
│   ├── generate_demo.py        # Демо русских голосов
│   ├── generate_demo_en.py     # Демо английских референсов
│   └── concat_samples.py       # Склейка WAV
├── docs/characters/            # Описания персонажей
├── refs/samples_en/            # Английские референсы из игры (для Voice Clone)
└── assets/portraits/           # Портреты
```

---

## Использованные технологии

- [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) — Base модель для Voice Clone
- [Harmony](https://github.com/pardeike/Harmony) — IL-патчинг .NET
- [Unity Mod Manager](https://www.nexusmods.com/site/mods/21) — загрузчик модов
- Wwise (AkSoundEngine) — ducking звуков
- PowerShell / Python — инструменты генерации

---

## Лицензия

Проект распространяется для некоммерческого использования. Все WAV-файлы сгенерированы AI и не являются оригинальной озвучкой игры.

---

<p align="center">
  <a href="https://github.com/Domovikx/W40KRTAudioDirectMod">GitHub</a>
</p>
