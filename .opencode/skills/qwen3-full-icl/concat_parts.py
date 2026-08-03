"""
Concatenate multi-part GUID WAVs into a single file.

Output from tools/qwen3_full_icl.py:
    output/full_icl/{voice}/{guid}__1.wav
    output/full_icl/{voice}/{guid}__2.wav
    output/full_icl/{voice}/{guid}__3.wav  (optional)

This script:
    output/full_icl/{voice}/{guid}.wav      (merged)

Usage:
    python concat_parts.py <directory_or_glob>
    python concat_parts.py output/full_icl/kunrad/
"""

import os
import sys
import glob
import struct
import wave
import re
from collections import defaultdict

PART_RE = re.compile(r"^(.+)__(\d+)\.wav$")

def find_parts(directory: str):
    """Group wav files by GUID, ordered by part index."""
    pattern = os.path.join(directory, "*__*.wav")
    groups = defaultdict(list)
    for path in glob.glob(pattern):
        basename = os.path.basename(path)
        m = PART_RE.match(basename)
        if m:
            guid = m.group(1)
            idx = int(m.group(2))
            groups[guid].append((idx, path))
    # sort each group by part index
    for guid in groups:
        groups[guid].sort(key=lambda x: x[0])
    return groups


def read_wav(path: str) -> tuple:
    """Read WAV file, return (frames: bytes, params: (nchannels, sampwidth, framerate))."""
    with wave.open(path, "rb") as wf:
        nchannels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    return frames, (nchannels, sampwidth, framerate)


def concat_wavs(input_paths: list, output_path: str, gap_ms: int = 0):
    """
    Concatenate multiple WAV files into one.
    All inputs must have same params (nchannels, sampwidth, framerate).
    Optional gap (silence) between parts in milliseconds.
    """
    if not input_paths:
        return

    all_frames = []
    params = None

    for i, path in enumerate(input_paths):
        frames, p = read_wav(path)
        if params is None:
            params = p
        else:
            assert params == p, f"WAV param mismatch: {path}"

        all_frames.append(frames)

        # add silence gap between parts
        if gap_ms > 0 and i < len(input_paths) - 1:
            gap_frames = int(params[2] * params[0] * params[1] * gap_ms / 1000)
            all_frames.append(b"\x00" * gap_frames)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(params[0])
        wf.setsampwidth(params[1])
        wf.setframerate(params[2])
        wf.writeframes(b"".join(all_frames))

    total_sec = sum(len(f) // (params[0] * params[1]) / params[2] for f in all_frames)
    print(f"  {output_path} ({total_sec:.1f}s)")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    gap_ms = int(sys.argv[2]) if len(sys.argv) > 2 else 300

    if os.path.isdir(target):
        groups = find_parts(target)
    else:
        groups = find_parts(os.path.dirname(target))

    if not groups:
        print("No part files found.")
        return

    for guid in sorted(groups):
        paths = [p for _, p in groups[guid]]
        out = os.path.join(os.path.dirname(paths[0]), f"{guid}.wav")
        concat_wavs(paths, out, gap_ms)

    print(f"\nDone. {len(groups)} GUIDs merged.")


if __name__ == "__main__":
    main()
