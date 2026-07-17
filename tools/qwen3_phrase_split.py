"""
Qwen3-TTS: разбивка фразы на части, генерация + склейка.
Читает tests/phrase_split.yaml, использует scene_presets из config/default.yaml
"""
import os, sys, time, yaml
from pathlib import Path
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = ROOT / "tests" / "phrase_split.yaml"
CONFIG_PATH = ROOT / "config" / "default.yaml"

def load_scene_presets():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg.get("qwen3_scene_presets", {})

def main():
    with open(YAML_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    presets = load_scene_presets()

    sys.path.insert(0, str(ROOT / "tools"))
    from qwen3_tts import generate

    OUT = ROOT / cfg["output_dir"]
    os.makedirs(OUT, exist_ok=True)

    base_kwargs = {k: cfg[k] for k in
        ["top_k", "repetition_penalty",
         "max_new_tokens", "do_sample"]}

    parts = cfg["parts"]
    total = len(parts)
    all_wavs = []
    sr = None

    for i, part in enumerate(parts, 1):
        out_path = OUT / part["output"]

        scene = part.get("scene", "default")
        preset = presets.get(scene, presets.get("default", {}))

        temperature = part.get("temperature", preset.get("temperature"))
        top_p = part.get("top_p", preset.get("top_p"))
        instruct = part.get("instruct") if "instruct" in part else preset.get("instruct", "")

        kwargs = {**base_kwargs}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if top_p is not None:
            kwargs["top_p"] = top_p

        print(f"[{i}/{total}] {part['output']}  voice={part['voice']}  scene={scene}  temp={kwargs.get('temperature','?')}  instruct={instruct!r}")

        if out_path.exists():
            print(f"  exists, skipping")
        else:
            try:
                dur = generate(part["text_clean"], str(out_path),
                              voice=part["voice"], instruct=instruct,
                              **kwargs)
                print(f"  generated: {dur:.1f}s")
            except Exception as e:
                print(f"  ERROR: {e}")
                continue

        wav, file_sr = sf.read(str(out_path))
        all_wavs.append(wav)
        sr = file_sr

    if not all_wavs:
        print("No audio generated!")
        return

    pause_sec = cfg.get("pause_between_parts", 0.0)
    pause_samples = int(sr * pause_sec) if pause_sec > 0 else 0
    silence = np.zeros(pause_samples, dtype=all_wavs[0].dtype)

    segments = []
    for w in all_wavs:
        segments.append(w)
        if pause_samples > 0:
            segments.append(silence)
    segments.pop()

    combined = np.concatenate(segments)
    concat_path = OUT / cfg["concat_output"]
    sf.write(str(concat_path), combined, sr)
    total_dur = combined.shape[0] / sr
    print(f"\nСклеено: {concat_path}  ({total_dur:.1f}s всего, пауза {pause_sec}s)")

if __name__ == "__main__":
    main()
