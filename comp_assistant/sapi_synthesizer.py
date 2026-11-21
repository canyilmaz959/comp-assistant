"""Legacy import compatibility; speech output now uses Windows OneCore."""

from .onecore_synthesizer import OneCoreSpeechSynthesizer

# Keep integrations importing the old class name working without invoking SAPI5.
SapiSpeechSynthesizer = OneCoreSpeechSynthesizer

__all__ = ["OneCoreSpeechSynthesizer", "SapiSpeechSynthesizer"]
