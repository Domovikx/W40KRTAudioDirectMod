"""
Edge TTS — генерация WAV (онлайн, Azure Neural)
================================================

Контракт:
  generate(text: str, output: str, voice: str) -> float
    text    — очищенный текст без тегов
    output  — путь к WAV файлу
    voice   — "ru-RU-DmitryNeural" (М) | "ru-RU-SvetlanaNeural" (Ж)
    return  — длительность в секундах

Конфиг: см. config/default.yaml → edge_*

Документация:
  - Движок: edge-tts (https://github.com/rany2/edge-tts)
  - Бекенд: Microsoft Azure Neural TTS (бесплатный endpoint Edge)
  - Голоса: 2 (Dmitry М + Svetlana Ж)
  - Формат: WAV 24000 Гц, 16-bit, mono
  - Зависимости: edge-tts, ffmpeg (уже установлены)
  - Интернет: требуется

Особенности:
  - Не требует API-ключа (использует публичный endpoint Edge)
  - Поддерживает rate (-50%..+50%), volume, pitch
  - Возможны изменения endpoint (Microsoft может отключить)

Подробнее: https://github.com/rany2/edge-tts
"""

from __future__ import annotations
import asyncio, os, subprocess, tempfile, struct


def _ffmpeg_path() -> str:
    """Поиск ffmpeg в системе."""
    candidates = [
        r"C:\Program Files\KMPlayer 64X\LAVFilters64\ffmpeg.exe",
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    # fallback: hope it's on PATH
    return "ffmpeg"


def generate(text: str, output: str, voice: str = "ru-RU-DmitryNeural") -> float:
    """Сгенерировать WAV через edge-tts (Azure Neural).
    
    Args:
        text: очищенный текст
        output: путь до WAV файла
        voice: ru-RU-DmitryNeural (М) | ru-RU-SvetlanaNeural (Ж)
    
    Returns:
        float — длительность в секундах
    """
    import edge_tts

    async def _gen():
        data = b""
        tts = edge_tts.Communicate(text, voice)
        async for chunk in tts.stream():
            if chunk["type"] == "audio":
                data += chunk["data"]
        return data

    mp3_data = asyncio.run(_gen())
    if not mp3_data:
        raise RuntimeError("edge-tts: no audio received")

    ffmpeg = _ffmpeg_path()
    mp3 = os.path.join(tempfile.gettempdir(), f"edge_{id(text)}.mp3")
    with open(mp3, "wb") as f:
        f.write(mp3_data)

    subprocess.run(
        [ffmpeg, "-y", "-i", mp3, "-ar", "24000", "-ac", "1", output],
        capture_output=True, timeout=30,
    )
    os.remove(mp3)

    if not os.path.exists(output):
        raise RuntimeError("edge-tts: ffmpeg conversion failed")

    # read duration
    try:
        with open(output, "rb") as f:
            d = f.read()
        sr = struct.unpack_from("<I", d, 24)[0]
        bits = struct.unpack_from("<H", d, 34)[0]
        pos = 12
        while pos + 8 <= len(d):
            chunk = d[pos:pos+4]
            sz = struct.unpack_from("<I", d, pos+4)[0]
            if chunk == b"data":
                return sz / (sr * bits / 8) if sr > 0 else 0.0
            if sz == 0:
                break
            pos += 8 + sz
    except Exception:
        pass
    return 0.0
