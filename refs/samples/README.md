# Voice Reference Samples

Референсные образцы голосов актёров для Full ICL (Qwen3-TTS Base model).

## Формат

- **Формат:** WAV (PCM s16le), 48000 Hz, **моно**
- **Громкость:** нормализована до RMS = -23dB (EBU R128)
- **Длина:** ~15 секунд
- **Имя файла:** `{Имя Фамилия}.wav` (с пробелом)

## Нормализация

Если добавляешь новый файл, выровняй громкость:

```bash
# 1. Измерить RMS
python3 -c "
import wave, numpy as np
with wave.open('file.wav') as wf:
    data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    if wf.getnchannels() > 1:
        data = data.reshape(-1, wf.getnchannels()).mean(axis=1)
    rms = 20*np.log10(np.sqrt(np.mean(data.astype(np.float64)**2))/32768)
    print(f'RMS={rms:.1f}dB')
"

# 2. Применить gain до -23dB RMS (gain = -23 - current_RMS)
ffmpeg -y -i file.wav -af "volume=<gain>dB" file_norm.wav

# 3. Если стерео — свести в моно
ffmpeg -y -i file.wav -ac 1 -ar 48000 file_mono.wav
```

## Текущие файлы (22 референса + 2 демо)

| Файл                          | Длина | Каналы | RMS   |
| ----------------------------- | ----- | ------ | ----- |
| Аглая Шиловская.wav           | ~15s  | моно   | -23dB |
| Александр Клюквин.wav         | ~15s  | моно   | -23dB |
| Алексей Мясников.wav          | ~15s  | моно   | -23dB |
| Анастасия Лапина.wav          | ~15s  | моно   | -23dB |
| Андрей Кравец.wav             | ~15s  | моно   | -23dB |
| Вадим Медведев.wav            | ~15s  | моно   | -23dB |
| Владимир Антоник.wav          | ~15s  | моно   | -23dB |
| Всеволод Кузнецов.wav         | ~15s  | моно   | -23dB |
| Денис Некрасов.wav            | ~15s  | моно   | -23dB |
| Елена Соловьёва.wav           | ~15s  | моно   | -23dB |
| Иван Литвинов.wav             | ~15s  | моно   | -23dB |
| Ирина Киреева.wav             | ~15s  | моно   | -23dB |
| Лина Иванова.wav              | ~15s  | моно   | -23dB |
| Михаил Пшеничный.wav          | ~15s  | моно   | -23dB |
| Михаил Хрусталёв.wav          | ~15s  | моно   | -23dB |
| Наталья Казначеева.wav        | ~15s  | моно   | -23dB |
| Никита Прозоровский.wav       | ~15s  | моно   | -23dB |
| Олег Куценко.wav              | ~15s  | моно   | -23dB |
| Ольга Голованова.wav          | ~15s  | моно   | -23dB |
| Сергей Чихачёв.wav            | ~15s  | моно   | -23dB |
| Сергей Чихачёв 2.wav          | ~15s  | моно   | -23dB |
| Сергей Чонишвили.wav          | ~15s  | моно   | -23dB |
| demo/Сергей Чихачёв_demo.wav  | demo  | моно   | -23dB |
| demo/Сергей Чихачёв 2_demo.wav| demo  | моно   | -23dB |
