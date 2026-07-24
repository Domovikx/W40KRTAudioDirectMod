"""Generate WAVs for target characters (imports core from qwen3_full_icl)."""

import os, sys

PINOKIO_APP = r"C:\pinokio\api\Qwen3-TTS-Pinokio.git\app"
sys.path.insert(0, PINOKIO_APP)

import yaml
import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = yaml.safe_load(open(os.path.join(ROOT, "config", "default.yaml"), "r", encoding="utf-8"))
voices_cfg = yaml.safe_load(open(os.path.join(ROOT, "config", "voices.yaml"), "r", encoding="utf-8"))

TARGET_FILES = [
    "Cassia Orsellio.yaml",
    "Heinrix van Calox.yaml",
]


def normalize_name(name):
    return name.lower().replace("_", " ").replace("-", " ").strip()


def resolve_speaker(speaker):
    norm = normalize_name(speaker)
    for vname, ref in voices_cfg.get("references", {}).items():
        for c in ref.get("characters", []):
            nc = normalize_name(c)
            if norm == nc or norm in nc or nc in norm:
                return vname
    return None


def get_prompt(model, voice_name, prompts):
    if voice_name in prompts:
        return prompts[voice_name]
    ref = voices_cfg["references"].get(voice_name)
    if not ref:
        print(f"    !! Voice not found: {voice_name}")
        return None
    ref_wav = os.path.join(ROOT, ref["wav"])
    if not os.path.exists(ref_wav):
        print(f"    !! Reference missing: {ref_wav}")
        return None
    print(f"    Creating prompt for {voice_name}...")
    prompts[voice_name] = model.create_voice_clone_prompt(
        ref_audio=ref_wav, ref_text="", x_vector_only_mode=True,
    )
    return prompts[voice_name]


def concat_wavs(part_paths, output_path, gap_ms=300):
    import wave
    all_frames, params = [], None
    for i, path in enumerate(part_paths):
        with wave.open(path, "rb") as wf:
            if params is None:
                params = (wf.getnchannels(), wf.getsampwidth(), wf.getframerate())
            all_frames.append(wf.readframes(wf.getnframes()))
        if gap_ms > 0 and i < len(part_paths) - 1:
            gap_frames = int(params[2] * params[0] * params[1] * gap_ms / 1000 / 2)
            all_frames.append(b"\x00" * gap_frames)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(params[0])
        wf.setsampwidth(params[1])
        wf.setframerate(params[2])
        wf.writeframes(b"".join(all_frames))
    total_sec = len(b"".join(all_frames)) // (params[0] * params[1]) / params[2]
    print(f"      => {output_path} ({total_sec:.1f}s)")


def main():
    model_path = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
    if not os.path.exists(model_path):
        import glob
        snaps = glob.glob(os.path.join(
            os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface/hub")),
            "models--Qwen--Qwen3-TTS-12Hz-1.7B-Base", "snapshots", "*"))
        if snaps:
            model_path = snaps[0]

    device = cfg.get("qwen3_base_device", "cpu")
    dtype_name = cfg.get("qwen3_base_dtype", "float32")
    dtype = torch.float32 if dtype_name == "float32" else torch.bfloat16
    temperature = cfg.get("qwen3_base_temperature", 0.2)
    top_p = cfg.get("qwen3_base_top_p", 0.9)
    rep_penalty = cfg.get("qwen3_base_repetition_penalty", 1.05)
    max_tokens = cfg.get("qwen3_base_max_new_tokens", 2048)

    print(f"Loading model: {model_path} ({dtype_name})")
    model = Qwen3TTSModel.from_pretrained(
        model_path, device_map=device, dtype=dtype, local_files_only=True,
    )

    prompts = {}
    total = 0
    skipped = 0

    for fname in TARGET_FILES:
        fpath = os.path.join(ROOT, "catalog", "people", fname)
        if not os.path.exists(fpath):
            print(f"!! File not found: {fpath}")
            continue
        data = yaml.safe_load(open(fpath, "r", encoding="utf-8"))
        char_name = data.get("name", fname)
        print(f"\n=== {char_name} ===")

        for phrase in data.get("phrases", []):
            parts = phrase.get("parts")
            if not parts:
                continue

            guid = phrase.get("guid", "")
            part_paths = []
            success = True

            for idx, part in enumerate(parts):
                speaker = part.get("speaker", "")
                text = part.get("text_clean", "").strip()
                if not text:
                    continue

                resolved = resolve_speaker(speaker)
                if not resolved:
                    print(f"  !! {guid}: cannot resolve '{speaker}'")
                    success = False
                    break

                parts_out_dir = os.path.join(ROOT, "output", "full_icl", resolved)
                os.makedirs(parts_out_dir, exist_ok=True)
                part_path = os.path.join(parts_out_dir, f"{guid}__{idx+1}.wav")
                part_paths.append(part_path)

                if os.path.exists(part_path):
                    print(f"  {guid[:12]}__{idx+1} (cached) [{speaker}]")
                    continue

                prompt = get_prompt(model, resolved, prompts)
                if not prompt:
                    success = False
                    break

                print(f"  {guid[:12]}__{idx+1} [{speaker}]: {text[:60]}...")
                wavs, sr = model.generate_voice_clone(
                    text=text, language="Russian",
                    voice_clone_prompt=prompt,
                    temperature=temperature, top_p=top_p,
                    repetition_penalty=rep_penalty,
                    max_new_tokens=max_tokens,
                )
                sf.write(part_path, wavs[0], sr)

            if success and part_paths:
                merged_path = os.path.join(ROOT, "Localization", "ruRU", f"{guid}.wav")
                if os.path.exists(merged_path):
                    skipped += 1
                else:
                    concat_wavs(part_paths, merged_path)
                    total += 1

        print(f"\nDone: {char_name}")

    print(f"\n=== Finished. Generated: {total}, Skipped: {skipped} ===")


if __name__ == "__main__":
    main()
