"""
Qwen3-TTS Instruct тест — читает tests/instruct_test.yaml, генерирует WAV.
"""
import os, sys, time, yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = ROOT / "tests" / "instruct_test.yaml"
OUT_DIR = ROOT / "samples" / "qwen3_17b"

def main():
    with open(YAML_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    sys.path.insert(0, str(ROOT / "tools"))
    from qwen3_tts import generate

    base_kwargs = {k: cfg[k] for k in [
        "top_k", "top_p", "repetition_penalty",
        "max_new_tokens", "do_sample",
    ]}

    tests = cfg["tests"]
    total = len(tests)
    for i, t in enumerate(tests, 1):
        out = OUT_DIR / t["output"]
        if out.exists():
            print(f"[{i}/{total}] SKIP {t['output']} (exists)")
            continue

        kwargs = {**base_kwargs, "temperature": t["temperature"]}
        print(f"[{i}/{total}] {t['output']}  instr={t['name']!r}  temp={t['temperature']}")
        try:
            dur = generate(cfg["text"], str(out), voice=cfg["voice"],
                          instruct=t["instruct"], **kwargs)
            print(f"  -> {dur:.1f}s")
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\nDone! {total} samples in {OUT_DIR}")

if __name__ == "__main__":
    main()
