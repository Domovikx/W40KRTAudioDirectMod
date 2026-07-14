"""
Silero TTS — генерация WAV (офлайн, PyTorch)
=============================================

Контракт:
  generate(text: str, output: str, voice: str) -> float
    text    — очищенный текст без тегов
    output  — путь к WAV файлу
    voice   — "eugene" | "aidar" | "xenia" | "baya" | "kseniya"
    return  — длительность в секундах

Конфиг: см. config/default.yaml → silero_*

Документация:
  - Модель: Silero v5_5_ru (https://github.com/snakers4/silero-models)
  - Голоса: 5 (2М + 3Ж)
  - Формат: WAV 48000 Гц, 16-bit, mono
  - Зависимости: torch, scipy (уже установлены)

Особенности:
  - put_accent (+), put_yo (ё), put_stress_homo (омографы)
  - SSML: <break time="500ms"/> ✅ | <prosody rate="+N%"> ⚠️ | <emphasis> ❌
"""

from __future__ import annotations
import os, sys, struct, time, re
from pathlib import Path

MOD_DIR = Path(__file__).parent.parent
_silero_model = None


def _model():
    global _silero_model
    if _silero_model is None:
        import torch
        device = torch.device("cpu")
        print("  loading Silero v5_5_ru...", end=" ", flush=True)
        ts = time.time()
        m, _ = torch.hub.load(
            "snakers4/silero-models", "silero_tts", "ru", "v5_5_ru",
            trust_repo=True, force_reload=False,
        )
        m.to(device)
        _silero_model = m
        print(f"done ({time.time()-ts:.1f}s)")
    return _silero_model


def generate(text: str, output: str, voice: str = "eugene") -> float:
    """Сгенерировать WAV через Silero.
    
    Args:
        text: очищенный текст
        output: путь до WAV файла
        voice: eugene | aidar | xenia | baya | kseniya
    
    Returns:
        float — длительность в секундах
    """
    import yaml, scipy.io.wavfile as wav
    m = _model()

    cfg = {
        "silero_sample_rate": 48000,
        "silero_put_accent": True,
        "silero_put_stress_homo": True,
        "silero_put_yo": True,
        "silero_put_stress_single": True,
    }
    cfg_path = MOD_DIR / "config" / "default.yaml"
    if cfg_path.exists():
        with open(cfg_path) as f:
            cfg.update({k.split("silero_", 1)[1] if "silero_" in k else k: v
                       for k, v in (yaml.safe_load(f) or {}).items()
                       if k.startswith("silero_")})

    audio = m.apply_tts(
        text=text, speaker=voice,
        sample_rate=cfg.get("sample_rate", 48000),
        put_accent=cfg.get("put_accent", True),
        put_stress_homo=cfg.get("put_stress_homo", True),
        put_yo=cfg.get("put_yo", True),
        stress_single_vowel=cfg.get("stress_single_vowel", True),
    )
    wav.write(output, cfg.get("sample_rate", 48000), audio.numpy())
    return audio.shape[0] / cfg.get("sample_rate", 48000)


def duration(path: str) -> float:
    """Прочитать длительность WAV из заголовка."""
    try:
        with open(path, "rb") as f:
            d = f.read()
        if len(d) < 44:
            return 0.0
        sr = struct.unpack_from("<I", d, 24)[0]
        bits = struct.unpack_from("<H", d, 34)[0]
        pos = 12
        while pos + 8 <= len(d):
            cid = d[pos:pos+4]
            sz = struct.unpack_from("<I", d, pos+4)[0]
            if cid == b"data":
                return sz / (sr * bits / 8) if sr > 0 else 0.0
            if sz == 0:
                break
            pos += 8 + sz
    except Exception:
        pass
    return 0.0
