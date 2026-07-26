# Voice Reference Samples

Референсные образцы голосов актёров для Full ICL (Qwen3-TTS Base model).

## Формат

- **Формат:** WAV (PCM s16le), 48000 Hz, **моно**
- **Громкость:** нормализована до RMS = -23dB (EBU R128)
- **Длина:** ~15 секунд
- **Имя файла:** `{Name_Surname}.wav` (транслит, нижнее подчёркивание)

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

| Файл                               | Длина | Каналы | RMS   |
| ---------------------------------- | ----- | ------ | ----- |
| Aglaya_Shilovskaya.wav             | ~15s  | моно   | -23dB |
| Aleksandr_Klyukvin.wav             | ~15s  | моно   | -23dB |
| Aleksey_Myasnikov.wav              | ~15s  | моно   | -23dB |
| Anastasiya_Lapina.wav              | ~15s  | моно   | -23dB |
| Andrey_Kravets.wav                 | ~15s  | моно   | -23dB |
| Vadim_Medvedev.wav                 | ~15s  | моно   | -23dB |
| Vladimir_Antonik.wav               | ~15s  | моно   | -23dB |
| Vsevolod_Kuznetsov.wav             | ~15s  | моно   | -23dB |
| Denis_Nekrasov.wav                 | ~15s  | моно   | -23dB |
| Elena_Solovyova.wav                | ~15s  | моно   | -23dB |
| Ivan_Litvinov.wav                  | ~15s  | моно   | -23dB |
| Irina_Kireeva.wav                  | ~15s  | моно   | -23dB |
| Lina_Ivanova.wav                   | ~15s  | моно   | -23dB |
| Mikhail_Pshenichny.wav             | ~15s  | моно   | -23dB |
| Mikhail_Khrustalyov.wav            | ~15s  | моно   | -23dB |
| Natalya_Kaznacheeva.wav            | ~15s  | моно   | -23dB |
| Nikita_Prozorovsky.wav             | ~15s  | моно   | -23dB |
| Oleg_Kutsenko.wav                  | ~15s  | моно   | -23dB |
| Olga_Golovanova.wav                | ~15s  | моно   | -23dB |
| Sergey_Chikhachyov.wav             | ~15s  | моно   | -23dB |
| Sergey_Chikhachyov_2.wav           | ~15s  | моно   | -23dB |
| Sergey_Chonishvili.wav             | ~15s  | моно   | -23dB |
| demo/sergey_chikhachyov_demo.wav   | demo  | моно   | -23dB |
| demo/sergey_chikhachyov_2_demo.wav | demo  | моно   | -23dB |
