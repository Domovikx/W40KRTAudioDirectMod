#!/usr/bin/env python3
"""Concatenate top WAVs from each NARR bank into ~60s reference samples."""
import os, glob, subprocess
import soundfile as sf
import numpy as np

ROOT = r"C:\Users\Domo\AppData\LocalLow\Owlcat Games\Warhammer 40000 Rogue Trader\UnityModManager\W40KRTAudioDirectMod"
INPUT = os.path.join(ROOT, "output", "noncompanion")
OUTPUT = os.path.join(ROOT, "output", "samples_identify")
os.makedirs(OUTPUT, exist_ok=True)

MAX_DURATION = 60  # seconds

for pck_dir in sorted(os.listdir(INPUT)):
    pck_path = os.path.join(INPUT, pck_dir)
    if not os.path.isdir(pck_path) or pck_dir.startswith('_'):
        continue
    
    # Collect all WAVs from this PCK
    all_wavs = []
    for bank_dir in sorted(os.listdir(pck_path)):
        wav_dir = os.path.join(pck_path, bank_dir, "wav")
        if not os.path.isdir(wav_dir):
            continue
        for f in glob.glob(os.path.join(wav_dir, "*.wav")):
            sz = os.path.getsize(f)
            all_wavs.append((sz, f))
    
    if not all_wavs:
        continue
    
    # Sort by size descending, take top
    all_wavs.sort(reverse=True)
    
    # Concatenate top files to fill MAX_DURATION
    total_dur = 0
    parts = []
    for sz, path in all_wavs:
        duration = sz / (48000 * 2)
        if total_dur + duration > MAX_DURATION + 5:
            continue
        try:
            w, sr = sf.read(path)
            if w.ndim > 1:
                w = w.mean(axis=1)
            parts.append(w)
            total_dur += duration
        except:
            continue
        if total_dur >= MAX_DURATION:
            break
    
    if parts:
        combined = np.concatenate(parts)
        # Short gap between parts
        gap = np.zeros(int(0.3 * 48000))
        with_gaps = []
        for p in parts:
            with_gaps.append(p)
            with_gaps.append(gap)
        combined = np.concatenate(with_gaps)
        
        out_name = f"{pck_dir}_sample.wav"
        out_path = os.path.join(OUTPUT, out_name)
        sf.write(out_path, combined.astype(np.float32), 48000)
        
        size_mb = os.path.getsize(out_path) / 1024 / 1024
        total_real = sum(len(p) for p in parts) / 48000
        print(f"{out_name:45s} {total_real:5.1f}s ({len(parts)} files) -> {size_mb:.0f} MB")

print(f"\nDone! {OUTPUT}/")
