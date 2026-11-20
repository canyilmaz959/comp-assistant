from __future__ import annotations

import time
import unittest

from comp_assistant.lifecycle import RuntimeState
from comp_assistant.runtime import AssistantRuntime
from comp_assistant.voice import MockAudioService


class AssistantRuntimeLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.audio = MockAudioService(command_handler=lambda text: f"Processed: {text}")
        self.runtime = AssistantRuntime(1, audio_service=self.audio)

    def tearDown(self) -> None:
        self.runtime.shutdown()

    def wait_for(self, predicate, timeout: float = 1.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.01)
        self.fail("Condition was not reached before timeout")

    def test_wake_recognize_and_return_to_standby(self) -> None:
        self.assertEqual(self.runtime.state, RuntimeState.STANDBY)
        self.assertTrue(self.audio.worker_alive)

        self.audio.recognizer.submit("hello assistant")
        self.audio.detector.trigger()

        self.wait_for(lambda: self.audio.synthesizer.spoken)
        self.wait_for(lambda: self.runtime.state is RuntimeState.STANDBY)
        self.assertEqual(self.audio.synthesizer.spoken, ["Processed: hello assistant"])

    def test_pause_stops_worker_and_releases_services_then_resume_reopens(self) -> None:
        self.runtime.pause()

        self.assertEqual(self.runtime.state, RuntimeState.PAUSED)
        self.assertFalse(self.audio.worker_alive)
        self.assertFalse(self.audio.detector.is_open)
        self.assertFalse(self.audio.recognizer.is_open)
        self.assertFalse(self.audio.synthesizer.is_open)

        self.runtime.resume()

        self.assertEqual(self.runtime.state, RuntimeState.STANDBY)
        self.assertTrue(self.audio.worker_alive)
        self.assertTrue(self.audio.detector.is_open)
        self.assertEqual(self.audio.detector.open_count, 2)

    def test_repeated_shutdown_is_idempotent_and_resume_cannot_restart(self) -> None:
        self.runtime.shutdown()
        counts = (
            self.audio.detector.close_count,
            self.audio.recognizer.close_count,
            self.audio.synthesizer.close_count,
        )

        self.runtime.shutdown()
        self.runtime.resume()

        self.assertEqual(self.runtime.state, RuntimeState.STOPPED)
        self.assertFalse(self.audio.worker_alive)
        self.assertEqual(
            (
                self.audio.detector.close_count,
                self.audio.recognizer.close_count,
                self.audio.synthesizer.close_count,
            ),
            counts,
        )

    def test_pause_and_shutdown_are_safe_when_repeated(self) -> None:
        self.runtime.pause()
        close_counts = (
            self.audio.detector.close_count,
            self.audio.recognizer.close_count,
            self.audio.synthesizer.close_count,
        )
        self.runtime.pause()
        self.assertEqual(
            (
                self.audio.detector.close_count,
                self.audio.recognizer.close_count,
                self.audio.synthesizer.close_count,
            ),
            close_counts,
        )
        self.runtime.shutdown()
        self.assertEqual(self.runtime.state, RuntimeState.STOPPED)

    def test_shutdown_while_recognizer_waits_leaves_no_worker_or_open_service(self) -> None:
        self.audio.detector.trigger()
        self.wait_for(lambda: self.runtime.state is RuntimeState.ACTIVE)

        self.runtime.shutdown()

        self.assertEqual(self.runtime.state, RuntimeState.STOPPED)
        self.assertFalse(self.audio.worker_alive)
        self.assertFalse(self.audio.detector.is_open)
        self.assertFalse(self.audio.recognizer.is_open)
        self.assertFalse(self.audio.synthesizer.is_open)


if __name__ == "__main__":
    unittest.main()
