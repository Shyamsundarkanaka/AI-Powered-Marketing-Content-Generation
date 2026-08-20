"""Voiceover track generation, over a pluggable chain of TTS engines.

`TTS_ENGINES` in .env is an ordered, comma-separated list of engine names. Each
is tried in turn and the first that produces a valid WAV wins; if none does, the
track is written as digital silence of the script's estimated spoken length, so
the video's timing, scene pacing and audio stream are all still correct and the
result is flagged loudly rather than passed off as narration.

With `TTS_ENGINES=elevenlabs,piper,pyttsx3` (the default), the paid ElevenLabs
engine leads, with Piper and then pyttsx3 as free local fallbacks. An engine
signals "not usable" by raising `TTSUnavailable`; anything else it raises is
caught and logged the same way, so a failover always shows up in a run's
warnings — see `generate_voiceover`.
"""
from __future__ import annotations

import logging
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from brand.loader import load_brand
from config import settings

logger = logging.getLogger(__name__)

SAMPLE_WIDTH_BYTES = 2  # 16-bit PCM
CHANNELS = 1
MIN_DURATION_SECONDS = 1.0
SILENCE = "silence"

SILENT_TRACK_WARNING = (
    "No speech was synthesised — the voiceover track is silent. The video's timing "
    "still matches the script, so a real narration WAV of the same length can be "
    "dropped in without re-rendering anything else."
)


class TTSUnavailable(RuntimeError):
    """This engine cannot run here (not installed, not configured, no model file)."""


@dataclass
class VoiceoverResult:
    path: Path
    duration_seconds: float
    engine: str                     # engine name, or "silence"
    spoken_text: str
    warnings: list[str] = field(default_factory=list)
    # Real spoken duration of each script beat, in beat order — empty when the
    # track is silence (no real speech to measure). This is what lets scene
    # timing follow the words actually being spoken beat-by-beat instead of
    # one whole-video average; see `media/movie.scale_scenes_to_beats`.
    beat_durations: list[float] = field(default_factory=list)

    @property
    def is_silent(self) -> bool:
        return self.engine == SILENCE

    def as_dict(self) -> dict[str, Any]:
        return {
            "file_path": str(self.path),
            "duration_seconds": round(self.duration_seconds, 2),
            "engine": self.engine,
            "is_silent": self.is_silent,
            "spoken_text": self.spoken_text,
            "warnings": self.warnings,
            "beat_durations": [round(d, 3) for d in self.beat_durations],
        }


# --- script -> speech text ---------------------------------------------------

def spoken_text_from_script(script: dict[str, Any]) -> str:
    """The narration, joined from the script's beats.

    Only `line` is spoken — `on_screen` is a visual label for the renderer and
    would be nonsense read aloud.
    """
    beats = script.get("beats") or []
    return " ".join(str(beat.get("line", "")).strip() for beat in beats if beat.get("line")).strip()


def estimate_duration(text: str, script: dict[str, Any] | None = None) -> float:
    """Spoken duration in seconds, for sizing the silent fallback track.

    Trusts the script's own estimate when present — `graph/schemas.py` computes
    it from the real word count, so it is a measurement rather than a guess.
    """
    if script and script.get("estimated_duration_seconds"):
        try:
            return max(float(script["estimated_duration_seconds"]), MIN_DURATION_SECONDS)
        except (TypeError, ValueError):
            pass
    words_per_second = float(load_brand().content_rules["script"]["words_per_second"])
    return max(len(text.split()) / words_per_second, MIN_DURATION_SECONDS)


# --- WAV helpers -------------------------------------------------------------

def write_silence(path: Path, duration_seconds: float) -> None:
    """Write a mono 16-bit PCM WAV of pure silence.

    Uses the stdlib `wave` module rather than numpy/moviepy so this works even
    if the render dependencies are missing — a silent track should never be the
    thing that fails a run.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = int(round(duration_seconds * settings.VOICEOVER_SAMPLE_RATE))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(CHANNELS)
        handle.setsampwidth(SAMPLE_WIDTH_BYTES)
        handle.setframerate(settings.VOICEOVER_SAMPLE_RATE)
        handle.writeframes(b"\x00" * (frame_count * CHANNELS * SAMPLE_WIDTH_BYTES))


def write_pcm_wav(path: Path, pcm: bytes, sample_rate: int, channels: int = CHANNELS) -> None:
    """Wrap raw 16-bit PCM bytes in a WAV container.

    Most hosted TTS APIs can return raw PCM; this is the two lines that turn
    that into a file the renderer accepts.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(SAMPLE_WIDTH_BYTES)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm)


