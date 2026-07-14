#!/usr/bin/env python3
"""
Gemini TTS — CLI для однократной генерации WAV.
Один вызов = один запрос. После генерации пауза 25с.

Usage:
    python gemini_tts.py --text "Привет" --output speech.wav --voice Kore
    python gemini_tts.py --text "Привет" --output speech.wav --voice Kore --proxy http://47.253.201.85:7890
"""

from __future__ import annotations
import argparse, os, sys, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from tools.gemini_tts import generate, VOICES


def main():
    p = argparse.ArgumentParser(description="Gemini TTS — генерация WAV")
    p.add_argument("--text", required=True, help="Текст для озвучивания")
    p.add_argument("--output", required=True, help="Путь к WAV файлу")
    p.add_argument("--voice", default="Kore", help=f"Голос Gemini. По умолчанию Kore")
    p.add_argument("--proxy", default="", help="HTTP прокси (http://ip:port)")
    p.add_argument("--no-wait", action="store_true", help="Не ждать после генерации")
    args = p.parse_args()

    if args.voice not in VOICES:
        print(f"Warning: unknown voice '{args.voice}'. Available: {', '.join(VOICES)}")
        sys.exit(1)

    print(f"Gemini TTS: {args.voice} → {args.output}")
    if args.proxy:
        print(f"  Proxy: {args.proxy}")

    try:
        dur = generate(args.text, args.output, args.voice, args.proxy)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Done: {args.output} ({dur:.2f}s)")

    if not args.no_wait:
        wait = 25
        print(f"Wait {wait}s (rate limit)...")
        time.sleep(wait)


if __name__ == "__main__":
    main()
