"""
Qwen3 1.7B batch generation — all voices + instruct variations.
Usage:
  python tools/qwen3_batch.py
"""

import os, time, sys, re, itertools
from pathlib import Path

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples" / "qwen3_17b"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

TEXT = "Прекрасное место для размышлений. Взгляд приблизившегося к вам мужчины устремлен вниз — в глубины корабельного храма. Завораживает, не правда ли?"

VOICES = [
    "Dylan", "Ryan",                # male (2)
    "Vivian", "Serena",             # female (2)
]

INSTRUCTS = {
    "neutral": "",
    "warm": "Тёплый, дружелюбный тон",
    "firm": "Уверенный, командный голос",
    "deep": "Глубокий, низкий тембр, медленный темп",
}

def clean_game_text(text: str) -> str:
    text = re.sub(r'\{/?\w+(?:\|[^}]*)?\}', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def main():
    import torch
    from qwen_tts import Qwen3TTSModel

    model_id = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"

    print(f"Loading {model_id}...")
    t0 = time.time()
    model = Qwen3TTSModel.from_pretrained(
        model_id,
        device_map="cpu",
        dtype=torch.float32,
    )
    print(f"  Loaded in {time.time()-t0:.1f}s")

    text = TEXT

    os.makedirs(SAMPLES_DIR, exist_ok=True)

    total = len(VOICES) * len(INSTRUCTS)
    count = 0

    for voice in VOICES:
        for iname, instruct in INSTRUCTS.items():
            count += 1
            fname = f"{voice.lower()}_{iname}.wav"
            out = SAMPLES_DIR / fname

            if out.exists():
                duration = out.stat().st_size / 44100
                print(f"[{count}/{total}] SKIP {fname} (exists)")
                continue

            print(f"[{count}/{total}] {fname} (instruct={iname!r})...")

            try:
                wavs, sr = model.generate_custom_voice(
                    text=text,
                    language="Russian",
                    speaker=voice,
                    instruct=instruct,
                    temperature=0.9,
                    top_k=50,
                    top_p=1.0,
                    repetition_penalty=1.05,
                    max_new_tokens=8192,
                    do_sample=True,
                )
                import soundfile as sf
                sf.write(str(out), wavs[0], sr)
                dur = wavs[0].shape[0] / sr
                print(f"  -> {dur:.1f}s")
            except Exception as e:
                print(f"  ERROR: {e}")

    print(f"\nDone! {count} samples in {SAMPLES_DIR}")

if __name__ == "__main__":
    main()