def _mp3_bytes_to_wav(mp3: bytes, path: Path, sample_rate: int) -> None:
    """Decode MP3 bytes to a mono WAV at `path`, via the ffmpeg binary
    `imageio_ffmpeg` already bundles for video rendering — no extra install.

    Used for the `elevenlabs` engine: free/starter ElevenLabs tiers can only
    return MP3, not raw PCM (that needs a paid tier), but the rest of the
    pipeline (duration reads, the renderer) expects a plain WAV file.
    """
    import subprocess

    import imageio_ffmpeg

    path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    # Output goes to a real file path, not a pipe: writing to pipe:1 leaves
    # ffmpeg unable to seek back and fill in the WAV header's real data size,
    # so it writes a placeholder (0x7FFFFFFF frames) that every downstream
    # reader trusts as if it were the truth.
    result = subprocess.run(
        [
            ffmpeg, "-y", "-f", "mp3", "-i", "pipe:0",
            "-ar", str(sample_rate), "-ac", str(CHANNELS), str(path),
        ],
        input=mp3,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0 or not path.exists() or path.stat().st_size == 0:
        raise TTSUnavailable(f"ffmpeg could not decode ElevenLabs' MP3: {result.stderr.decode(errors='replace')[-300:]}")


def wav_duration_seconds(path: Path) -> float:
    """Duration straight from the WAV header. Raises if the file is unusable."""
    with wave.open(str(path), "rb") as handle:
        frames, rate = handle.getnframes(), handle.getframerate()
    if not frames or not rate:
        raise TTSUnavailable(f"{path.name} contains no audio frames")
    return frames / float(rate)


def _concat_wavs(paths: list[Path], output_path: Path) -> None:
    """Join beat-level WAV clips, in order, into one voiceover track.

    All clips come from the same engine call in the same run, so they share
    one format (channels/sample width/rate); this just streams frames through
    rather than re-encoding.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(paths[0]), "rb") as first:
        params = first.getparams()
    with wave.open(str(output_path), "wb") as out:
        out.setparams(params)
        for path in paths:
            with wave.open(str(path), "rb") as segment:
                out.writeframes(segment.readframes(segment.getnframes()))


# --- engines -----------------------------------------------------------------

def _synthesize_piper(text: str, path: Path) -> None:
    """Local/offline neural TTS. No API key, no network call at synthesis time.

    Needs `PIPER_MODEL_PATH` pointed at a downloaded `.onnx` voice (with its
    `.onnx.json` sidecar alongside) and `pip install piper-tts`.
    """
    if not settings.PIPER_MODEL_PATH:
        raise TTSUnavailable("PIPER_MODEL_PATH is not set")
    model_path = Path(settings.PIPER_MODEL_PATH)
    if not model_path.is_file():
        raise TTSUnavailable(f"PIPER_MODEL_PATH points at {model_path}, which does not exist")
    if not model_path.with_suffix(model_path.suffix + ".json").is_file():
        raise TTSUnavailable(f"{model_path.name} has no .onnx.json config sidecar next to it")

    try:
        from piper import PiperVoice
    except ImportError as exc:
        raise TTSUnavailable("piper-tts is not installed (pip install piper-tts)") from exc

    voice = PiperVoice.load(str(model_path))
    with wave.open(str(path), "wb") as handle:
        voice.synthesize_wav(text, handle)


def _synthesize_elevenlabs(text: str, path: Path) -> None:
    """Hosted, paid neural TTS. Needs `ELEVENLABS_API_KEY` (and optionally
    `ELEVENLABS_VOICE_ID`) in .env, plus `pip install elevenlabs`.
    """
    if not settings.ELEVENLABS_API_KEY:
        raise TTSUnavailable("ELEVENLABS_API_KEY is not set")

    try:
        from elevenlabs.client import ElevenLabs
    except ImportError as exc:
        raise TTSUnavailable("elevenlabs is not installed (pip install elevenlabs)") from exc

    client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
    audio = client.text_to_speech.convert(
        voice_id=settings.ELEVENLABS_VOICE_ID,
        model_id="eleven_turbo_v2_5",
        text=text,
        # MP3, not PCM: raw PCM output is a Pro-tier-and-above feature, while
        # MP3 is available on every plan including free. Decoded to WAV below.
        output_format="mp3_44100_128",
    )
    _mp3_bytes_to_wav(b"".join(audio), path, sample_rate=settings.VOICEOVER_SAMPLE_RATE)


def _synthesize_pyttsx3(text: str, path: Path) -> None:
    """Whatever voices the operating system already has. Quality varies a lot."""
    try:
        import pyttsx3
    except ImportError as exc:
        raise TTSUnavailable("pyttsx3 is not installed (pip install pyttsx3)") from exc

    engine = pyttsx3.init()
    try:
        engine.save_to_file(text, str(path))
        engine.runAndWait()
    finally:
        engine.stop()


# name -> synthesize(text, path). The function must leave a valid WAV at `path`
# or raise; it does not need to report the duration, which is read back from
# the file so the timeline is driven by real audio rather than a claim about it.
ENGINES: dict[str, Callable[[str, Path], None]] = {
    "elevenlabs": _synthesize_elevenlabs,
    "piper": _synthesize_piper,
    "pyttsx3": _synthesize_pyttsx3,
}


def configured_engines() -> list[str]:
    """The engine chain from settings, filtered to ones that actually exist."""
    chain: list[str] = []
    for name in settings.TTS_ENGINES:
        if name in ENGINES:
            chain.append(name)
        else:
            logger.warning(
                "TTS_ENGINES lists unknown engine %r; known engines are: %s",
                name, ", ".join(sorted(ENGINES)),
            )
    return chain


def _synthesize_beats(name: str, lines: list[str], scratch_dir: Path) -> tuple[list[Path], list[float]]:
    """Synthesize each script beat's line as its own clip with one engine.

    Each beat gets its own file so its real spoken duration is measured
    individually, rather than only the whole script's total being known. That
    per-beat duration is what lets a scene's on-screen time match the words
    actually being spoken during it (`media/movie.scale_scenes_to_beats`)
    instead of everyone sharing one whole-video average stretch factor, which
    is what let scenes drift out of sync with narration mid-video.
    """
    paths: list[Path] = []
    durations: list[float] = []
    for index, line in enumerate(lines):
        beat_path = scratch_dir / f"beat_{index}.wav"
        ENGINES[name](line, beat_path)
        if not beat_path.exists() or beat_path.stat().st_size == 0:
            raise TTSUnavailable(f"{name} produced no output for beat {index}")
        durations.append(wav_duration_seconds(beat_path))
        paths.append(beat_path)
    return paths, durations


def generate_voiceover(script: dict[str, Any], output_path: Path) -> VoiceoverResult:
    """Produce the voiceover WAV for a script.

    Always returns a playable file. `engine` records what produced it, and
    `is_silent` flows through to the review UI so a silent track is visible to
    the person approving the video rather than buried in metadata.

    Synthesizes one clip per script beat (falling back to the next engine if
    any beat fails) and concatenates them, so `beat_durations` reports each
    beat's real measured length rather than a single total.
    """
    import tempfile

    output_path = Path(output_path)
    beats = script.get("beats") or []
    lines = [str(beat.get("line", "")).strip() for beat in beats if beat.get("line")]
    text = spoken_text_from_script(script)
    warnings: list[str] = []

    if not lines:
        warnings.append("The script contained no spoken lines.")
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output_path.parent) as tmp:
            scratch_dir = Path(tmp)
            for name in configured_engines():
                try:
                    beat_paths, beat_durations = _synthesize_beats(name, lines, scratch_dir)
                    _concat_wavs(beat_paths, output_path)
                except TTSUnavailable as exc:
                    logger.info("TTS engine %s unavailable: %s", name, exc)
                    warnings.append(f"{name}: {exc}")
                except Exception as exc:  # noqa: BLE001 — TTS backends fail creatively
                    logger.warning("TTS engine %s failed: %s", name, exc)
                    warnings.append(f"{name} failed: {type(exc).__name__}: {exc}")
                else:
                    duration = sum(beat_durations)
                    logger.info(
                        "Voiceover: %.1fs from %s -> %s (%d beats)",
                        duration, name, output_path, len(beat_durations),
                    )
                    return VoiceoverResult(output_path, duration, name, text, warnings, beat_durations)

    duration = estimate_duration(text, script)
    write_silence(output_path, duration)
    warnings.append(SILENT_TRACK_WARNING)
    logger.warning("Voiceover: %.1fs of silence -> %s", duration, output_path)
    return VoiceoverResult(output_path, duration, SILENCE, text, warnings)


def main() -> None:
    """Standalone check: `python -m media.voice --text "hello there"`."""
    import argparse

    from config.logging_setup import configure_logging

    parser = argparse.ArgumentParser(description="Generate a voiceover track.")
    parser.add_argument("--text", default="Built for the ride to everywhere.")
    parser.add_argument("--out", type=Path, default=Path("voiceover.wav"))
    args = parser.parse_args()

    configure_logging()
    script = {"beats": [{"line": args.text}]}
    result = generate_voiceover(script, args.out)
    print(f"{result.engine}: {result.duration_seconds:.1f}s -> {result.path}")
    for warning in result.warnings:
        print(f"  warning: {warning}")


if __name__ == "__main__":
    main()
