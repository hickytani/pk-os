"""
PK Intelligence Core Interfaces
Defines abstract contracts for audio capture, wake-word detection,
speech-to-text, intent planning, typed tools, and permission auditing.
"""

from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Dict, Any, List, Optional
import dataclasses
import time


class Capability(Enum):
    READ_ONLY = "read_only"
    SYSTEM_CONFIG = "system_config"
    CONSEQUENTIAL = "consequential"


class AudioState(Enum):
    IDLE = auto()
    LISTENING = auto()
    VOICE_DETECTED = auto()
    MUTED = auto()


@dataclasses.dataclass(frozen=True)
class AudioChunk:
    pcm_data: bytes
    sample_rate: int = 16000
    channels: int = 1
    timestamp: float = dataclasses.field(default_factory=time.time)


@dataclasses.dataclass(frozen=True)
class WakeWordResult:
    detected: bool
    wake_word: str = "Hey PK"
    confidence: float = 0.0
    timestamp: float = dataclasses.field(default_factory=time.time)


@dataclasses.dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str = "en"
    duration_ms: float = 0.0
    confidence: float = 1.0


@dataclasses.dataclass(frozen=True)
class ToolResult:
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time_ms: float = 0.0


class AudioCaptureInterface(ABC):
    @abstractmethod
    def start_capture(self) -> None:
        pass

    @abstractmethod
    def stop_capture(self) -> None:
        pass

    @abstractmethod
    def read_chunk(self) -> AudioChunk:
        pass


class WakeWordInterface(ABC):
    @abstractmethod
    def process_chunk(self, chunk: AudioChunk) -> WakeWordResult:
        pass


class SpeechToTextInterface(ABC):
    @abstractmethod
    def transcribe(self, audio: bytes) -> TranscriptionResult:
        pass


class ToolInterface(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def capability(self) -> Capability:
        pass

    @property
    @abstractmethod
    def parameter_schema(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        pass
