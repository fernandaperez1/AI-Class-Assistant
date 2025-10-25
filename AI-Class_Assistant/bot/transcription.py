"""
Utility module to transcribe Telegram voice notes into text.

This module wraps the workflow shared by the user:
1. Normalize any incoming audio to 16 kHz mono WAV via ffmpeg.
2. Detect the spoken language with faster-whisper (tiny model by default).
3. Select the appropriate Vosk acoustic model (ES/EN) and obtain the transcript.

All heavy lifting lives in the bot service, so the backend only receives text.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

from faster_whisper import WhisperModel
from vosk import KaldiRecognizer, Model

LOGGER = logging.getLogger(__name__)


class TranscriptionError(RuntimeError):
    """Raised when the audio transcription pipeline fails."""


@dataclass
class TranscriptionResult:
    text: str
    language: str
    confidence: float
    model_used: str


class TranscriptionService:
    """
    Encapsulates the workflow to turn arbitrary audio files into plain text using
    faster-whisper (for language detection) and Vosk (for speech-to-text).
    """

    def __init__(
        self,
        es_model_dir: Path,
        en_model_dir: Path,
        whisper_model_name: str = "tiny",
        target_rate: int = 16000,
        whisper_device: str | None = None,
        whisper_compute_type: str | None = None,
    ) -> None:
        self.es_model_dir = Path(es_model_dir)
        self.en_model_dir = Path(en_model_dir)
        self.whisper_model_name = whisper_model_name
        self.target_rate = target_rate
        self.whisper_device = whisper_device or os.getenv("WHISPER_DEVICE", "cpu")
        self.whisper_compute_type = whisper_compute_type or os.getenv(
            "WHISPER_COMPUTE_TYPE", "int8"
        )

        self._vosk_models: Dict[Path, Model] = {}
        self._whisper_model: WhisperModel | None = None

    def transcribe_file(self, audio_path: Path) -> TranscriptionResult:
        """
        Convert `audio_path` into normalized WAV, detect language, and transcribe.
        Returns the textual transcript and metadata.
        """
        if not Path(audio_path).exists():
            raise TranscriptionError(f"Audio file not found: {audio_path}")

        wav_path = self._ensure_wav_16k_mono(Path(audio_path))
        try:
            lang_code, probability = self._detect_language(wav_path)
            normalized_lang = self._normalize_language(lang_code)
            model_dir = self._select_model_path(normalized_lang)
            text = self._transcribe_with_vosk(wav_path, model_dir)

            if not text.strip():
                raise TranscriptionError("No se reconoció audio. Intenta nuevamente.")

            return TranscriptionResult(
                text=text.strip(),
                language=normalized_lang,
                confidence=probability,
                model_used=str(model_dir),
            )
        finally:
            try:
                os.remove(wav_path)
            except OSError:
                pass

    # --- Internal helpers -------------------------------------------------

    def _ensure_wav_16k_mono(self, src_path: Path) -> Path:
        """Use ffmpeg to get a temporary WAV 16k mono s16le file."""
        tmp_file = Path(
            tempfile.NamedTemporaryFile(prefix="bot_wav16k_", suffix=".wav", delete=False).name
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(src_path),
            "-ar",
            str(self.target_rate),
            "-ac",
            "1",
            "-sample_fmt",
            "s16",
            str(tmp_file),
        ]
        try:
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise TranscriptionError(
                "ffmpeg no está disponible para convertir el audio."
            ) from exc
        return tmp_file

    def _detect_language(self, wav_path: Path) -> Tuple[str, float]:
        """Use faster-whisper to identify the spoken language."""
        model = self._get_whisper_model()
        segments, info = model.transcribe(
            str(wav_path),
            task="transcribe",
            beam_size=1,
            vad_filter=True,
        )
        # Consume generator quickly (language metadata is already computed)
        for _ in segments:
            break

        language = info.language or "unknown"
        probability = float(info.language_probability or 0.0)
        LOGGER.debug("Whisper detected language=%s (%.2f)", language, probability)
        return language, probability

    def _transcribe_with_vosk(self, wav_path: Path, model_dir: Path) -> str:
        """Run the Vosk recognizer over the normalized WAV."""
        if not model_dir.is_dir():
            raise TranscriptionError(f"Modelo Vosk no encontrado en {model_dir}")

        vosk_model = self._get_vosk_model(model_dir)

        with wave.open(str(wav_path), "rb") as wav_file:
            if wav_file.getnchannels() != 1 or wav_file.getframerate() != self.target_rate:
                raise TranscriptionError("El WAV debe ser mono a 16 kHz.")

            recognizer = KaldiRecognizer(vosk_model, wav_file.getframerate())
            chunk_size = 4000
            results = []

            while True:
                data = wav_file.readframes(chunk_size)
                if len(data) == 0:
                    break
                if recognizer.AcceptWaveform(data):
                    results.append(json.loads(recognizer.Result()))

            results.append(json.loads(recognizer.FinalResult()))

        text = " ".join(r.get("text", "") for r in results if isinstance(r, dict))
        LOGGER.debug("Vosk transcription result length=%d chars", len(text))
        return text.strip()

    def _select_model_path(self, lang: str) -> Path:
        if lang == "es":
            return self.es_model_dir
        if lang == "en":
            return self.en_model_dir
        LOGGER.info("Idioma %s no soportado explícitamente. Usando modelo ES.", lang)
        return self.es_model_dir

    def _normalize_language(self, lang_code: str) -> str:
        if lang_code.startswith("es"):
            return "es"
        if lang_code.startswith("en"):
            return "en"
        return lang_code or "es"

    def _get_whisper_model(self) -> WhisperModel:
        if self._whisper_model is None:
            LOGGER.info(
                "Loading faster-whisper model '%s' on %s (%s)",
                self.whisper_model_name,
                self.whisper_device,
                self.whisper_compute_type,
            )
            self._whisper_model = WhisperModel(
                self.whisper_model_name,
                device=self.whisper_device,
                compute_type=self.whisper_compute_type,
            )
        return self._whisper_model

    def _get_vosk_model(self, model_dir: Path) -> Model:
        if model_dir not in self._vosk_models:
            LOGGER.info("Loading Vosk model from %s", model_dir)
            self._vosk_models[model_dir] = Model(str(model_dir))
        return self._vosk_models[model_dir]


__all__ = [
    "TranscriptionError",
    "TranscriptionResult",
    "TranscriptionService",
]
