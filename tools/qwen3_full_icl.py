"""
Batch dialog generation via Qwen3-TTS Base model + Full ICL (voice clone).

Reads catalog/people/*.yaml with multi-part phrases (parts: [{speaker, text_clean}]).
Resolves speaker → voice reference from config/voices.yaml characters lists.
Generates per-part WAVs, then concatenates into final per-phrase WAV.

Usage:
    python tools/qwen3_full_icl.py [voice_name]

    voice_name — optional filter (generate only this voice)
    Without args — all voices from config/voices.yaml
"""

import os, sys
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
import glob
import yaml
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

PINOKIO_APP = r"C:\pinokio\api\Qwen3-TTS-Pinokio.git\app"
sys.path.insert(0, PINOKIO_APP)

from qwen_tts import Qwen3TTSModel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTS_DIR = os.path.join(ROOT, "output", "full_icl")
GAME_DIR = os.path.join(ROOT, "Localization", "ruRU")
CONFIG_VOICES = os.path.join(ROOT, "config", "voices.yaml")
CONFIG_DEFAULT = os.path.join(ROOT, "config", "default.yaml")
CATALOG_DIR = os.path.join(ROOT, "catalog", "people")
os.makedirs(GAME_DIR, exist_ok=True)
os.makedirs(PARTS_DIR, exist_ok=True)


