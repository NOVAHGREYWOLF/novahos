"""TRANSCRIBER — pluggable speech-to-text (a shared capability). (Agents.)

Provider from env TRANSCRIPTION_PROVIDER: whisper_local (default, free, private), assemblyai,
deepgram. Heavy SDKs import lazily so the app boots without them.
"""
from __future__ import annotations

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


class AssemblyAITranscriber(Transcriber):
    provider = "assemblyai"

    async def transcribe(self, media_path: str) -> str:
        import assemblyai as aai

        aai.settings.api_key = os.environ.get("ASSEMBLYAI_API_KEY", "")
        return aai.Transcriber().transcribe(media_path).text or ""


class DeepgramTranscriber(Transcriber):
    provider = "deepgram"

    async def transcribe(self, media_path: str) -> str:
        from deepgram import DeepgramClient, PrerecordedOptions

        dg = DeepgramClient(os.environ.get("DEEPGRAM_API_KEY", ""))
        with open(media_path, "rb") as f:
            source = {"buffer": f.read()}
        resp = dg.listen.prerecorded.v("1").transcribe_file(
            source, PrerecordedOptions(model="nova-2", smart_format=True))
        return resp["results"]["channels"][0]["alternatives"][0]["transcript"]


_REGISTRY = {"whisper_local": WhisperLocal, "assemblyai": AssemblyAITranscriber, "deepgram": DeepgramTranscriber}


def get_transcriber() -> Transcriber:
    return _REGISTRY.get(os.environ.get("TRANSCRIPTION_PROVIDER", "whisper_local"), WhisperLocal)()
