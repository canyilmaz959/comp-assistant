from __future__ import annotations

import asyncio
from threading import Event, Thread
import time
import unittest
from types import SimpleNamespace

from comp_assistant.lifecycle import RuntimeState
from comp_assistant.onecore_synthesizer import (
    OneCoreSpeechSynthesizer,
    _is_turkish_language,
    list_onecore_voices,
)
from comp_assistant.runtime import AssistantRuntime
from comp_assistant.voice import AudioService, MockSpeechRecognizer, MockWakeWordDetector


class FakeVoice:
    def __init__(self, display_name, language, voice_id):
        self.display_name = display_name
        self.language = language
        self.id = voice_id


class FakeStream:
    content_type = "audio/wav"

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeSource:
    def __init__(self, stream):
        self.stream = stream
        self.closed = False

    def close(self):
        self.closed = True


class FakeOptions:
    speaking_rate = 1.0
    audio_volume = 1.0


class FakeSpeechSynthesizer:
    default_voices = [
        FakeVoice("Microsoft Zira", "en-US", "voice-en"),
        FakeVoice("Microsoft Hedda", "de-DE", "voice-de"),
        FakeVoice("Turkish Voice", "tr-TR", "voice-tr"),
        FakeVoice("Microsoft Tolga", "tr-TR", "voice-tolga"),
    ]
    all_voices = list(default_voices)
    instances = []
    synthesis_error = None

    def __init__(self):
        self.voice = None
        self.options = FakeOptions()
        self.options.speaking_rate = 1.0
        self.options.audio_volume = 1.0
        self.texts = []
        self.closed = False
        type(self).instances.append(self)

    async def synthesize_text_to_stream_async(self, text):
        self.texts.append(text)
        await asyncio.sleep(0)
        if type(self).synthesis_error:
            raise type(self).synthesis_error
        return FakeStream()

    def close(self):
        self.closed = True


class FakeMediaPlayer:
    instances = []
    active_count = 0
    maximum_active = 0
    playback_seconds = 0.02
    fail_playback = False

    def __init__(self):
        self.audio_category = None
        self.source = None
        self._handler = None
        self._failure_handler = None
        self._loop = asyncio.get_running_loop()
        self.closed = False
        self.paused = False
        type(self).instances.append(self)

    def add_media_ended(self, handler):
        self._handler = handler
        return handler

    def remove_media_ended(self, token):
        if token is self._handler:
            self._handler = None

    def add_media_failed(self, handler):
        self._failure_handler = handler
        return handler

    def remove_media_failed(self, token):
        if token is self._failure_handler:
            self._failure_handler = None

    def play(self):
        type(self).active_count += 1
        type(self).maximum_active = max(type(self).maximum_active, type(self).active_count)
        if type(self).fail_playback:
            self._loop.call_soon(self._fail)
            return
        self._loop.call_later(type(self).playback_seconds, self._finish)

    def _fail(self):
        type(self).active_count -= 1
        if self._failure_handler:
            self._failure_handler(self, SimpleNamespace(error="mock output-device error"))

    def _finish(self):
        if type(self).active_count:
            type(self).active_count -= 1
        if self._handler:
            self._handler(self, None)

    def pause(self):
        if not self.paused and type(self).active_count:
            type(self).active_count -= 1
        self.paused = True

    def close(self):
        self.closed = True


class FakeMediaSource:
    @staticmethod
    def create_from_stream(stream, _content_type):
        return FakeSource(stream)


class FakeOneCoreApi:
    speech_synthesizer = FakeSpeechSynthesizer
    media_source = FakeMediaSource
    media_player = FakeMediaPlayer
    media_player_audio_category = SimpleNamespace(SPEECH="speech")


class FakeMicrophone:
    def __init__(self):
        self.is_capturing = False
        self.start_count = 0

    def start(self):
        self.is_capturing = True
        self.start_count += 1

    def stop(self):
        self.is_capturing = False

    def close(self):
        self.is_capturing = False


