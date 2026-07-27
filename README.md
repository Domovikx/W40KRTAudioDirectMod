# W40KRT Audio Direct Mod

**Русская AI-озвучка для Warhammer 40,000: Rogue Trader**

Замена английской диалоговой озвучки на русскую через AI-генерацию (TTS) с голосовым клонированием. Работает через Unity Mod Manager.

<p align="center">
  <img src="assets/portraits/0001/Fulllength.png" alt="Rogue Trader Portrait" width="400">
</p>

[![Version](https://img.shields.io/badge/version-0.0.1-blue)](Info.json)
[![Phrases](https://img.shields.io/badge/фраз%20в%20каталоге-39.4K-blueviolet)](catalog/people/index.yaml)
[![Сгенерировано](https://img.shields.io/badge/WAV%20в%20игре-180-success)](Localization/ruRU/)
[![Персонажи](https://img.shields.io/badge/персонажей-26-orange)](catalog/people/)
[![Voice](https://img.shields.io/badge/голосов-21-lightgrey)](config/voices.yaml)
[![.NET](https://img.shields.io/badge/.NET-4.8.1-512BD4)](W40KRTAudioDirectMod.csproj)
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

1. Установите [Unity Mod Manager](https://www.nexusmods.com/site/mods/21) (v0.25+)
2. Скачайте последний релиз `W40KRTAudioDirectMod.dll`
3. Поместите в `%userprofile%\AppData\LocalLow\Owlcat Games\Warhammer 40000 Rogue Trader\UnityModManager\W40KRTAudioDirectMod\`
4. Скопируйте папку `Localization/ruRU/` туда же (WAV-файлы)
5. Запустите игру через Unity Mod Manager

### Настройки

| Параметр           | По умолч. | Описание                     |
| ------------------ | --------- | ---------------------------- |
| `Volume`           | 100       | Громкость озвучки (%)        |
| `Language`         | ruRU      | Языковая папка для WAV       |
| `DuckLevel`        | 50        | Приглушение игры (%)         |
| `MuteEnglishVoice` | true      | Выключить английскую озвучку |

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
