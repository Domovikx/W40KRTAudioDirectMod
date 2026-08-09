# W40KRT Audio Direct Mod

**Русская AI-озвучка для Warhammer 40,000: Rogue Trader**

Замена английской диалоговой озвучки на русскую через AI-генерацию (TTS) с голосовым клонированием. Работает через Unity Mod Manager (встроен в игру).

<p align="center">
  <img src="assets/portraits/0001/Fulllength.png" alt="Rogue Trader Portrait" width="400">
</p>

[![Version](https://img.shields.io/badge/version-0.0.2-blue)](Info.json)
[![WAV](https://img.shields.io/badge/WAV%20сгенерировано-3494-success)](Localization/ruRU/)
[![Готово](https://img.shields.io/badge/прогресс-9.8%25-yellow)](Localization/ruRU/)
[![Персонажи](https://img.shields.io/badge/персонажей-23-orange)](Localization/ruRU/)
[![Голосов](https://img.shields.io/badge/голосов-21-lightgrey)](config/voices.yaml)
[![UMM](https://img.shields.io/badge/Unity%20Mod%20Manager-0.25.0-green)](Info.json)

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
| `Language`         | ruRU      | Языковая папка для WAV       |
| `DuckLevel`        | 50        | Приглушение игры (%)         |
| `MuteEnglishVoice` | true      | Выключить английскую озвучку |

---

## Статус озвучки

| Статус | Персонажи |
|--------|-----------|
| ✅ 100% | Heinrix, Theodora, Kunrad, Environment |
| 🟨 99.8% | Abelard (осталась 1 фраза) |
| 🟨 87% | Seneschal NPC |
| 🔴 0-16% | Остальные 17 персонажей |

**Всего:** 3 494 WAV / 35 716 фраз (9.8%).

---

## Использованные технологии

- [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) — Voice Clone
- [Harmony](https://github.com/pardeike/Harmony) — IL-патчинг
- [Unity Mod Manager](https://www.nexusmods.com/site/mods/21)
- Wwise (AkSoundEngine) — ducking

---

## Лицензия

Некоммерческое использование. WAV-файлы сгенерированы AI.

---

<p align="center">
  <a href="https://github.com/Domovikx/W40KRTAudioDirectMod">GitHub</a>
</p>
