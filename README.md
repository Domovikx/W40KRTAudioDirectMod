# W40KRT Audio Direct Mod — русская нейро-озвучка Warhammer 40,000: Rogue Trader

**Русская озвучка Warhammer 40,000: Rogue Trader** — мод заменяет английскую озвучку диалогов, барков и описаний окружения на русскую, сгенерированную нейросетью **Qwen3-TTS** через **Voice Clone** (AI TTS, клонирование голосов оригинальных актёров). Работает через **Unity Mod Manager** (встроен в игру).

[![Version](https://img.shields.io/badge/version-0.0.2-blue)](Info.json)
[![WAV](https://img.shields.io/badge/WAV%20сгенерировано-21%20760-success)](Localization/ruRU/)
[![Готово](https://img.shields.io/badge/прогресс-61%25-yellow)](Localization/ruRU/)
[![Персонажи](https://img.shields.io/badge/персонажей-23-orange)](Localization/ruRU/)
[![Голосов](https://img.shields.io/badge/голосов-21-lightgrey)](config/voices.yaml)
[![CosyVoice 3](https://img.shields.io/badge/CosyVoice%203-эксперимент-blueviolet)](Localization/ruRU_cosy/)
[![UMM](https://img.shields.io/badge/Unity%20Mod%20Manager-0.25.0-green)](Info.json)

<p align="center">
  <img src="assets/portraits/0001/Fulllength.png" alt="Rogue Trader Portrait" width="400">
</p>

---

## О моде

Мод заменяет английскую озвучку диалогов, барков и описаний окружения в **Warhammer 40,000: Rogue Trader** на русскую, сгенерированную нейросетью **Qwen3-TTS Base** через механизм Voice Clone.

### Особенности

- Работает с любыми диалогами, барками, описаниями окружения
- Голос клонирован по оригинальным английским референсам из игры
- Настройка громкости озвучки в меню мода
- Регулировка приглушения игры (duck level) 0–100%
- Опция отключения английской озвучки
- Плавный возврат громкости после реплики

---

## Установка

Игра **уже содержит** Unity Mod Manager — ничего дополнительно устанавливать не нужно.

1. Скачайте архив: **[W40KRTAudioDirectMod-v0.0.2.zip](https://github.com/Domovikx/W40KRTAudioDirectMod/archive/refs/tags/v0.0.2.zip)** (~2.1 ГБ, содержит WAV-файлы озвучки)
2. Распакуйте в `%userprofile%\AppData\LocalLow\Owlcat Games\Warhammer 40000 Rogue Trader\UnityModManager\`
3. Должна получиться папка `W40KRTAudioDirectMod` с `Info.json`, `W40KRTAudioDirectMod.dll` и `Localization\ruRU\`
4. Запустите игру, нажмите **Ctrl+F10** → мод появится в списке

### Настройки

| Параметр           | По умолч. | Описание                     |
| ------------------ | --------- | ---------------------------- |
| `Volume`           | 100       | Громкость озвучки (%)        |
| `Language`         | ruRU_cosy | Языковая папка для WAV (CosyVoice3 / Qwen3) |
| `DuckLevel`        | 50        | Приглушение игры (%)         |
| `MuteEnglishVoice` | true      | Выключить английскую озвучку |

---

## Статус озвучки

**Всего: 21 760 WAV / 35 716 фраз (60.9%).**

| Статус | Персонажи |
|--------|-----------|
| ✅ 100% | Abelard, Cassia, Eogann, Heinrix, Idira, Jae, Kibellah, Kunrad, Manipulus, Marazhai, Narrator, Pasqal, Seneschal NPC, Sister Argenta, Smuggler, Solomon, Theodora, Trazyn, Ulfar, Yrliet, Environment |
| 🟨 44.2% | Generic Male NPC (11 000 / 24 862) |
| 🔴 3.1% | Psyker NPC (3 / 97) |

### Озвучка CosyVoice 3

По умолчанию мод использует **CosyVoice 3** (`Localization\ruRU_cosy\`).
Для переключения на Qwen3-TTS нажмите кнопку **Qwen3** в GUI мода (UMM → Settings).
Текущий статус CV3: 10 персонажей, 197 WAV.

---

## Использованные технологии

- [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) — Voice Clone (основной движок)
- [CosyVoice 3](https://github.com/FunAudioLLM/CosyVoice) — zero-shot voice clone (эксперимент, ruRU_cosy)
- [Harmony](https://github.com/pardeike/Harmony) — IL-патчинг
- [Unity Mod Manager](https://www.nexusmods.com/site/mods/21)
- Wwise (AkSoundEngine) — ducking

---

## Ключевые слова

русская озвучка Rogue Trader · Russian voiceover Warhammer 40k · нейроозвучка Вархаммер · AI TTS мод · voice clone Qwen3 · замена озвучки Unity Mod Manager · русская озвучка WH40KRT · озвучка диалогов нейросетью · Warhammer 40000 русский дубляж

---

## Лицензия

Некоммерческое использование. WAV-файлы сгенерированы AI.

---

<p align="center">
  <a href="https://github.com/Domovikx/W40KRTAudioDirectMod">GitHub</a>
</p>
