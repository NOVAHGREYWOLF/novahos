"""TRANSCRIBER — pluggable speech-to-text (a shared capability). (Agents.)

Provider from env TRANSCRIPTION_PROVIDER: whisper_local (default, free, private), assemblyai,
deepgram. Heavy SDKs import lazily so the app boots without them.
"""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod


class Transcriber(ABC):
    provider: str = "base"

    @abstractmethod
    async def transcribe(self, media_path: str) -> str:
        raise NotImplementedError


class WhisperLocal(Transcriber):
    provider = "whisper_local"

    async def transcribe(self, media_path: str) -> str:
        from faster_whisper import WhisperModel

        model = WhisperModel(os.environ.get("WHISPER_MODEL", "base"), device="auto", compute_type="auto")
        segments, _info = model.transcribe(media_path)
        return " ".join(seg.text.strip() for seg in segments).strip()


async def _meter_audio(provider: str, seconds: float, rate_env: str, default_per_hour: float) -> None:
    """Account for a PAID transcription call, billed per hour of audio.

    Both cloud providers were dark (audit P0): real money, no ai_usage row, and no entry
    in any cost model. They are billed by DURATION, not tokens, so the duration each API
    already returns is the billable quantity — recorded in tokens_out so the volume stays
    visible even if the rate is later corrected.

    The per-hour rate is the published list price and is env-overridable; confirm it
    against the actual plan (same pattern as VOYAGE_PRICE_PER_MTOK / RESEND_PRICE_PER_EMAIL).
    Never raises: metering must not lose a transcript that was already paid for."""
    try:
        secs = max(0.0, float(seconds or 0.0))
        try:
            per_hour = float(os.environ.get(rate_env) or default_per_hour)
        except (TypeError, ValueError):
            per_hour = default_per_hour
        from ...llm import emit_usage
        await emit_usage(task="transcribe", model=provider,
                         tokens_out=int(secs), cost_usd=(secs / 3600.0) * per_hour)
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).warning(
            "[transcriber] metering failed for %s — this spend is NOT recorded",
            provider, exc_info=True)


class AssemblyAITranscriber(Transcriber):
    provider = "assemblyai"

    async def transcribe(self, media_path: str) -> str:
        import assemblyai as aai

        aai.settings.api_key = os.environ.get("ASSEMBLYAI_API_KEY", "")
        tr = aai.Transcriber().transcribe(media_path)
        # audio_duration is seconds; it is what AssemblyAI bills on.
        await _meter_audio("assemblyai", getattr(tr, "audio_duration", 0) or 0,
                           "ASSEMBLYAI_PRICE_PER_HOUR", 0.27)
        return tr.text or ""


class DeepgramTranscriber(Transcriber):
    provider = "deepgram"

    async def transcribe(self, media_path: str) -> str:
        from deepgram import DeepgramClient, PrerecordedOptions

        dg = DeepgramClient(os.environ.get("DEEPGRAM_API_KEY", ""))
        with open(media_path, "rb") as f:
            source = {"buffer": f.read()}
        resp = dg.listen.prerecorded.v("1").transcribe_file(
            source, PrerecordedOptions(model="nova-2", smart_format=True))
        # Deepgram is ALSO paid and was ALSO dark (the audit only caught AssemblyAI).
        # metadata.duration is seconds of audio, which is what it bills on.
        try:
            _dur = (resp["metadata"] or {}).get("duration", 0) or 0
        except Exception:  # noqa: BLE001 — shape drift must not lose the transcript
            _dur = 0
        await _meter_audio("deepgram:nova-2", _dur, "DEEPGRAM_PRICE_PER_HOUR", 0.258)
        return resp["results"]["channels"][0]["alternatives"][0]["transcript"]


_REGISTRY = {"whisper_local": WhisperLocal, "assemblyai": AssemblyAITranscriber, "deepgram": DeepgramTranscriber}


def get_transcriber() -> Transcriber:
    return _REGISTRY.get(os.environ.get("TRANSCRIPTION_PROVIDER", "whisper_local"), WhisperLocal)()
