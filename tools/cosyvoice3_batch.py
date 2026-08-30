#!/usr/bin/env python
"""Batch CV3 → Localization/{lang}/{char}/{guid}.wav (trimmed inline).

Победный конфиг (2026-08-29, выбор пользователя по демкам accent):
    cross_lingual + RL + flow-temp 1.2 + cfg 0.9 + RAS 0.5,10,0.15
    + smart-tail-trim (trim_tails) + s16 + seed 42.

Модель грузится ОДИН раз на процесс (~15-25с), затем по ~1-2 мин на фразу.
Каждая часть: generate → trim inline → save trimmed part → glue → Localization.

Запуск ОБЯЗАТЕЛЬНО через venv CosyVoice:
    C:\\tools\\cosyvoice3\\.venv\\Scripts\\python.exe tools/cosyvoice3_batch.py \\
        --char Kunrad_Voigtvir [--lang ruRU_cosy] [--guid ...] [--limit N] [--force]

Resumable: существующие WAV пропускаются (без --force).
"""

import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COSY_ROOT = r'C:\tools\cosyvoice3'
REPO_DIR = os.path.join(COSY_ROOT, 'CosyVoice')
sys.path.insert(0, REPO_DIR)
sys.path.insert(0, os.path.join(REPO_DIR, 'third_party', 'Matcha-TTS'))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import torch
import torchaudio
import yaml
from cosyvoice.cli.cosyvoice import AutoModel
from cosyvoice.utils.common import set_all_random_seed

from cosyvoice3_demo import (CV3_PREFIX, MODEL_DIR, load_phrase, ref_for_speaker,
                             prep_ref, patch_flow_temperature,
                             patch_silent_token_trim, make_tuned_model_dir)
from trim_tails import trim_part

FLOW_TEMP = 1.2
CFG_RATE = 0.9
SAMPLING = (0.5, 10.0, 0.15)
GAP = 0.25


def gen_one(cosyvoice, text, ref, seed):
    prepped = prep_ref(ref)
    set_all_random_seed(seed)
    gen = cosyvoice.inference_cross_lingual(CV3_PREFIX + text, prepped,
                                            stream=False, speed=1.0,
                                            text_frontend=False)
    for j in gen:
        return j['tts_speech']


def main():
    ap = argparse.ArgumentParser(description='CosyVoice 3 batch → Localization')
    ap.add_argument('--char', required=True, help='имя файла каталога (Kunrad_Voigtvir)')
    ap.add_argument('--lang', default='ruRU_cosy')
    ap.add_argument('--guid', nargs='*', default=None, help='только эти GUID')
    ap.add_argument('--limit', type=int, default=None, help='максимум фраз за прогон')
    ap.add_argument('--force', action='store_true', help='перегенерировать существующие')
    ap.add_argument('--seed', type=int, default=42)
    args = ap.parse_args()

    out_dir = os.path.join(ROOT, 'Localization', args.lang, args.char)
    os.makedirs(out_dir, exist_ok=True)
    raw_dir = os.path.join(ROOT, 'output', 'cosyvoice3', 'raw', args.char)
    os.makedirs(raw_dir, exist_ok=True)

    model_dir = make_tuned_model_dir(*SAMPLING, rl=True, cfg_rate=CFG_RATE)
    print('model :', model_dir)
    t0 = time.time()
    cosyvoice = AutoModel(model_dir=model_dir)
    patch_flow_temperature(FLOW_TEMP)
    patch_silent_token_trim()
    print('model loaded in {:.1f}s (flow-temp {}, cfg {}, RAS {}, silent-trim ON)'.format(
        time.time() - t0, FLOW_TEMP, CFG_RATE, SAMPLING))

    catalog = os.path.join(ROOT, 'catalog', 'people', '{}.yaml'.format(args.char))
    with open(catalog, encoding='utf-8') as f:
        data = yaml.safe_load(f)
    phrases = [p for p in data.get('phrases', []) if p.get('parts')]
    if args.guid:
        phrases = [p for p in phrases if p['guid'] in args.guid]

    done = skipped = failed = 0
    total = len(phrases)
    t_start = time.time()
    for idx, phrase in enumerate(phrases):
        guid = phrase['guid']
        out = os.path.join(out_dir, '{}.wav'.format(guid))
        if os.path.exists(out) and not args.force:
            skipped += 1
            continue
        if args.limit and done >= args.limit:
            break
        parts = [(pp.get('speaker_override') or pp.get('speaker'), pp['text_clean'])
                 for pp in phrase.get('parts', []) if pp.get('text_clean')]
        if not parts:
            continue
        print('[{}/{}] {}'.format(idx + 1, total, guid))
        try:
            pieces = []
            for i, (speaker, text) in enumerate(parts):
                ref = ref_for_speaker(speaker)
                print('  part {} {}: {}'.format(i + 1, speaker, text[:70]))
                speech = gen_one(cosyvoice, text, ref, args.seed)
                sr = cosyvoice.sample_rate
                # torch → numpy → trim → save trimmed part
                x_np = speech.squeeze(0).cpu().numpy().astype(np.float64)
                x_trimmed = trim_part(x_np, sr, verbose=True)
                trimmed_t = torch.from_numpy(x_trimmed).unsqueeze(0)
                raw_part = os.path.join(raw_dir, '{}__{}.wav'.format(guid, i + 1))
                if not os.path.exists(raw_part) or args.force:
                    torchaudio.save(raw_part, trimmed_t, sr,
                                    encoding='PCM_S', bits_per_sample=16)
                pieces.append(x_trimmed)
            gap = np.zeros(int(sr * GAP), dtype=np.float64)
            glued = pieces[0]
            for p in pieces[1:]:
                glued = np.concatenate([glued, gap, p])
            glued_t = torch.from_numpy(glued).unsqueeze(0)
            torchaudio.save(out, glued_t, sr,
                            encoding='PCM_S', bits_per_sample=16)
            raw_out = os.path.join(raw_dir, '{}.wav'.format(guid))
            if not os.path.exists(raw_out) or args.force:
                torchaudio.save(raw_out, glued_t, sr,
                                encoding='PCM_S', bits_per_sample=16)
            dur = len(glued) / sr
            eta = (time.time() - t_start) / max(done + 1, 1) * (total - idx - 1)
            print('  saved {} ({:.1f}s), eta ~{:.0f} мин'.format(out, dur, eta / 60))
            done += 1
        except Exception as e:
            failed += 1
            print('  !! FAIL {}: {}'.format(guid, e))

    print('done={} skipped={} failed={} total={}'.format(done, skipped, failed, total))


if __name__ == '__main__':
    main()
