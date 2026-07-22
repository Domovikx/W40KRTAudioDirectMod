"""
Voice clone demo: generate same text with two different reference WAVs.
Usage: python tools/voice_clone_demo.py
Output: refs/samples/Сергей Чихачёв_demo.wav, refs/samples/Сергей Чихачёв 2_demo.wav
"""

import os, sys, time, warnings
warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINOKIO_APP = r"C:\pinokio\api\Qwen3-TTS-Pinokio.git\app"
sys.path.insert(0, PINOKIO_APP)

from qwen_tts import Qwen3TTSModel

DEMO_TEXT = (
    "Варп — это зеркало души, капитан. "
    "Он показывает не то, что ты хочешь увидеть, а то, что ты боишься увидеть. "
    "Империум держится не на стали и лазганах, а на вере миллионов людей, "
    "которые никогда не видели Императора, но знают: он есть. "
    "И пока мы верим, тьма не поглотит нас."
)

def main():
    refs = [
        ("Сергей Чихачёв", os.path.join(ROOT, "refs", "samples", "Сергей Чихачёв.wav")),
        ("Сергей Чихачёв 2", os.path.join(ROOT, "refs", "samples", "Сергей Чихачёв 2.wav")),
    ]

    print("Loading Base model (CPU, float32)...")
    t0 = time.time()
    model = Qwen3TTSModel.from_pretrained(
        "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        device_map="cpu",
        dtype=torch.float32,
        local_files_only=True,
    )
    print(f"Model loaded in {time.time() - t0:.1f}s")

    import soundfile as sf

    for name, wav_path in refs:
        print(f"\n{'='*60}")
        print(f"Processing: {name}")
        print(f"  Reference: {wav_path}")
        if not os.path.exists(wav_path):
            print(f"  !! WAV not found, skipping")
            continue

        print("  Creating voice clone prompt (x_vector_only)...")
        try:
            prompt_items = model.create_voice_clone_prompt(
                ref_audio=wav_path,
                ref_text="",
                x_vector_only_mode=True,
            )
        except Exception as e:
            print(f"  !! Prompt creation failed: {e}")
            continue

        out_path = os.path.join(ROOT, "refs", "samples", f"{name}_demo.wav")
        print(f"  Generating demo ({len(DEMO_TEXT)} chars)...")
        try:
            wavs, sr = model.generate_voice_clone(
                text=DEMO_TEXT,
                language="Russian",
                voice_clone_prompt=prompt_items,
                temperature=0.2,
                top_p=0.9,
                repetition_penalty=1.05,
                max_new_tokens=2048,
            )
            sf.write(out_path, wavs[0], sr)
            dur = wavs[0].shape[0] / sr
            print(f"  => {out_path} ({dur:.1f}s)")
        except Exception as e:
            print(f"  !! Generation failed: {e}")
            continue

    print("\nDone!")

if __name__ == "__main__":
    import torch
    main()