class OneCoreSpeechSynthesizerTests(unittest.TestCase):
    def setUp(self):
        FakeSpeechSynthesizer.instances.clear()
        FakeSpeechSynthesizer.all_voices = list(FakeSpeechSynthesizer.default_voices)
        FakeSpeechSynthesizer.synthesis_error = None
        FakeMediaPlayer.instances.clear()
        FakeMediaPlayer.active_count = 0
        FakeMediaPlayer.maximum_active = 0
        FakeMediaPlayer.playback_seconds = 0.02
        FakeMediaPlayer.fail_playback = False

    def make_synth(self, **options):
        synth = OneCoreSpeechSynthesizer(winrt_api=FakeOneCoreApi, **options)
        synth.open()
        self.assertTrue(synth._ready.wait(1))
        return synth

    def wait_for(self, predicate, timeout=2.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.005)
        self.fail("Condition was not reached before timeout")

    def test_enumerates_voice_display_language_and_id(self):
        details = list_onecore_voices(FakeOneCoreApi)
        self.assertEqual(len(details), 4)
        self.assertEqual(
            (details[-1].display_name, details[-1].language, details[-1].voice_id),
            ("Microsoft Tolga", "tr-TR", "voice-tolga"),
        )

    def test_turkish_voice_detection_uses_bcp47_language(self):
        self.assertTrue(_is_turkish_language("tr-TR"))
        self.assertTrue(_is_turkish_language("tr"))
        self.assertFalse(_is_turkish_language("en-US"))
        self.assertFalse(_is_turkish_language("de-DE"))

    def test_prefers_tolga_among_turkish_voices(self):
        synth = self.make_synth()
        try:
            self.assertEqual(FakeSpeechSynthesizer.instances[-1].voice.id, "voice-tolga")
            self.assertEqual(synth.available_voices[-1], ("voice-tolga", "Microsoft Tolga"))
        finally:
            synth.close()

    def test_configured_turkish_voice_is_honored(self):
        synth = self.make_synth(voice_id="voice-tr")
        try:
            self.assertEqual(FakeSpeechSynthesizer.instances[-1].voice.id, "voice-tr")
        finally:
            synth.close()

    def test_configured_non_turkish_voice_is_rejected(self):
        synth = OneCoreSpeechSynthesizer(
            winrt_api=FakeOneCoreApi,
            voice_id="voice-en",
        )
        with self.assertLogs("comp_assistant.onecore_synthesizer", level="ERROR"):
            synth.open()
            self.assertTrue(synth._ready.wait(1))
            self.wait_for(lambda: not synth.worker_alive)
        try:
            self.assertIn("ses Türkçe (tr-TR) değil", synth.last_error)
            self.assertEqual(FakeSpeechSynthesizer.instances, [])
        finally:
            synth.close()

    def test_missing_turkish_voice_reports_error_without_language_fallback(self):
        FakeSpeechSynthesizer.all_voices = [
            FakeVoice("Microsoft Zira", "en-US", "voice-en"),
            FakeVoice("Microsoft Hedda", "de-DE", "voice-de"),
        ]
        synth = OneCoreSpeechSynthesizer(winrt_api=FakeOneCoreApi)
        with self.assertLogs("comp_assistant.onecore_synthesizer", level="ERROR"):
            synth.open()
            self.assertTrue(synth._ready.wait(1))
            self.wait_for(lambda: not synth.worker_alive)
        try:
            self.assertIn("Türkçe (tr-TR) ses bulunamadı", synth.last_error)
            self.assertEqual(FakeSpeechSynthesizer.instances, [])
        finally:
            synth.close()
        FakeSpeechSynthesizer.all_voices = [
            FakeVoice("Microsoft Zira", "en-US", "voice-en"),
            FakeVoice("Microsoft Hedda", "de-DE", "voice-de"),
            FakeVoice("Turkish Voice", "tr-TR", "voice-tr"),
            FakeVoice("Microsoft Tolga", "tr-TR", "voice-tolga"),
        ]

    def test_onecore_enumeration_failure_is_reported_and_worker_terminates(self):
        class UnavailableSpeechApi:
            @property
            def all_voices(self):
                raise OSError("Internal Speech Error")

        api = SimpleNamespace(speech_synthesizer=UnavailableSpeechApi)
        synth = OneCoreSpeechSynthesizer(winrt_api=api)
        with self.assertLogs("comp_assistant.onecore_synthesizer", level="ERROR"):
            synth.open()
            self.assertTrue(synth._ready.wait(1))
            self.wait_for(lambda: not synth.worker_alive)
        try:
            self.assertIn("AllVoices envanteri okunamadı", synth.last_error)
        finally:
            synth.close()

    def test_synthesizes_and_releases_native_stream_and_player(self):
        synth = self.make_synth(rate=205, volume=0.6)
        try:
            synth.speak("Merhaba, Türkçe konuşuyorum.", Event())
            instance = FakeSpeechSynthesizer.instances[-1]
            self.assertEqual(instance.texts, ["Merhaba, Türkçe konuşuyorum."])
            self.assertEqual(instance.options.speaking_rate, 205 / 180)
            self.assertEqual(instance.options.audio_volume, 0.6)
            self.assertTrue(FakeMediaPlayer.instances[0].closed)
        finally:
            synth.close()
        self.assertTrue(instance.closed)
        self.assertFalse(synth.worker_alive)

    def test_synthesis_failure_is_reported_and_worker_remains_available(self):
        FakeSpeechSynthesizer.synthesis_error = OSError("mock synthesis failure")
        synth = self.make_synth()
        try:
            with self.assertLogs("comp_assistant.onecore_synthesizer", level="ERROR"):
                synth.speak("Bu yanıt üretilemedi", Event())
            self.assertIn("synthesis or playback failed", synth.last_error)
            self.assertTrue(synth.worker_alive)
        finally:
            synth.close()

    def test_playback_failure_is_reported_and_native_objects_are_released(self):
        FakeMediaPlayer.fail_playback = True
        synth = self.make_synth()
        try:
            with self.assertLogs("comp_assistant.onecore_synthesizer", level="ERROR"):
                synth.speak("Ses çıkışı hata veriyor", Event())
            self.assertIn("mock output-device error", synth.last_error)
            self.assertTrue(FakeMediaPlayer.instances[0].closed)
            self.assertTrue(synth.worker_alive)
        finally:
            synth.close()

    def test_queue_is_sequential_without_overlapping_playback(self):
        synth = self.make_synth()
        first = Thread(target=synth.speak, args=("birinci", Event()))
        second = Thread(target=synth.speak, args=("ikinci", Event()))
        try:
            first.start()
            self.wait_for(lambda: FakeMediaPlayer.active_count == 1)
            second.start()
            self.wait_for(lambda: synth._queue.qsize() == 1)
            first.join(2)
            second.join(2)
            self.assertFalse(first.is_alive())
            self.assertFalse(second.is_alive())
            self.assertEqual(FakeSpeechSynthesizer.instances[-1].texts, ["birinci", "ikinci"])
            self.assertEqual(FakeMediaPlayer.maximum_active, 1)
        finally:
            synth.close()

    def test_clear_queue_cancels_waiting_jobs(self):
        synth = self.make_synth()
        first = Thread(target=synth.speak, args=("aktif", Event()))
        second = Thread(target=synth.speak, args=("bekleyen", Event()))
        try:
            first.start()
            self.wait_for(lambda: FakeMediaPlayer.active_count == 1)
            second.start()
            self.wait_for(lambda: synth._queue.qsize() == 1)
            synth.clear_queue()
            second.join(1)
            first.join(2)
            self.assertFalse(second.is_alive())
            self.assertFalse(first.is_alive())
            self.assertEqual(FakeSpeechSynthesizer.instances[-1].texts, ["aktif"])
        finally:
            synth.close()

    def test_stop_playback_cancels_active_audio(self):
        synth = self.make_synth()
        speaking = Thread(target=synth.speak, args=("uzun yanıt", Event()))
        try:
            speaking.start()
            self.wait_for(lambda: FakeMediaPlayer.active_count == 1)
            synth.stop_playback()
            speaking.join(1)
            self.assertFalse(speaking.is_alive())
            self.assertTrue(FakeMediaPlayer.instances[0].paused)
            self.assertTrue(FakeMediaPlayer.instances[0].closed)
        finally:
            synth.close()

    def test_shutdown_is_idempotent_and_leaves_no_worker(self):
        synth = self.make_synth()
        synth.close()
        synth.close()
        self.assertFalse(synth.worker_alive)
        self.assertTrue(FakeSpeechSynthesizer.instances[-1].closed)

    def test_runtime_pause_stops_playback_and_resume_opens_one_fresh_worker(self):
        FakeMediaPlayer.playback_seconds = 0.25
        synth = OneCoreSpeechSynthesizer(winrt_api=FakeOneCoreApi)
        microphone = FakeMicrophone()
        detector = MockWakeWordDetector()
        recognizer = MockSpeechRecognizer()
        service = AudioService(
            detector,
            recognizer,
            synth,
            command_handler=lambda text: f"Yanıt: {text}",
        )
        runtime = AssistantRuntime(1, audio_service=service, microphone_manager=microphone)
        try:
            recognizer.submit("komut")
            detector.trigger()
            self.wait_for(lambda: len(FakeMediaPlayer.instances) == 1)
            runtime.pause()
            self.assertEqual(runtime.state, RuntimeState.PAUSED)
            self.assertFalse(microphone.is_capturing)
            starts_before_resume = microphone.start_count
            runtime.resume()
            self.assertEqual(runtime.state, RuntimeState.STANDBY)
            self.assertEqual(microphone.start_count, starts_before_resume)
            recognizer.submit("ikinci komut")
            detector.trigger()
            self.wait_for(lambda: len(FakeSpeechSynthesizer.instances) == 2)
            self.wait_for(lambda: FakeSpeechSynthesizer.instances[-1].texts == ["Yanıt: ikinci komut"])
        finally:
            runtime.shutdown()
        self.assertFalse(service.worker_alive)
        self.assertFalse(synth.worker_alive)
        self.assertFalse(microphone.is_capturing)


if __name__ == "__main__":
    unittest.main()
