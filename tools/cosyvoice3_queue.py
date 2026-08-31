#!/usr/bin/env python
"""CosyVoice 3 queue — one process, model loaded once, runs until done.

Usage (MUST use CosyVoice venv):
    C:\tools\cosyvoice3\.venv\Scripts\python.exe tools/cosyvoice3_queue.py

Optional filters:
    --char Cassia_Orsellio     # only this character
    --guid abc123 def456       # only these GUIDs
    --limit N                  # max phrases total
    --force                    # regenerate existing

Resumable: existing WAVs in Localization/ruRU_cosy/{char}/{guid}.wav are skipped.
Log: output/cosyvoice3/queue.log
"""

import argparse
import glob
import os
import sys
import time
from datetime import datetime

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

from cosyvoice3_demo import (CV3_PREFIX, prep_ref, ref_for_speaker,
                             patch_flow_temperature, patch_silent_token_trim,
                             make_tuned_model_dir)
from trim_tails import trim_part

FLOW_TEMP = 1.2
CFG_RATE = 0.9
SAMPLING = (0.5, 10.0, 0.15)
GAP = 0.25
LOG = os.path.join(ROOT, 'output', 'cosyvoice3', 'queue.log')

# Queue: all characters with phrases, sorted by size (smallest first for quick wins)
QUEUE = [
    ('Trazyn', 66),
    ('Psyker_NPC', 97),
    ('Seneschal_NPC', 105),
    ('Smuggler', 179),
    ('Manipulus', 204),
    ('Eogann', 207),
    ('Jae_Heydari', 248),
    ('Yrliet_Lanaeviss', 329),
    ('Ulfar', 358),
    ('Sister_Argenta', 382),
    ('Abelard_Werserian', 404),
    ('Pasqal_Haneumann', 408),
    ('Heinrix_van_Calox', 410),
    ('Idira_Tlass', 412),
    ('Marazhai_Aezyrraesh', 553),
    ('Kibellah', 579),
    ('Solomon_Antar', 607),
    ('Cassia_Orsellio', 656),
    ('Narrator', 4478),
    ('Generic_Male_NPC', 24862),
]


def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line, flush=True)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def count_wav(char_name):
    d = os.path.join(ROOT, 'Localization', 'ruRU_cosy', char_name)
    if not os.path.isdir(d):
        return 0
    return len([f for f in os.listdir(d) if f.endswith('.wav')])


def gen_one(cosyvoice, text, ref, seed):
    prepped = prep_ref(ref)
    set_all_random_seed(seed)
    gen = cosyvoice.inference_cross_lingual(CV3_PREFIX + text, prepped,
                                            stream=False, speed=1.0,
                                            text_frontend=False)
    for j in gen:
        return j['tts_speech']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--char', default=None, help='only this character')
    ap.add_argument('--guid', nargs='*', default=None)
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--seed', type=int, default=42)
    args = ap.parse_args()

    # Load model ONCE
    log('Loading model...')
    t0 = time.time()
    model_dir = make_tuned_model_dir(*SAMPLING, rl=True, cfg_rate=CFG_RATE)
    cosyvoice = AutoModel(model_dir=model_dir)
    patch_flow_temperature(FLOW_TEMP)
    patch_silent_token_trim()
    log(f'Model loaded in {time.time()-t0:.0f}s (flow-temp {FLOW_TEMP}, cfg {CFG_RATE})')
    sr = cosyvoice.sample_rate

    # Load all catalogs
    catalog_dir = os.path.join(ROOT, 'catalog', 'people')
    chars_to_process = []
    for char_name, total_phrases in QUEUE:
        if args.char and char_name != args.char:
            continue
        yaml_path = os.path.join(catalog_dir, f'{char_name}.yaml')
        if not os.path.exists(yaml_path):
            continue
        with open(yaml_path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        phrases = [p for p in data.get('phrases', []) if p.get('parts')]
        if args.guid:
            phrases = [p for p in phrases if p['guid'] in args.guid]
        done = count_wav(char_name)
        remaining = len(phrases) - done if not args.force else len(phrases)
        if remaining > 0:
            chars_to_process.append((char_name, data, phrases, done))

    total_phrases = sum(len(ph) for _, _, ph, _ in chars_to_process)
    log(f'Queue: {len(chars_to_process)} chars, {total_phrases} phrases to process')

    # Process
    done_count = 0
    failed_count = 0
    t_start = time.time()

    for char_name, char_data, phrases, already_done in chars_to_process:
        out_dir = os.path.join(ROOT, 'Localization', 'ruRU_cosy', char_name)
        os.makedirs(out_dir, exist_ok=True)
        raw_dir = os.path.join(ROOT, 'output', 'cosyvoice3', 'raw', char_name)
        os.makedirs(raw_dir, exist_ok=True)

        log(f'--- {char_name}: {already_done}/{len(phrases)} done ---')

        for phrase in phrases:
            guid = phrase['guid']
            out_path = os.path.join(out_dir, f'{guid}.wav')

            if os.path.exists(out_path) and not args.force:
                continue

            if args.limit and done_count >= args.limit:
                log(f'Limit reached ({args.limit})')
                break

            parts = [(pp.get('speaker_override') or pp.get('speaker'), pp['text_clean'])
                     for pp in phrase.get('parts', []) if pp.get('text_clean')]
            if not parts:
                continue

            try:
                pieces = []
                for i, (speaker, text) in enumerate(parts):
                    ref = ref_for_speaker(speaker)
                    speech = gen_one(cosyvoice, text, ref, args.seed)
                    x_np = speech.squeeze(0).cpu().numpy().astype(np.float64)
                    x_trimmed = trim_part(x_np, sr)
                    trimmed_t = torch.from_numpy(x_trimmed).unsqueeze(0)
                    raw_part = os.path.join(raw_dir, f'{guid}__{i+1}.wav')
                    if not os.path.exists(raw_part) or args.force:
                        torchaudio.save(raw_part, trimmed_t, sr,
                                        encoding='PCM_S', bits_per_sample=16)
                    pieces.append(x_trimmed)

                gap = np.zeros(int(sr * GAP), dtype=np.float64)
                glued = pieces[0]
                for p in pieces[1:]:
                    glued = np.concatenate([glued, gap, p])
                glued_t = torch.from_numpy(glued).unsqueeze(0)
                torchaudio.save(out_path, glued_t, sr,
                                encoding='PCM_S', bits_per_sample=16)
                raw_out = os.path.join(raw_dir, f'{guid}.wav')
                if not os.path.exists(raw_out) or args.force:
                    torchaudio.save(raw_out, glued_t, sr,
                                    encoding='PCM_S', bits_per_sample=16)

                dur = len(glued) / sr
                done_count += 1
                elapsed = time.time() - t_start
                rate = done_count / elapsed * 3600
                remaining_phrases = total_phrases - done_count
                eta_h = remaining_phrases / rate if rate > 0 else 0
                log(f'  [{done_count}/{total_phrases}] {guid} ({dur:.1f}s) '
                    f'rate={rate:.0f}/h eta={eta_h:.1f}h')
            except Exception as e:
                failed_count += 1
                log(f'  !! FAIL {guid}: {e}')

        if args.limit and done_count >= args.limit:
            break

    elapsed = time.time() - t_start
    log(f'=== Done: {done_count} generated, {failed_count} failed, '
        f'{elapsed/3600:.1f}h elapsed ===')


if __name__ == '__main__':
    main()
