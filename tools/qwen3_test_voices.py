"""
Qwen3-TTS тест всех голосов — читает tests/instruct_test_2.yaml
"""
import os, sys, time, yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = ROOT / "tests" / "instruct_test_2.yaml"
OUT_DIR = ROOT / "samples" / "qwen3_17b"

def main():
    with open(YAML_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    sys.path.insert(0, str(ROOT / "tools"))
    from qwen3_tts import generate

    base_kwargs = {k: cfg[k] for k in [
        "top_k", "top_p", "repetition_penalty",
        "max_new_tokens", "do_sample", "temperature",
    ]}

    voices = cfg["voices"]
    total = len(voices)
    for i, v in enumerate(voices, 1):
        out = OUT_DIR / v["output"]
        if out.exists():
            print(f"[{i}/{total}] SKIP {v['output']} (exists)")
            continue

        print(f"[{i}/{total}] {v['output']}  speaker={v['speaker']}")
        try:
            dur = generate(cfg["text"], str(out), voice=v["speaker"],
                          instruct=cfg["instruct"], **base_kwargs)
            print(f"  -> {dur:.1f}s")
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\nDone! {total} samples in {OUT_DIR}")

if __name__ == "__main__":
    main()
