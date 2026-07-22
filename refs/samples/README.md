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

## Текущие файлы

| Файл                    | Длина | Каналы | RMS   |
| ----------------------- | ----- | ------ | ----- |
| Андрей Кравец.wav       | 15.8s | моно   | -23dB |
| Всеволод Кузнецов.wav   | 14.7s | моно   | -23dB |
| Иван Литвинов.wav       | 15.3s | моно   | -23dB |
| Наталья Казначеева.wav  | 14.8s | моно   | -23dB |
| Никита Прозоровский.wav | 15.6s | моно   | -23dB |
