from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from comp_assistant.config import Settings
from comp_assistant.lifecycle import RuntimeState
from comp_assistant.microphone import MicrophoneCaptureError, MicrophoneManager
from comp_assistant.runtime import AssistantRuntime
from comp_assistant.voice import MockAudioService


class FakeFrames:
    def __init__(self, value: str) -> None:
        self.value = value

    def copy(self) -> "FakeFrames":
        return FakeFrames(self.value)


class FakeInputStream:
    def __init__(self, start_error: Exception | None = None, **kwargs) -> None:
        self.kwargs = kwargs
        self.callback = kwargs["callback"]
        self.start_error = start_error
        self.start_count = 0
        self.stop_count = 0
        self.close_count = 0
        self.active = False

    def start(self) -> None:
        self.start_count += 1
        if self.start_error is not None:
            raise self.start_error
        self.active = True

    def stop(self) -> None:
        self.stop_count += 1
        self.active = False

    def close(self) -> None:
        self.close_count += 1


class FakeSoundDevice:
    def __init__(
        self, error: Exception | None = None, start_error: Exception | None = None
    ) -> None:
        self.error = error
        self.start_error = start_error
        self.streams: list[FakeInputStream] = []

    def InputStream(self, **kwargs) -> FakeInputStream:
        if self.error is not None:
            raise self.error
        stream = FakeInputStream(start_error=self.start_error, **kwargs)
        self.streams.append(stream)
        return stream


class MicrophoneManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sounddevice = FakeSoundDevice()
        self.manager = MicrophoneManager(
            sample_rate=22_050,
            channels=2,
            block_size=512,
            input_device=None,
            dtype="float32",
            sounddevice_module=self.sounddevice,
        )

    def test_stream_uses_configuration_and_starts(self) -> None:
        self.manager.start()

        self.assertTrue(self.manager.is_capturing)
        self.assertTrue(self.manager.has_open_stream)
        stream = self.sounddevice.streams[0]
        self.assertEqual(stream.start_count, 1)
        self.assertEqual(stream.kwargs["device"], None)
        self.assertEqual(stream.kwargs["samplerate"], 22_050)
        self.assertEqual(stream.kwargs["channels"], 2)
        self.assertEqual(stream.kwargs["blocksize"], 512)
        self.assertEqual(stream.kwargs["dtype"], "float32")
        self.manager.close()

    def test_callback_delivers_copied_audio_frame(self) -> None:
        self.manager.start()
        original = FakeFrames("captured")
        self.sounddevice.streams[0].callback(original, 128, None, None)

        chunk = self.manager.read_frame()
        self.assertEqual(chunk.data.value, "captured")
        self.assertIsNot(chunk.data, original)
        self.assertEqual(chunk.frame_count, 128)
        self.manager.close()

    def test_repeated_start_does_not_create_duplicate_stream(self) -> None:
        self.manager.start()
        self.manager.start()

        self.assertEqual(len(self.sounddevice.streams), 1)
        self.manager.close()

    def test_stop_closes_stream_discards_frames_and_is_idempotent(self) -> None:
        self.manager.start()
        stream = self.sounddevice.streams[0]
        stream.callback(FakeFrames("queued"), 32, None, None)

        self.manager.stop()
        self.manager.stop()

        self.assertFalse(self.manager.is_capturing)
        self.assertFalse(self.manager.has_open_stream)
        self.assertEqual(stream.stop_count, 1)
        self.assertEqual(stream.close_count, 1)
        self.assertEqual(self.manager.queued_frames, 0)

    def test_repeated_close_is_safe_and_prevents_reopening(self) -> None:
        self.manager.start()
        self.manager.close()
        self.manager.close()

        self.assertFalse(self.manager.has_open_stream)
        self.assertFalse(self.manager.is_capturing)
        with self.assertRaises(MicrophoneCaptureError):
            self.manager.start()

    def test_device_initialization_error_is_clear_and_does_not_leak_stream(self) -> None:
        sounddevice = FakeSoundDevice(error=OSError("No default input device"))
        manager = MicrophoneManager(input_device="Missing Mic", sounddevice_module=sounddevice)

        with self.assertRaisesRegex(MicrophoneCaptureError, "Missing Mic") as raised:
            manager.start()

        self.assertIn("No default input device", str(raised.exception))
        self.assertFalse(manager.is_capturing)
        self.assertFalse(manager.has_open_stream)
        self.assertIsNotNone(manager.last_error)
        manager.close()

    def test_stream_start_error_closes_the_created_stream(self) -> None:
        sounddevice = FakeSoundDevice(start_error=OSError("stream start failed"))
        manager = MicrophoneManager(sounddevice_module=sounddevice)

        with self.assertRaisesRegex(MicrophoneCaptureError, "stream start failed"):
            manager.start()

        stream = sounddevice.streams[0]
        self.assertFalse(manager.is_capturing)
        self.assertFalse(manager.has_open_stream)
        self.assertEqual(stream.stop_count, 1)
        self.assertEqual(stream.close_count, 1)
        manager.close()

    def test_settings_keep_old_format_compatible_and_round_trip_audio_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(
                json.dumps({"command_wait_seconds": 12, "websites": ["https://example.com"]}),
                encoding="utf-8",
            )
            old = Settings.load(path)
            self.assertEqual(old.command_wait_seconds, 12)
            self.assertEqual(old.websites, ["https://example.com"])
            self.assertEqual(old.input_device, None)

            configured = Settings(
                command_wait_seconds=12,
                websites=["https://example.com"],
                sample_rate=48_000,
                channels=2,
                block_size=256,
                input_device="USB Mic",
                dtype="float32",
                vosk_model_directory="D:/speech/vosk-model-small-tr-0.3",
            )
            configured.save(path)
            reloaded = Settings.load(path)

        self.assertEqual(reloaded.sample_rate, 48_000)
        self.assertEqual(reloaded.channels, 2)
        self.assertEqual(reloaded.block_size, 256)
        self.assertEqual(reloaded.input_device, "USB Mic")
        self.assertEqual(reloaded.dtype, "float32")
        self.assertEqual(reloaded.vosk_model_directory, "D:/speech/vosk-model-small-tr-0.3")


