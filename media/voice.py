"""Voiceover track generation.

No TTS provider is wired up, so the default output is **digital silence of
exactly the script's estimated spoken duration**. That is a deliberate choice
rather than a stub: the video's timing, scene pacing and audio stream are all
correct, and dropping in a real narration WAV of the same length later changes
nothing else in the pipeline.

If `ENABLE_TTS` is set and `pyttsx3` happens to be installed, a real track is
attempted first and silence is the fallback. The returned metadata always says
which one you got.
"""
from __future__ import annotations

import logging
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from config.settings import ENABLE_TTS, VOICEOVER_SAMPLE_RATE
from brand.loader import load_brand

logger = logging.getLogger(__name__)

SAMPLE_WIDTH_BYTES = 2  # 16-bit PCM
CHANNELS = 1
MIN_DURATION_SECONDS = 1.0


@dataclass
class VoiceoverResult:
    path: Path
    duration_seconds: float
    kind: str                       # "silence" | "tts"
    spoken_text: str
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "file_path": str(self.path),
            "duration_seconds": round(self.duration_seconds, 2),
            "kind": self.kind,
            "spoken_text": self.spoken_text,
            "warnings": self.warnings,
        }


def spoken_text_from_script(script: dict[str, Any]) -> str:
    """The narration, joined from the script's beats.

    Only `line` is spoken — `on_screen` is a visual label for the renderer and
    would be nonsense read aloud.
    """
    beats = script.get("beats") or []
    return " ".join(str(beat.get("line", "")).strip() for beat in beats if beat.get("line")).strip()


def estimate_duration(text: str, script: dict[str, Any] | None = None) -> float:
    """Spoken duration in seconds.

    Trusts the script's own estimate when present (the agent was given the
    words-per-second budget and wrote to it); otherwise derives it from the
    brand's speaking rate.
    """
    if script and script.get("estimated_duration_seconds"):
        try:
            return max(float(script["estimated_duration_seconds"]), MIN_DURATION_SECONDS)
        except (TypeError, ValueError):
            pass
    words_per_second = load_brand().content_rules["script"]["words_per_second"]
    return max(len(text.split()) / float(words_per_second), MIN_DURATION_SECONDS)


def write_silence(path: Path, duration_seconds: float) -> None:
    """Write a mono 16-bit PCM WAV of pure silence.

    Uses the stdlib `wave` module rather than numpy/moviepy so this works even
    if the render dependencies are missing — a silent track should never be the
    thing that fails a run.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = int(round(duration_seconds * VOICEOVER_SAMPLE_RATE))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(CHANNELS)
        handle.setsampwidth(SAMPLE_WIDTH_BYTES)
        handle.setframerate(VOICEOVER_SAMPLE_RATE)
        handle.writeframes(b"\x00" * (frame_count * CHANNELS * SAMPLE_WIDTH_BYTES))


def _try_tts(text: str, path: Path) -> Optional[float]:
    """Attempt offline TTS. Returns the produced duration, or None on any failure."""
    try:
        import pyttsx3  # noqa: PLC0415 — optional dependency, imported only when enabled
    except ImportError:
        logger.info("ENABLE_TTS is set but pyttsx3 is not installed; using silence.")
        return None

    try:
        engine = pyttsx3.init()
        engine.save_to_file(text, str(path))
        engine.runAndWait()
        engine.stop()
        if not path.exists() or path.stat().st_size == 0:
            return None
        with wave.open(str(path), "rb") as handle:
            return handle.getnframes() / float(handle.getframerate())
    except Exception as exc:  # noqa: BLE001 — TTS backends fail in many creative ways
        logger.warning("TTS failed (%s); falling back to silence.", exc)
        return None


def generate_voiceover(script: dict[str, Any], output_path: Path) -> VoiceoverResult:
    """Produce the voiceover WAV for a script.

    Always returns a playable file. `kind` records whether it carries narration
    or silence, and that flows through to the review UI.
    """
    output_path = Path(output_path)
    text = spoken_text_from_script(script)
    duration = estimate_duration(text, script)
    warnings: list[str] = []

    if ENABLE_TTS and text:
        tts_duration = _try_tts(text, output_path)
        if tts_duration:
            logger.info("Voiceover: %.1fs of synthesized speech -> %s", tts_duration, output_path)
            return VoiceoverResult(output_path, tts_duration, "tts", text)
        warnings.append("TTS unavailable or failed; wrote a silent track instead.")

    write_silence(output_path, duration)
    warnings.append(
        "Silent track: no TTS provider configured. Video timing matches the script's "
        "estimated narration length, so a real WAV of the same duration can be dropped "
        "in without touching anything else."
    )
    logger.info("Voiceover: %.1fs of silence -> %s", duration, output_path)
    return VoiceoverResult(output_path, duration, "silence", text, warnings)


def main() -> None:
    """Standalone check: `python -m media.voice --seconds 12 --out out.wav`."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate a voiceover track.")
    parser.add_argument("--seconds", type=float, default=28.0)
    parser.add_argument("--out", type=Path, default=Path("voiceover.wav"))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    result = generate_voiceover({"estimated_duration_seconds": args.seconds, "beats": []}, args.out)
    print(f"{result.kind}: {result.duration_seconds:.1f}s -> {result.path}")


if __name__ == "__main__":
    main()
