#!/usr/bin/env python
"""Smart tail trim per part + reglue (детектор хвостовых артефактов CV3).

Проблема: аудио-трим по абсолютному порогу резал последние слова
(пример: ca2ef6c0). Новый детектор работает по структуре хвоста:

    речь → тишина (>= SIL_MIN_S) → короткий всплеск (<= BURST_MAX_S) → конец

тогда всплеск = артефакт (вздох/всхлип модели), режем его целиком.
Если всплеск длинный или перед ним нет тишины — это речь, не трогаем.

Читает сырые части output/cosyvoice3/raw/{char}/{guid}__{N}.wav,
склеивает с gap 0.25с и пишет в Localization/{lang}/{char}/{guid}.wav
(или в --out-dir).

Usage:
    python tools/trim_tails.py --char Kunrad_Voigtvir [--guid g1 g2 ...]
        [--dry-run] [--out-dir dir]
"""

import argparse
import glob
import os

import numpy as np
from scipy.io import wavfile

SIL_DB = -45.0       # порог тишины, dBFS
BURST_MAX_S = 0.30   # всплеск короче — артефакт
SIL_MIN_S = 0.15     # тишина перед всплеском — длиннее
FADE_MS = 40
GAP_S = 0.25
HOP_MS = 10
WIN_MS = 20

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def frame_rms(x, sr):
    hop = int(sr * HOP_MS / 1000)
    win = int(sr * WIN_MS / 1000)
    n = max(0, (len(x) - win) // hop + 1)
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    return np.sqrt(np.mean(x[idx] ** 2, axis=1) + 1e-12)


def trim_part(x, sr, verbose=False):
    """Return trimmed float64 array. x: float64 [-1,1]."""
    hop = int(sr * HOP_MS / 1000)
    rms = frame_rms(x, sr)
    loud = rms > 10 ** (SIL_DB / 20)
    if not loud.any():
        return np.zeros(0, dtype=np.float64)
    last = int(np.where(loud)[0][-1])
    reg_start = last
    while reg_start >= 0 and loud[reg_start]:
        reg_start -= 1
    reg_start += 1
    reg_dur = (last - reg_start + 1) * HOP_MS / 1000.0
    sil_start = reg_start - 1
    while sil_start >= 0 and not loud[sil_start]:
        sil_start -= 1
    sil_dur = (reg_start - 1 - sil_start) * HOP_MS / 1000.0
    cut = (reg_dur <= BURST_MAX_S and sil_dur >= SIL_MIN_S and sil_start >= 0)
    if cut:
        # режем вместе с тишиной: конец = последний речевой кадр перед тишиной
        end_sample = (sil_start + 1) * hop
    else:
        end_sample = (last + 1) * hop
    y = x[:end_sample].copy()
    f = int(sr * FADE_MS / 1000)
    if f > 0 and len(y) > 2 * f:
        y[-f:] *= np.linspace(1.0, 0.0, f)
    y2, start_cut = trim_start(y, sr)
    if verbose:
        print(f'    end: reg={reg_dur*1000:.0f}ms sil={sil_dur*1000:.0f}ms '
              f'cut={cut} | start_cut={start_cut}')
    return y2


def trim_start(x, sr):
    """Срезать ведущий микрозвук (вздох/транзиент) в начале части.

    Правило пользователя: была пауза (стык частей/старт), потом вдруг
    микрозвук небольшой длительности, и только потом настоящая речь.
    Режем всё до первого кадра громче -30dB, если этот пред-речевой
    участок длится >= 100мс и за ним есть явная речь (> -25dB).
    """
    hop = int(sr * HOP_MS / 1000)
    rms = frame_rms(x, sr)
    n = len(rms)
    if n < 5:
        return x, False
    onset = next((i for i in range(n) if rms[i] > 10 ** (-25 / 20)), None)
    if onset is None or onset < 5:
        return x, False  # часть целиком тихая — не трогаем
    onset30 = next((i for i in range(n) if rms[i] > 10 ** (-30 / 20)), None)
    if onset30 is None or onset30 >= onset:
        return x, False
    if onset30 * HOP_MS / 1000.0 < 0.1:
        return x, False  # короткий транзиент (<100мс) — нормальная атака слова
    return x[onset30 * hop:], True


def to_int16(y):
    return np.clip(y * 32767, -32768, 32767).astype(np.int16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--char', required=True)
    ap.add_argument('--guid', nargs='*', default=None)
    ap.add_argument('--lang', default='ruRU_cosy')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--out-dir', default=None)
    args = ap.parse_args()

    raw_dir = os.path.join(ROOT, 'output', 'cosyvoice3', 'raw', args.char)
    out_dir = args.out_dir or os.path.join(ROOT, 'Localization', args.lang, args.char)
    os.makedirs(out_dir, exist_ok=True)

    guids = sorted({os.path.basename(f)[:36] for f in glob.glob(os.path.join(raw_dir, '*.wav'))})
    if args.guid:
        guids = [g for g in guids if g in args.guid]

    total_cut = 0
    for guid in guids:
        parts = sorted(glob.glob(os.path.join(raw_dir, '{}__*.wav'.format(guid))))
        if not parts:
            print('!! no parts for', guid)
            continue
        print('{}: {} parts'.format(guid, len(parts)))
        trimmed = []
        for p in parts:
            sr, x = wavfile.read(p)
            if x.dtype == np.int16:
                x = x.astype(np.float64) / 32768
            else:
                x = x.astype(np.float64)
            x = x.ravel()
            y = trim_part(x, sr, verbose=True)
            if len(y) != len(x):
                total_cut += 1
            trimmed.append(y)
        gap = np.zeros(int(sr * GAP_S), dtype=np.float64)
        glued = trimmed[0]
        for t in trimmed[1:]:
            glued = np.concatenate([glued, gap, t])
        out = os.path.join(out_dir, '{}.wav'.format(guid))
        if not args.dry_run:
            wavfile.write(out, sr, to_int16(glued))
        print('  -> {} ({:.2f}s){}'.format(out, len(glued) / sr,
                                           ' [dry-run]' if args.dry_run else ''))
    print('done: {} phrases, {} parts cut'.format(len(guids), total_cut))


if __name__ == '__main__':
    main()
