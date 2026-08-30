#!/usr/bin/env python
"""Build refs/samples_en_cosy/*.wav (+.txt) from refs/samples_en/*.wav.

Правила (docs/cosyvoice3.md):
- 24kHz mono, целевой отрезок ~10с чистой речи
- не рвать слово/фразу: окно выравнивается по word-timestamps whisper
- защита от «двойных тейков» (как у Jae): если whisper видит в окне
  две почти одинаковые фразы — берём один полный тейк
- .txt = точный транскрипт выбранного окна (нужен zero_shot CV3)

Запуск: python tools/build_cosy_refs.py [--dry-run] [--force] [--whisper MODEL]
Idempotent: существующие .wav пропускаются без --force.
"""

import argparse
import os
import subprocess
import sys

SRC_DIR = os.path.join('refs', 'samples_en')
DST_DIR = os.path.join('refs', 'samples_en_cosy')

DEFAULT_START = 2.5
TARGET_LEN = 10.0
MIN_LEN = 4.0
MAX_GAP = 1.5  # пауза длиннее — обрезаем хвост


def transcribe(whisper_model, path):
    m = whisper_model
    r = m.transcribe(path, language='en', fp16=False, word_timestamps=True)
    words = []
    for seg in r.get('segments', []):
        for w in seg.get('words') or []:
            if w.get('start') is not None and w.get('end') is not None:
                words.append((float(w['start']), float(w['end']), w.get('word', '').strip()))
        if not (seg.get('words') or []) and seg.get('text', '').strip():
            words.append((float(seg['start']), float(seg['end']), seg['text'].strip()))
    return words


def norm(s):
    return ''.join(c for c in s.lower() if c.isalnum())


def find_window(words, duration):
    """Return (start, end, txt). Окно ~TARGET_LEN внутри одного тейка:
    берём группу слов, содержащую 2.5с (или самую длинную), старт — первое
    слово после 2.5с, конец выравниваем по концу слова."""
    if not words:
        return None

    # сегменты = слова, сгруппированные по паузам > MAX_GAP
    groups = []
    cur = [words[0]]
    for w in words[1:]:
        if w[0] - cur[-1][1] > MAX_GAP:
            groups.append(cur)
            cur = [w]
        else:
            cur.append(w)
    groups.append(cur)

    # целевая группа: содержит 2.5с; иначе самая длинная
    g = next((gr for gr in groups if gr[0][0] <= DEFAULT_START <= gr[-1][1]),
             max(groups, key=len))
    ws = [w for w in g if w[0] >= DEFAULT_START] or g
    start = ws[0][0]
    end = min(start + TARGET_LEN, g[-1][1], duration)
    last = ws[0]
    for w in ws:
        if w[1] <= end:
            last = w
        else:
            break
    end = last[1]
    if end - start < MIN_LEN:
        end = min(duration, g[-1][1])
    txt = ' '.join(w[2] for w in g if w[1] <= end + 0.05)
    return start, end, txt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--whisper', default='large-v3-turbo')
    args = ap.parse_args()

    import whisper
    model = whisper.load_model(args.whisper)
    os.makedirs(DST_DIR, exist_ok=True)

    done = skip = 0
    for f in sorted(os.listdir(SRC_DIR)):
        if not f.endswith('.wav'):
            continue
        name = f[:-4]
        src = os.path.join(SRC_DIR, f)
        dst = os.path.join(DST_DIR, f)
        txt_path = os.path.join(DST_DIR, name + '.txt')
        if os.path.exists(dst) and not args.force:
            skip += 1
            continue

        words = transcribe(model, src)
        dur = float(subprocess.check_output(
            ['ffprobe', '-v', 'error', '-show_entries', 'stream=duration',
             '-of', 'csv=p=0', src]).decode().strip().splitlines()[0])
        win = find_window(words, dur)
        if not win:
            print('!! no words for', name)
            continue
        start, end, txt = win
        print(f'{name:22s} window {start:6.2f}-{end:6.2f}s ({end-start:4.1f}s) | {txt[:60]}...')
        if args.dry_run:
            continue
        subprocess.run(['ffmpeg', '-y', '-ss', f'{start:.3f}', '-to', f'{end:.3f}',
                        '-i', src, '-ac', '1', '-ar', '24000', dst],
                       check=True, capture_output=True)
        with open(txt_path, 'w', encoding='utf-8') as fh:
            fh.write(txt + '\n')
        done += 1

    print(f'built={done} skipped(existing)={skip} dry_run={args.dry_run}')


if __name__ == '__main__':
    main()
