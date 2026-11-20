from __future__ import annotations

import json
from pathlib import Path
import struct
import tempfile
from threading import Event, Thread
import time
import unittest
from queue import Queue, Empty

from comp_assistant.lifecycle import RuntimeState
from comp_assistant.microphone import AudioChunk
from comp_assistant.runtime import AssistantRuntime
from comp_assistant.voice import AudioService, MockSpeechSynthesizer, MockWakeWordDetector
from comp_assistant.vosk_recognizer import VoskModelError, VoskSpeechRecognizer


class FakeMicrophone:
    sample_rate = 16_000

    def __init__(self):
        self.frames = Queue()
        self.dropped_frames = 0
        self.is_capturing = False
        self.has_open_stream = False
        self.start_count = self.stop_count = self.close_count = 0

    def start(self):
        self.start_count += 1
        self.is_capturing = self.has_open_stream = True

    def stop(self):
        self.stop_count += 1
        self.is_capturing = self.has_open_stream = False
        while True:
            try:
                self.frames.get_nowait()
            except Empty:
                break

    def close(self):
        self.close_count += 1
        self.stop()

    def read_frame(self, timeout=None):
        try:
            return self.frames.get(timeout=timeout)
        except Empty as error:
            raise TimeoutError from error

    def submit(self, samples=(100, -100)):
        raw = struct.pack("<" + "h" * len(samples), *samples)
        self.frames.put(AudioChunk(raw, len(samples)))


class FakeKaldiRecognizer:
    def __init__(self, model, sample_rate, accepted):
        self.model = model
        self.sample_rate = sample_rate
        self.accepted = accepted
        self.audio = []

    def AcceptWaveform(self, data):
        self.audio.append(data)
        return self.accepted.pop(0) if self.accepted else False

    def Result(self):
        return json.dumps({"text": "hei comp"})

    def PartialResult(self):
        return json.dumps({"partial": "hei"})

    def FinalResult(self):
        return json.dumps({"text": "son"})


class FakeVosk:
    def __init__(self, accepted=(False, True)):
        self.paths = []
        self.instances = []
        self.accepted = list(accepted)

    def Model(self, path):
        self.paths.append(path)
        return object()

    def KaldiRecognizer(self, model, sample_rate):
        result = FakeKaldiRecognizer(model, sample_rate, self.accepted)
        self.instances.append(result)
        return result


class VoskRecognizerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.model_dir = Path(self.temp.name) / "tr-model"
        self.model_dir.mkdir()
        self.mic = FakeMicrophone()
        self.vosk = FakeVosk()
        self.partials = []
        self.recognizer = VoskSpeechRecognizer(
            self.mic,
            self.model_dir,
            vosk_module=self.vosk,
            on_partial_result=self.partials.append,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_loads_configured_model_and_processes_partial_then_final_audio(self):
        self.recognizer.open()
        self.mic.submit()
        self.mic.submit((200, -200))
        result = self.recognizer.recognize(Event())

        self.assertEqual(self.vosk.paths, [str(self.model_dir)])
        self.assertEqual(self.vosk.instances[0].sample_rate, 16_000)
        self.assertEqual(self.vosk.instances[0].audio, [struct.pack("<hh", 100, -100), struct.pack("<hh", 200, -200)])
        self.assertEqual(self.partials, ["hei"])
        self.assertEqual(result, "hei comp")

    def test_missing_model_is_clear_and_does_not_load(self):
        missing = VoskSpeechRecognizer(self.mic, self.model_dir / "missing", vosk_module=self.vosk)
        missing.open()
        self.mic.submit()
        with self.assertRaisesRegex(VoskModelError, "Türkçe Vosk modeli bulunamadı"):
            missing.recognize(Event())
        self.assertEqual(self.vosk.paths, [])

    def test_audio_service_delivers_completed_text_only(self):
        self.recognizer.open()
        handled = []
        states = []
        detector = MockWakeWordDetector()
        service = AudioService(
            detector,
            self.recognizer,
            MockSpeechSynthesizer(),
            command_handler=handled.append,
            on_state_change=states.append,
        )
        service.start()
        try:
            detector.trigger()
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline and states.count(RuntimeState.ACTIVE) == 0:
                time.sleep(0.005)
            self.mic.submit()
            self.mic.submit()
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline and handled != ["hei comp"]:
                time.sleep(0.005)
            self.assertEqual(self.partials, ["hei"])
            self.assertEqual(handled, ["hei comp"])
        finally:
            service.shutdown()

    def test_pause_stops_worker_and_capture_then_resume_creates_fresh_session(self):
        detector = MockWakeWordDetector()
        service = AudioService(detector, self.recognizer, MockSpeechSynthesizer())
        runtime = AssistantRuntime(1, audio_service=service, microphone_manager=self.mic)
        try:
            detector.trigger()
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline and not self.mic.is_capturing:
                time.sleep(0.005)
            self.assertTrue(self.mic.is_capturing)
            self.mic.submit()
            self.assertTrue(service.worker_alive)
            runtime.pause()
            self.assertEqual(runtime.state, RuntimeState.PAUSED)
            self.assertFalse(self.mic.is_capturing)
            self.assertFalse(service.worker_alive)
            self.assertFalse(self.recognizer.is_open)

            runtime.resume()
            self.assertTrue(service.worker_alive)
            detector.trigger()
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline and not self.mic.is_capturing:
                time.sleep(0.005)
            self.mic.submit()
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline and len(self.vosk.instances) < 2:
                time.sleep(0.005)
            self.assertGreaterEqual(len(self.vosk.instances), 2)
        finally:
            runtime.shutdown()
        self.assertEqual(runtime.state, RuntimeState.STOPPED)
        self.assertFalse(service.worker_alive)
        self.assertFalse(self.mic.is_capturing)
        self.assertFalse(self.mic.has_open_stream)

    def test_repeated_service_start_does_not_create_duplicate_worker(self):
        detector = MockWakeWordDetector()
        service = AudioService(detector, self.recognizer, MockSpeechSynthesizer())
        service.start()
        worker = service._worker
        service.start()
        self.assertIs(service._worker, worker)
        service.shutdown()
        service.shutdown()
        self.assertFalse(service.worker_alive)


if __name__ == "__main__":
    unittest.main()
