"""
Synthesizes short WAV tone files for UI sound effects. No external audio
assets or dependencies -- stdlib `wave` + `array` + `math` only.
"""
from __future__ import annotations
import array
import math
import pathlib
import wave
from typing import Sequence

SAMPLE_RATE = 44100
AMPLITUDE = 0.5  # fraction of full scale -- keeps headroom against clipping
_FADE_SECONDS = 0.01  # linear fade in/out, avoids an audible click at the edges


def generate_tone(path: pathlib.Path, frequencies_hz: Sequence[float], duration_ms: float,
                   sample_rate: int = SAMPLE_RATE, amplitude: float = AMPLITUDE) -> None:
    """
    Write a mono 16-bit PCM WAV file at path: the sum of frequencies_hz
    (a short chord reads as a more distinct "blip" than a single sine tone),
    duration_ms long, faded in/out to avoid clicks.
    """
    n = max(1, int(sample_rate * duration_ms / 1000))
    fade_samples = max(1, min(n // 2, int(sample_rate * _FADE_SECONDS)))
    peak = 2 ** 15 - 1
    samples = array.array('h')

    for i in range(n):
        t = i / sample_rate
        value = sum(math.sin(2 * math.pi * f * t) for f in frequencies_hz) / len(frequencies_hz)
        if i < fade_samples:
            value *= i / fade_samples
        elif i >= n - fade_samples:
            value *= (n - i) / fade_samples
        samples.append(int(max(-1.0, min(1.0, value * amplitude)) * peak))

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(samples.tobytes())


def ensure_tone(path: pathlib.Path, frequencies_hz: Sequence[float], duration_ms: float) -> pathlib.Path:
    """Generate path only if it doesn't already exist; return path either way."""
    if not path.exists():
        generate_tone(path, frequencies_hz, duration_ms)
    return path
