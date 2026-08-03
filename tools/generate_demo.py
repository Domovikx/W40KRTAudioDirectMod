#!/usr/bin/env python3
"""Generate demo TTS for all voices with a test phrase."""

import os, sys
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

PINOKIO = r"C:\pinokio\api\Qwen3-TTS-Pinokio.git\app"
sys.path.insert(0, PINOKIO)

import yaml
import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_VOICES = os.path.join(ROOT, "config", "voices.yaml")
CONFIG_DEFAULT = os.path.join(ROOT, "config", "default.yaml")
OUT_DIR = os.path.join(ROOT, "refs", "samples_en_demo")
os.makedirs(OUT_DIR, exist_ok=True)

DEMO_TEXT = "Приветствую, лорд-капитан. Это тестовое сообщение для проверки голоса."

def main():
    with open(CONFIG_DEFAULT, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    with open(CONFIG_VOICES, "r", encoding="utf-8") as f:
        voices_config = yaml.safe_load(f)

    model_id = cfg.get("qwen3_base_model", "Qwen/Qwen3-TTS-12Hz-1.7B-Base")
    device = cfg.get("qwen3_base_device", "cpu")
    dtype_name = cfg.get("qwen3_base_dtype", "float32")
    dtype = torch.float32 if dtype_name == "float32" else torch.bfloat16

    model_path = model_id
    if not os.path.exists(model_path):
        model_path = os.path.join(
            os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface/hub")),
            "models--Qwen--Qwen3-TTS-12Hz-1.7B-Base",
            "snapshots", "fd4b254389122332181a7c3db7f27e918eec64e3"
        )

    print(f"Loading model: {model_path} ({dtype_name}) on {device}...")
    model = Qwen3TTSModel.from_pretrained(
        model_path,
        device_map=device,
        dtype=dtype,
        local_files_only=True,
    )
    print("Model loaded.")

    voices = voices_config.get("references", {})
    print(f"\nGenerating demo for {len(voices)} voices...\n")

    for vname, ref in sorted(voices.items()):
        ref_wav = os.path.join(ROOT, ref["wav"])
        if not os.path.exists(ref_wav):
            print(f"  {vname}: SKIP (ref not found: {ref_wav})")
            continue

        out_path = os.path.join(OUT_DIR, f"{vname}.wav")
        if os.path.exists(out_path):
            print(f"  {vname}: SKIP (exists)")
            continue

        print(f"  {vname}...", end=" ", flush=True)

        try:
            wavs, sr = model.generate_voice_clone(
                text=DEMO_TEXT,
                ref_audio=ref_wav,
                x_vector_only_mode=True,
                temperature=0.2,
                top_p=0.9,
            )
            sf.write(out_path, wavs[0], sr)
            dur = len(wavs[0]) / sr
            print(f"{dur:.1f}s")
        except Exception as e:
            print(f"ERROR: {e}")

    # Summary
    files = [f for f in os.listdir(OUT_DIR) if f.endswith('.wav') and not f.startswith('demo_')]
    print(f"\nDone. {len(files)} files in {OUT_DIR}/")
    for f in sorted(files):
        w, sr = sf.read(os.path.join(OUT_DIR, f))
        print(f"  {f}: {len(w)/sr:.1f}s")

if __name__ == "__main__":
    main()
