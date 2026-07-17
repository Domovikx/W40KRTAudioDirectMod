"""
Generate a voice reference (WAV + TXT) via Qwen3-TTS VoiceDesign model.
Used as the first step in the Full ICL pipeline.

Usage:
    python tools/qwen3_voice_design.py [voice_name] [instruct_file] [text_file]

Defaults to wh40k_narrator with a long Imperial sermon (~30s at 48kHz).
Output: refs/{voice_name}_reference.wav + refs/{voice_name}_reference.txt
"""

import torch
import soundfile as sf
import os
import sys

PINOKIO_APP = r"C:\pinokio\api\Qwen3-TTS-Pinokio.git\app"
sys.path.insert(0, PINOKIO_APP)

from qwen_tts import Qwen3TTSModel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFS_DIR = os.path.join(ROOT, "refs")
os.makedirs(REFS_DIR, exist_ok=True)

MODEL_PATH = os.path.join(
    PINOKIO_APP, "..",
    "cache", "HF_HOME", "hub",
    "models--Qwen--Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "snapshots", "5ecdb67327fd37bb2e042aab12ff7391903235d3"
)

VOICE_NAME = sys.argv[1] if len(sys.argv) > 1 else "wh40k_narrator"

if len(sys.argv) > 2:
    with open(sys.argv[2], "r", encoding="utf-8") as f:
        INSTRUCT = f.read().strip()
else:
    INSTRUCT = (
        "Low male voice, age 45-55, chest resonance, "
        "slow measured pace, clear Imperial diction, "
        "restrained emotion with a hint of reverence and fatalism, "
        "like a voiceover in a documentary about war or a religious sermon. "
        "No accent, no hoarseness, no theatrical declamation."
    )

if len(sys.argv) > 3:
    with open(sys.argv[3], "r", encoding="utf-8") as f:
        TEXT = f.read().strip()
else:
    TEXT = (
        "Во тьме далёкого будущего есть только война. "
        "Империум человечества стоит на краю гибели, "
        "и лишь вера в Императора удерживает его от падения во тьму. "
        "Слушай внимательно, странник, ибо Варп не прощает ошибок, "
        "а ересь начинается с малого — с сомнения в сердце. "
        "Человек слаб, но единство делает нас сильными. "
        "Тысячи лет мы сражаемся с ксеносами, мутантами и демонами, "
        "и каждый день кто-то отдаёт жизнь за Империум. "
        "Не ради славы — ради будущего, ради тех, кто придёт после. "
        "Помни: нет мира среди звёзд, лишь забвение и боль. "
        "Но мы держим строй. Мы — Адептус Милитарум, "
        "мы — стальной кулак Империума, и мы не отступим. "
        "Император защищает, но только тех, кто стоит твёрдо "
        "и не дрожит перед тьмой. Слава Императору! "
        "Смерть врагам человечества! "
        "Вера — наше оружие, долг — наша броня."
    )

print(f"Loading VoiceDesign model (float32, CPU)...")
design_model = Qwen3TTSModel.from_pretrained(
    MODEL_PATH,
    device_map="cpu",
    dtype=torch.float32,
)

print(f"Generating voice design: {VOICE_NAME} ({len(TEXT)} chars)")
print(f"Instruct: {INSTRUCT[:80]}...")
wavs, sr = design_model.generate_voice_design(
    text=TEXT,
    language="Russian",
    instruct=INSTRUCT,
    temperature=0.3,
    top_p=0.9,
    repetition_penalty=1.05,
    max_new_tokens=4096,
)

ref_wav = os.path.join(REFS_DIR, f"{VOICE_NAME}_reference.wav")
ref_txt = os.path.join(REFS_DIR, f"{VOICE_NAME}_reference.txt")
sf.write(ref_wav, wavs[0], sr)
with open(ref_txt, "w", encoding="utf-8") as f:
    f.write(TEXT)

duration = len(wavs[0]) / sr
print(f"Done: {ref_wav} ({duration:.1f}s, {sr}Hz, float32)")