class RuntimeMicrophoneLifecycleTests(unittest.TestCase):
    def wait_for(self, predicate, timeout: float = 1.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.01)
        self.fail("Condition was not reached before timeout")

    def make_runtime(self):
        sounddevice = FakeSoundDevice()
        manager = MicrophoneManager(sounddevice_module=sounddevice)
        audio = MockAudioService()
        runtime = AssistantRuntime(1, audio_service=audio, microphone_manager=manager)
        return runtime, audio, manager, sounddevice

    def test_active_capture_is_stopped_in_paused_and_resumes_without_duplicate(self) -> None:
        runtime, audio, manager, sounddevice = self.make_runtime()
        try:
            audio.detector.trigger()
            self.wait_for(lambda: runtime.state is RuntimeState.ACTIVE and manager.is_capturing)
            self.assertEqual(len(sounddevice.streams), 1)

            runtime.pause()
            self.assertEqual(runtime.state, RuntimeState.PAUSED)
            self.assertFalse(manager.is_capturing)
            self.assertFalse(manager.has_open_stream)

            runtime.resume()
            self.assertEqual(runtime.state, RuntimeState.STANDBY)
            self.assertFalse(manager.is_capturing)
            audio.detector.trigger()
            self.wait_for(lambda: runtime.state is RuntimeState.ACTIVE and manager.is_capturing)

            self.assertEqual(len(sounddevice.streams), 2)
            self.assertTrue(all(not stream.active for stream in sounddevice.streams[:-1]))
        finally:
            runtime.shutdown()

    def test_stopped_closes_capture_and_audio_worker(self) -> None:
        runtime, audio, manager, sounddevice = self.make_runtime()
        audio.detector.trigger()
        self.wait_for(lambda: manager.is_capturing)

        runtime.shutdown()

        self.assertEqual(runtime.state, RuntimeState.STOPPED)
        self.assertFalse(manager.is_capturing)
        self.assertFalse(manager.has_open_stream)
        self.assertFalse(audio.worker_alive)
        self.assertTrue(all(not stream.active for stream in sounddevice.streams))

    def test_capture_error_does_not_override_runtime_state_or_crash_worker(self) -> None:
        sounddevice = FakeSoundDevice(error=OSError("device unavailable"))
        manager = MicrophoneManager(sounddevice_module=sounddevice)
        audio = MockAudioService()
        runtime = AssistantRuntime(1, audio_service=audio, microphone_manager=manager)
        try:
            audio.detector.trigger()
            self.wait_for(lambda: runtime.state is RuntimeState.ACTIVE)
            self.wait_for(lambda: runtime.microphone_error is not None)
            self.assertIn("device unavailable", runtime.microphone_error)
            self.assertEqual(runtime.state, RuntimeState.ACTIVE)
            self.assertTrue(audio.worker_alive)
        finally:
            runtime.shutdown()


if __name__ == "__main__":
    unittest.main()
