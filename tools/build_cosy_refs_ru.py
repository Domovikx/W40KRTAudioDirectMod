#!/usr/bin/env python
"""Build refs/samples_ru_cosy/*.wav (+.txt) from refs/samples_ru/*.wav.

Correct workflow:
1. Cut ~10s from the BEGINNING of the source
2. Transcribe the CUT segment
3. Save both WAV and matching TXT
"""
import os
import subprocess

SRC_DIR = os.path.join(r'C:\Program Files (x86)\Steam\steamapps\common\The Survival of Sarah Rose', 'refs', 'samples_ru')
DST_DIR = os.path.join(r'C:\Program Files (x86)\Steam\steamapps\common\The Survival of Sarah Rose', 'refs', 'samples_ru_cosy')

TARGET_LEN = 10.0


def main():
    import whisper
    model = whisper.load_model('large-v3-turbo')
    os.makedirs(DST_DIR, exist_ok=True)

    for f in sorted(os.listdir(SRC_DIR)):
        if not f.endswith('.wav'):
            continue
        name = f[:-4]
        src = os.path.join(SRC_DIR, f)
        dst_wav = os.path.join(DST_DIR, f)
        dst_txt = os.path.join(DST_DIR, name + '.txt')

        if os.path.exists(dst_wav):
            print(f'{name:22s} SKIP (exists)')
            continue

        # Get duration
        dur = float(subprocess.check_output(
            ['ffprobe', '-v', 'error', '-show_entries', 'stream=duration',
             '-of', 'csv=p=0', src]).decode().strip().splitlines()[0])

        # Cut from start (or from 0.5s if there's initial silence)
        cut_end = min(TARGET_LEN, dur)

        # Step 1: Cut the WAV
        subprocess.run(['ffmpeg', '-y', '-ss', '0', '-to', f'{cut_end:.3f}',
                        '-i', src, '-ac', '1', '-ar', '24000', dst_wav],
                       check=True, capture_output=True)

        # Step 2: Transcribe the CUT segment (not the original!)
        r = model.transcribe(dst_wav, language='ru', fp16=False, word_timestamps=True)
        txt = r.get('text', '').strip()

        # Step 3: Save TXT
        with open(dst_txt, 'w', encoding='utf-8') as fh:
            fh.write(txt + '\n')

        print(f'{name:22s} cut 0-{cut_end:.1f}s | {txt[:80]}')

    print('\nDone.')


if __name__ == '__main__':
    main()