def load_defaults() -> dict:
    with open(CONFIG_DEFAULT, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_voices_config() -> dict:
    with open(CONFIG_VOICES, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_catalog_phrases() -> Dict[str, dict]:
    """Load all YAMLs from catalog/people/.
    Returns dict: character_name -> yaml_data (with phrases list)
    """
    catalog = {}
    for yaml_path in glob.glob(os.path.join(CATALOG_DIR, "*.yaml")):
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        char_name = data.get("name", os.path.splitext(os.path.basename(yaml_path))[0])
        catalog[char_name] = data
    return catalog


def normalize_name(name: str) -> str:
    return name.lower().replace("_", " ").replace("-", " ").strip()


def resolve_speaker_to_voice(
    speaker: str,
    voices_config: dict,
) -> Optional[str]:
    """Map a speaker name to a voice_name from voices.yaml by matching characters lists."""
    norm_speaker = normalize_name(speaker)

    if norm_speaker == "narrator":
        for vname, ref in voices_config.get("references", {}).items():
            for c in ref.get("characters", []):
                if normalize_name(c) == "narrator":
                    return vname
        return None

    for vname, ref in voices_config.get("references", {}).items():
        for c in ref.get("characters", []):
            norm_c = normalize_name(c)
            if norm_speaker == norm_c or norm_speaker in norm_c or norm_c in norm_speaker:
                return vname

    return None


def get_voice_prompt(
    model: Qwen3TTSModel,
    voice_name: str,
    voices_config: dict,
    prompt_cache: dict,
):
    """Create or retrieve cached voice clone prompt items for a voice."""
    if voice_name in prompt_cache:
        return prompt_cache[voice_name]

    ref = voices_config.get("references", {}).get(voice_name)
    if not ref:
        print(f"    !! Voice '{voice_name}' not found in config/voices.yaml")
        return None

    ref_wav = os.path.join(ROOT, ref["wav"])
    if not os.path.exists(ref_wav):
        print(f"    !! Reference WAV missing for '{voice_name}'")
        return None

    print(f"    Creating prompt for '{voice_name}' (x_vector_only)...")
    try:
        prompt_items = model.create_voice_clone_prompt(
            ref_audio=ref_wav,
            ref_text="",
            x_vector_only_mode=True,
        )
        prompt_cache[voice_name] = prompt_items
        return prompt_items
    except Exception as e:
        print(f"    !! Prompt creation failed for '{voice_name}': {e}")
        return None


def concat_wavs(part_paths: List[str], output_path: str, gap_ms: int = 300):
    """Concatenate WAV files with optional silence gap."""
    import wave

    if not part_paths:
        return

    all_frames = []
    params = None

    for i, path in enumerate(part_paths):
        with wave.open(path, "rb") as wf:
            if params is None:
                params = (wf.getnchannels(), wf.getsampwidth(), wf.getframerate())
            frames = wf.readframes(wf.getnframes())
            all_frames.append(frames)

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
    cfg = load_defaults()
    voices_config = load_voices_config()
    catalog = load_catalog_phrases()
    filter_voice = sys.argv[1] if len(sys.argv) > 1 else None

    model_id = cfg.get("qwen3_base_model", "Qwen/Qwen3-TTS-12Hz-1.7B-Base")
    device = cfg.get("qwen3_base_device", "cpu")
    dtype_name = cfg.get("qwen3_base_dtype", "float32")
    dtype = torch.float32 if dtype_name == "float32" else torch.bfloat16
    temperature = cfg.get("qwen3_base_temperature", 0.2)
    top_p = cfg.get("qwen3_base_top_p", 0.9)
    rep_penalty = cfg.get("qwen3_base_repetition_penalty", 1.05)
    max_new_tokens = cfg.get("qwen3_base_max_new_tokens", 2048)
    model_path = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
    if not os.path.exists(model_path):
        model_path = os.path.join(
            os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface/hub")),
            "models--Qwen--Qwen3-TTS-12Hz-1.7B-Base",
            "snapshots", "fd4b254389122332181a7c3db7f27e918eec64e3"
        )
    print(f"Loading Base model: {model_path} ({dtype_name})")
    model = Qwen3TTSModel.from_pretrained(
        model_path,
        device_map=device,
        dtype=dtype,
        local_files_only=True,
    )

    prompt_cache: Dict[str, dict] = {}
    total = 0
    skipped = 0

    for char_name, char_data in catalog.items():
        for phrase in char_data.get("phrases", []):
            parts = phrase.get("parts")
            if not parts:
                continue

            guid = phrase.get("guid", "")
            part_paths = []
            success = True
            first_voice = None

            for idx, part in enumerate(parts):
                speaker = part.get("speaker", "")
                text_clean = part.get("text_clean", "").strip()
                if not text_clean:
                    continue

                resolved = resolve_speaker_to_voice(speaker, voices_config)
                if not resolved:
                    print(f"  !! {guid}: cannot resolve speaker '{speaker}'")
                    success = False
                    break

                if filter_voice and resolved != filter_voice:
                    continue

                if first_voice is None:
                    first_voice = resolved
                parts_out_dir = os.path.join(PARTS_DIR, resolved)
                os.makedirs(parts_out_dir, exist_ok=True)
                os.makedirs(GAME_DIR, exist_ok=True)

                prompt = get_voice_prompt(model, resolved, voices_config, prompt_cache)
                if not prompt:
                    success = False
                    break

                part_path = os.path.join(parts_out_dir, f"{guid}__{idx+1}.wav")
                part_paths.append(part_path)

                if os.path.exists(part_path):
                    print(f"  {guid}__{idx+1} (cached) [{speaker} -> {resolved}]")
                    continue

                print(f"  {guid}__{idx+1} [{speaker} -> {resolved}]: {text_clean[:60]}...")
                try:
                    wavs, sr = model.generate_voice_clone(
                        text=text_clean,
                        language="Russian",
                        voice_clone_prompt=prompt,
                        temperature=temperature,
                        top_p=top_p,
                        repetition_penalty=rep_penalty,
                        max_new_tokens=max_new_tokens,
                    )
                    sf.write(part_path, wavs[0], sr)
                except Exception as e:
                    print(f"      !! {e}")
                    success = False
                    break

            if success and part_paths:
                merged_path = os.path.join(GAME_DIR, f"{guid}.wav")
                if os.path.exists(merged_path):
                    skipped += 1
                else:
                    concat_wavs(part_paths, merged_path)
                    total += 1
            elif not success:
                print(f"  !! {guid}: generation failed")

    print(f"\nDone. Generated: {total}, Skipped: {skipped}")


if __name__ == "__main__":
    import torch
    import soundfile as sf
    main()
