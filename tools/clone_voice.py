"""
Universal voice clone helper.

Usage:
    python tools/clone_voice.py <source_audio> <text_file> [output_wav]

    1. Cuts 15s from source audio (WAV 24kHz mono)
    2. Creates voice clone prompt (x_vector_only)
    3. Generates speech of text_file content in that voice

Examples:
    python tools/clone_voice.py refs/kunrad/sampleb.mp3 refs/kunrad/reference.txt
    python tools/clone_voice.py refs/teodora/sampleb.wav refs/teodora/reference.txt refs/teodora/cloned.wav
"""
import os, sys, subprocess, torch, soundfile as sf

os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
sys.path.insert(0, r"C:\pinokio\api\Qwen3-TTS-Pinokio.git\app")
from qwen_tts import Qwen3TTSModel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if len(sys.argv) < 3:
    print(__doc__)
    sys.exit(1)

src = os.path.join(ROOT, sys.argv[1]) if not os.path.isabs(sys.argv[1]) else sys.argv[1]
txt = os.path.join(ROOT, sys.argv[2]) if not os.path.isabs(sys.argv[2]) else sys.argv[2]
out = os.path.join(ROOT, sys.argv[3]) if len(sys.argv) > 3 else os.path.join(os.path.dirname(src), "cloned.wav")

ref_wav = os.path.join(os.path.dirname(out), "15s_ref.wav")

# 1. Cut 15s from source
print(f"Cutting 15s from {src} -> {ref_wav}")
subprocess.run([
    "ffmpeg", "-y", "-ss", "15", "-t", "15",
    "-i", src, "-ac", "1", "-ar", "24000", ref_wav
], check=True, capture_output=True)

# 2. Load model & create prompt
MODEL_PATH = os.path.join(
    os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface/hub")),
    "models--Qwen--Qwen3-TTS-12Hz-1.7B-Base",
    "snapshots", "fd4b254389122332181a7c3db7f27e918eec64e3"
)
print("Loading Base model (offline)...")
model = Qwen3TTSModel.from_pretrained(MODEL_PATH, device_map="cpu", dtype=torch.float32, local_files_only=True)

print("Creating prompt (x_vector_only)...")
prompt = model.create_voice_clone_prompt(ref_audio=ref_wav, ref_text="", x_vector_only_mode=True)

# 3. Generate
with open(txt, "r", encoding="utf-8") as f:
    target = f.read().strip()

print(f"Generating {len(target)} chars -> {out}")
wavs, sr = model.generate_voice_clone(
    text=target, language="Russian", voice_clone_prompt=prompt,
    temperature=0.2, top_p=0.9, repetition_penalty=1.05, max_new_tokens=4096,
)
sf.write(out, wavs[0], sr)
dur = len(wavs[0]) / sr
print(f"Done: {out} ({dur:.1f}s)")
