"""
Qwen3 TTS — генерация WAV (локально, Alibaba Qwen3-TTS)
=========================================================

Контракт:
  generate(text, output, voice="Dylan", instruct="", **gen_kwargs) -> float
    text       — текст для озвучивания (без тегов)
    output     — путь к WAV файлу
    voice      — имя голоса Qwen3 (см. VOICES)
    instruct   — инструкция по стилю/эмоции (опционально)
    gen_kwargs — temperature, top_k, top_p, repetition_penalty, max_new_tokens
    return     — длительность в секундах

Конфиг: см. config/default.yaml → qwen3_*

Зависимости: qwen-tts (pip install qwen-tts)

Голоса: 9 встроенных (Vivian, Serena, Uncle_Fu, Dylan, Eric, Ryan, Aiden, Ono_Anna, Sohee)
Формат: WAV 24000 Гц, 16-bit, mono
"""

from __future__ import annotations
import os, time, logging
from typing import Optional

logger = logging.getLogger(__name__)

VOICES = {
    "Vivian":    ("F", "Bright, slightly edgy, young female"),
    "Serena":    ("F", "Warm, gentle young female"),
    "Uncle_Fu":  ("M", "Seasoned male, low mellow timbre"),
    "Dylan":     ("M", "Youthful, clear, natural"),
    "Eric":      ("M", "Lively, slightly husky"),
    "Ryan":      ("M", "Dynamic, strong rhythmic drive"),
    "Aiden":     ("M", "Sunny American male, clear midrange"),
    "Ono_Anna":  ("F", "Playful Japanese female, light"),
    "Sohee":     ("F", "Warm Korean female, rich emotion"),
}

# Optimized defaults (based on official generation_config.json + tuning for dialog)
# float32 gives noticeably better quality than bfloat16 (verified on CPU).
# For more expressiveness: temperature=0.9, top_p=1.0
# For more stability: temperature=0.8, top_p=0.9
DEFAULT_GEN_KWARGS = {
    "temperature": 0.85,
    "top_k": 50,
    "top_p": 0.95,
    "repetition_penalty": 1.05,
    "max_new_tokens": 8192,
    "do_sample": True,
}

_model = None


def _get_model():
    global _model
    if _model is None:
        t0 = time.time()
        import torch
        from qwen_tts import Qwen3TTSModel

        logger.info("Loading Qwen3-TTS-12Hz-1.7B-CustomVoice (CPU, float32)...")
        _model = Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
            device_map="cpu",
            dtype=torch.float32,
        )
        logger.info(f"Model loaded in {time.time() - t0:.1f}s")
    return _model


def generate(text: str, output: str, voice: str = "Dylan", instruct: str = "",
             **gen_kwargs) -> float:
    """Сгенерировать WAV через Qwen3-TTS 1.7B (локально)."""
    import soundfile as sf

    model = _get_model()

    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)

    kwargs = {**DEFAULT_GEN_KWARGS, **gen_kwargs}

    t0 = time.time()
    logger.info(f"Qwen3 TTS: {voice} instr={instruct!r} kwargs={kwargs} -> {output}")

    wavs, sr = model.generate_custom_voice(
        text=text,
        language="Russian",
        speaker=voice,
        instruct=instruct or "",
        **kwargs,
    )

    sf.write(output, wavs[0], sr)
    duration = wavs[0].shape[0] / sr
    logger.info(f"Done: {output} ({duration:.2f}s, gen {time.time() - t0:.1f}s)")
    return duration


def duration(path: str) -> float:
    """Прочитать длительность WAV из заголовка."""
    import struct
    try:
        with open(path, "rb") as f:
            d = f.read()
        if len(d) < 44:
            return 0.0
        sr = struct.unpack_from("<I", d, 24)[0]
        bits = struct.unpack_from("<H", d, 34)[0]
        pos = 12
        while pos + 8 <= len(d):
            cid = d[pos:pos + 4]
            sz = struct.unpack_from("<I", d, pos + 4)[0]
            if cid == b"data":
                return sz / (sr * bits / 8) if sr > 0 else 0.0
            if sz == 0:
                break
            pos += 8 + sz
    except Exception:
        pass
    return 0.0
