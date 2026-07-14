"""
Gemini TTS — генерация WAV (онлайн, Google Gemini 3.1 Flash)
=============================================================

Контракт:
  generate(text: str, output: str, voice: str, proxy: str = "") -> float
    text    — очищенный текст без тегов
    output  — путь к WAV файлу
    voice   — имя голоса Gemini (см. VOICES)
    proxy   — HTTP прокси (опционально: "http://ip:port")
    return  — длительность в секундах

Конфиг: см. config/default.yaml → gemini_*

Зависимости: google.genai (уже установлен)

Голоса: 30 (15М + 15Ж)
Формат: WAV 24000 Гц, 16-bit, mono
Лимит: ~5 RPM на бесплатном ключе (пауза 20+ сек между вызовами)
"""

from __future__ import annotations
import os, tempfile, struct

def build_prompt(text: str, character_name: str, personality: str = "", scene: str = "") -> str:
    """Оборачивает текст в промпт для Gemini 3.1 Flash TTS.

    Без полного промпта Gemini обрезает текст до первого предложения.
    """
    if not personality:
        personality = "neutral"
    if not scene:
        scene = f"{character_name} говорит."

    return (
        "Synthesize speech for the performance defined below.\n"
        "The profile, scene, and performance notes are direction only.\n"
        "Do NOT speak them.\n"
        "Speak ONLY the lines under #### TRANSCRIPT.\n"
        "\n"
        f"# AUDIO PROFILE: {character_name}\n"
        f'## "{personality}"\n'
        "\n"
        f"## SCENE: {scene}\n"
        "\n"
        "#### TRANSCRIPT\n"
        f"{text}"
    )


VOICES = {
    # Male (15)
    "Achird":         ("M", "Friendly"),
    "Algenib":        ("M", "Gravelly"),
    "Algieba":        ("M", "Smooth"),
    "Alnilam":        ("M", "Firm"),
    "Charon":         ("M", "Informative"),
    "Enceladus":      ("M", "Breathy"),
    "Fenrir":         ("M", "Excitable"),
    "Iapetus":        ("M", "Clear"),
    "Orus":           ("M", "Firm"),
    "Puck":           ("M", "Upbeat"),
    "Rasalgethi":     ("M", "Informative"),
    "Sadachbia":      ("M", "Lively"),
    "Sadaltager":     ("M", "Knowledgeable"),
    "Schedar":        ("M", "Even"),
    "Umbriel":        ("M", "Easy-going"),
    "Zubenelgenubi":  ("M", "Casual"),
    # Female (15)
    "Achernar":       ("F", "Soft"),
    "Aoede":          ("F", "Breezy"),
    "Autonoe":        ("F", "Bright"),
    "Callirrhoe":     ("F", "Easy-going"),
    "Despina":        ("F", "Smooth"),
    "Erinome":        ("F", "Clear"),
    "Gacrux":         ("F", "Mature"),
    "Kore":           ("F", "Firm"),
    "Laomedeia":      ("F", "Upbeat"),
    "Leda":           ("F", "Youthful"),
    "Pulcherrima":    ("F", "Forward"),
    "Sulafat":        ("F", "Warm"),
    "Vindemiatrix":   ("F", "Gentle"),
    "Zephyr":         ("F", "Bright"),
}


def generate(text: str, output: str, voice: str = "Kore", proxy: str = "") -> float:
    """Сгенерировать WAV через Gemini 3.1 Flash TTS.

    Args:
        text: очищенный текст
        output: путь до WAV файла
        voice: имя голоса (см. VOICES)
        proxy: HTTP прокси ("http://ip:port" или "")

    Returns:
        float — длительность в секундах
    """
    if proxy:
        os.environ["HTTPS_PROXY"] = proxy
        os.environ["HTTP_PROXY"] = proxy

    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        # fallback: ищем в config/default.yaml
        import yaml
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "default.yaml")
        if os.path.exists(cfg_path):
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f) or {}
            api_key = cfg.get("gemini_api_key", "")

    if not api_key:
        raise RuntimeError(
            "Gemini API key not found. "
            "Set GEMINI_API_KEY env var or gemini_api_key in config/default.yaml"
        )

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model="gemini-3.1-flash-tts-preview",
        contents=text,
        config=types.GenerateContentConfig(
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice
                    )
                )
            )
        ),
    )

    # извлечь аудио (L16 PCM 24kHz)
    audio_bytes = None
    for c in response.candidates:
        for p in c.content.parts:
            if hasattr(p, "inline_data") and p.inline_data:
                data = p.inline_data.data
                if isinstance(data, str):
                    import base64
                    data = base64.b64decode(data)
                audio_bytes = data
                break

    if audio_bytes is None:
        raise RuntimeError("Gemini TTS: no audio in response")

    # записать WAV (L16 PCM → WAV header)
    sample_rate = 24000
    with open(output, "wb") as f:
        data_size = len(audio_bytes)
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))           # chunk size
        f.write(struct.pack("<H", 1))             # PCM
        f.write(struct.pack("<H", 1))             # mono
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", sample_rate * 2))  # byte rate
        f.write(struct.pack("<H", 2))             # block align
        f.write(struct.pack("<H", 16))            # bits per sample
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(audio_bytes)

    duration = data_size / (sample_rate * 2)
    return duration


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
