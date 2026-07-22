"""
Download a YouTube clip and save as reference WAV in refs/samples/

Usage:
    # Just download full audio + show RMS analysis
    python dl_ref.py <youtube_url> "<Actor Name>"

    # Download and cut
    python dl_ref.py <youtube_url> "<Actor Name>" --from <sec> --dur <sec>

    # Cut from existing temp file (skip download)
    python dl_ref.py <youtube_url> "<Actor Name>" --from <sec> --dur <sec> --reuse

Examples:
    python dl_ref.py "https://youtu.be/..." "Иван Иванов"
    python dl_ref.py "https://youtu.be/..." "Иван Иванов" --from 19.78 --dur 15.6
"""

import os
import sys
import argparse
import subprocess
import tempfile
import json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
SAMPLES_DIR = os.path.join(ROOT, "refs", "samples")
os.makedirs(SAMPLES_DIR, exist_ok=True)


def run(cmd, **kwargs):
    print(f"  $ {cmd}")
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kwargs)


def download(url, output_path):
    """Download full audio as WAV via yt-dlp."""
    result = run(
        f'python3 -m yt_dlp -x --audio-format wav --audio-quality 0 '
        f'--output "{output_path}" "{url}"',
        timeout=120,
    )
    if result.returncode != 0:
        print(f"ERROR: download failed: {result.stderr}")
        sys.exit(1)


def analyze_rms(wav_path):
    """Print RMS energy in 10ms windows across the file."""
    print("\nRMS analysis (50ms windows, showing only non-silent):")
    script = f"""
import wave, numpy as np
with wave.open(r"{wav_path}", "rb") as wf:
    sr = wf.getframerate()
    nch = wf.getnchannels()
    frames = wf.readframes(wf.getnframes())
    data = np.frombuffer(frames, dtype=np.int16)
    if nch > 1:
        data = data.reshape(-1, nch).mean(axis=1)
    abs_data = np.abs(data)
    omax = np.max(abs_data)
    ws = int(sr * 0.05)
    for s in np.arange(0, len(data)/sr, 0.05):
        sf = int(s * sr)
        ef = min(len(data), sf + ws)
        rms = np.sqrt(np.mean(abs_data[sf:ef]**2))
        rn = rms / omax
        if rn > 0.003:
            bar = int(rn * 200)
            print(f"  {{s:.2f}}s | {{'#' * bar}} ({{rn:.4f}})")
"""
    result = run(f'python3 -c "{script}"', timeout=30)
    print(result.stdout)


def cut(wav_path, output_path, start_sec, dur_sec):
    """Cut segment from WAV."""
    result = run(
        f'ffmpeg -y -ss {start_sec} -t {dur_sec} -i "{wav_path}" "{output_path}" 2>&1',
        timeout=60,
    )
    if result.returncode != 0:
        print(f"ERROR: cut failed: {result.stderr}")
        sys.exit(1)
    size = os.path.getsize(output_path)
    print(f"\nSaved: {output_path} ({size/1024:.0f}KB, {dur_sec}s)")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Download and cut voice reference clips")
    parser.add_argument("url", help="YouTube URL")
    parser.add_argument("name", help="Actor name (used as filename)")
    parser.add_argument("--from", dest="start", type=float, help="Start time in seconds")
    parser.add_argument("--dur", type=float, default=15.0, help="Duration in seconds (default: 15)")
    parser.add_argument("--reuse", action="store_true", help="Reuse existing temp file")
    args = parser.parse_args()

    temp_dir = os.path.join(SAMPLES_DIR, ".temp")
    os.makedirs(temp_dir, exist_ok=True)
    temp_wav = os.path.join(temp_dir, "full.wav")
    output_wav = os.path.join(SAMPLES_DIR, f"{args.name}.wav")

    if args.start is not None:
        # Cut mode
        if not args.reuse:
            print(f"Step 1: Downloading {args.url}...")
            download(args.url, os.path.join(temp_dir, "full"))
        else:
            if not os.path.exists(temp_wav):
                print("ERROR: --reuse but no temp file found. Run without --reuse first.")
                sys.exit(1)
            print("Reusing existing temp file.")

        print(f"Step 2: Cutting {args.start}s + {args.dur}s...")
        cut(temp_wav, output_wav, args.start, args.dur)

        if not args.reuse:
            # cleanup temp
            if os.path.exists(temp_wav):
                os.remove(temp_wav)
    else:
        # Analyze mode
        print("Downloading for analysis...")
        download(args.url, os.path.join(temp_dir, "full"))
        print(f"\nTemp file: {temp_wav}")
        analyze_rms(temp_wav)
        print(f"\nTip: pick a clean segment and re-run with --from <sec> --dur <sec>")
        print(f"  python dl_ref.py \"{args.url}\" \"{args.name}\" --from 20.0 --dur 15")


if __name__ == "__main__":
    main()
