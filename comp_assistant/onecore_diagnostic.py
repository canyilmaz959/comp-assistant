"""Standalone, stage-by-stage Windows OneCore speech diagnostics.

Run from the repository root with the project's interpreter:
``python -m comp_assistant.onecore_diagnostic``

The script does not import or start the tray, runtime, microphone, or project
TTS worker. Pass ``--playback`` to send successfully synthesized test phrases
to the current Windows playback device.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
from importlib import metadata
import platform
import struct
import sys
from threading import Thread
from typing import Any


_PHRASE = "Merhaba, ben Comp. T\u00fcrk\u00e7e ses sistemini test ediyorum."
_PACKAGES = (
    "winrt-runtime",
    "winrt-Windows.Media.SpeechSynthesis",
    "winrt-Windows.Media.Core",
    "winrt-Windows.Media.Playback",
)


def _exception_details(error: BaseException) -> str:
    """Format exception/HRESULT details without dumping machine paths."""
    parts = [f"{type(error).__module__}.{type(error).__qualname__}: {error!r}"]
    if error.args:
        parts.append(f"args={error.args!r}")
    code = getattr(error, "winerror", None)
    if code is None:
        code = getattr(error, "hresult", None)
    if code is None and error.args and isinstance(error.args[0], int):
        code = error.args[0]
    if isinstance(code, int):
        parts.append(f"HRESULT/WinError={code} (0x{code & 0xFFFFFFFF:08X})")
    return "; ".join(parts)


def _report(name: str, operation) -> Any | None:
    try:
        result = operation()
    except Exception as error:
        print(f"[FAIL] {name}: {_exception_details(error)}")
        return None
    print(f"[PASS] {name}")
    return result


def _voice_details(voice: Any, label: str) -> tuple[str, str, str]:
    display_name = str(voice.display_name)
    language = str(voice.language)
    voice_id = str(voice.id)
    print(f"  {label}: DisplayName={display_name!r}; Language={language!r}; Id={voice_id!r}")
    return display_name, language, voice_id


def _environment() -> None:
    print("=== Environment ===")
    print(f"Python: {platform.python_version()} ({struct.calcsize('P') * 8}-bit)")
    print(f"Implementation: {platform.python_implementation()}")
    if hasattr(sys, "getwindowsversion"):
        version = sys.getwindowsversion()
        print(
            f"Windows: {platform.platform()} "
            f"(Win32 version={version.major}.{version.minor}.{version.build})"
        )
    else:
        print(f"OS: {platform.system()} {platform.release()} ({platform.version()})")
    for package in _PACKAGES:
        try:
            version = metadata.version(package)
        except metadata.PackageNotFoundError:
            version = "not installed"
        print(f"{package}: {version}")
    print("Narrator voice (user-reported): Tolga, Turkish, selected; this script does not query Narrator settings.")


async def _synthesize(label: str, synthesizer_type: Any, voice: Any | None):
    synthesizer = _report(f"{label} - create SpeechSynthesizer()", synthesizer_type)
    if synthesizer is None:
        print(f"[SKIP] {label} - synthesize_text_to_stream_async: instance creation failed")
        return None
    if voice is not None:
        try:
            synthesizer.voice = voice
            print(f"[PASS] {label} - assign selected voice")
        except Exception as error:
            print(f"[FAIL] {label} - assign selected voice: {_exception_details(error)}")
            _close(synthesizer)
            return None
    try:
        stream = await synthesizer.synthesize_text_to_stream_async(_PHRASE)
        print(f"[PASS] {label}: stream generated (content_type={stream.content_type!r})")
        return synthesizer, stream
    except Exception as error:
        print(f"[FAIL] {label} - synthesize_text_to_stream_async: {_exception_details(error)}")
        _close(synthesizer)
        return None


def _close(value: Any | None) -> None:
    if value is not None:
        try:
            value.close()
        except Exception as error:
            print(f"[WARN] Resource close: {_exception_details(error)}")


async def _playback(label: str, stream: Any, api: dict[str, Any]) -> bool:
    player = None
    source = None
    loop = asyncio.get_running_loop()
    ended = asyncio.Event()
    failed: asyncio.Future[str] = loop.create_future()

    def on_ended(_sender: Any, _args: Any) -> None:
        loop.call_soon_threadsafe(ended.set)

    def on_failed(_sender: Any, args: Any) -> None:
        detail = str(getattr(args, "error", "MediaPlayer reported a playback failure"))
        loop.call_soon_threadsafe(
            lambda: None if failed.done() else failed.set_result(detail)
        )

    try:
        player = api["MediaPlayer"]()
        player.audio_category = api["MediaPlayerAudioCategory"].SPEECH
        source = api["MediaSource"].create_from_stream(stream, stream.content_type)
        player.source = source
        ended_token = player.add_media_ended(on_ended)
        failed_token = player.add_media_failed(on_failed)
        player.play()
        ended_task = asyncio.create_task(ended.wait())
        done, pending = await asyncio.wait(
            (ended_task, failed), timeout=30.0, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        if not done:
            raise TimeoutError("No MediaEnded/MediaFailed event within 30 seconds")
        if failed in done:
            raise RuntimeError(f"MediaPlayer playback failed: {failed.result()}")
        print(f"[PASS] {label}: playback completed")
        return True
    except Exception as error:
        print(f"[FAIL] {label}: {_exception_details(error)}")
        return False
    finally:
        if player is not None:
            for event_name, token_name in (("remove_media_ended", "ended_token"), ("remove_media_failed", "failed_token")):
                token = locals().get(token_name)
                if token is not None:
                    try:
                        getattr(player, event_name)(token)
                    except Exception:
                        pass
            try:
                player.pause()
                player.source = None
            except Exception:
                pass
            _close(player)
        _close(source)
        _close(stream)


async def _run(playback: bool) -> int:
    _environment()
    print("\n=== API stages ===")
    print(f"[PASS] Asyncio event loop running ({type(asyncio.get_running_loop()).__name__})")
    imports: dict[str, Any] = {}
    for module_name, symbol in (
        ("winrt.windows.media.speechsynthesis", "SpeechSynthesizer"),
        ("winrt.windows.media.core", "MediaSource"),
        ("winrt.windows.media.playback", "MediaPlayer"),
        ("winrt.windows.media.playback", "MediaPlayerAudioCategory"),
    ):
        try:
            imports[symbol] = getattr(importlib.import_module(module_name), symbol)
        except Exception as error:
            print(f"[FAIL] Import {module_name}.{symbol}: {_exception_details(error)}")
    required = {"SpeechSynthesizer", "MediaSource", "MediaPlayer", "MediaPlayerAudioCategory"}
    if required.issubset(imports):
        print("[PASS] Required WinRT module imports")
    else:
        print("[FAIL] Required WinRT module imports (one or more imports failed)")
    speech_type = imports.get("SpeechSynthesizer")
    if speech_type is None:
        for stage in (
            "Create SpeechSynthesizer", "Read default_voice", "Read all_voices",
            "Default-voice Turkish synthesis", "Explicit Turkish-voice synthesis",
        ):
            print(f"[SKIP] {stage}: SpeechSynthesizer import unavailable")
        return 1

    synthesizer = _report("Create SpeechSynthesizer()", speech_type)
    _close(synthesizer)

    default_voice = _report("Read SpeechSynthesizer.default_voice", lambda: speech_type.default_voice)
    if default_voice is not None:
        try:
            _report("Read default voice metadata", lambda: _voice_details(default_voice, "DefaultVoice"))
        except Exception as error:
            print(f"[FAIL] Read default voice metadata: {_exception_details(error)}")
    else:
        print("[SKIP] Default voice metadata: default_voice unavailable")

    voices = _report("Read SpeechSynthesizer.all_voices", lambda: tuple(speech_type.all_voices))
    turkish_voices: list[Any] = []
    if voices is None:
        print("[SKIP] Enumerate voice metadata: all_voices unavailable")
        print("[SKIP] Find Turkish voices: all_voices unavailable")
    else:
        metadata_ok = True
        for index, voice in enumerate(voices, start=1):
            try:
                _voice_details(voice, f"AllVoices[{index}]")
                if str(voice.language).strip().casefold().startswith("tr"):
                    turkish_voices.append(voice)
            except Exception as error:
                metadata_ok = False
                print(f"[FAIL] Read AllVoices[{index}] metadata: {_exception_details(error)}")
        print(f"[{'PASS' if metadata_ok else 'FAIL'}] Enumerate voice metadata ({len(voices)} voices)")
        if turkish_voices:
            print(f"[PASS] Find Turkish voices: {len(turkish_voices)}")
            for voice in turkish_voices:
                try:
                    _voice_details(voice, "Turkish")
                except Exception as error:
                    print(f"[FAIL] Read Turkish voice metadata: {_exception_details(error)}")
        else:
            print("[FAIL] Find Turkish voices: no language beginning with 'tr'")

    streams: list[tuple[str, Any, Any]] = []
    default_result = await _synthesize("Synthesize Turkish phrase using default voice", speech_type, default_voice)
    if default_result:
        streams.append(("Default voice", *default_result))
    else:
        print("[FAIL] Default-voice Turkish synthesis")

    preferred_turkish = next(
        (voice for voice in turkish_voices if "tolga" in str(voice.display_name).casefold()),
        turkish_voices[0] if turkish_voices else None,
    )
    if preferred_turkish is None:
        print("[SKIP] Explicit Turkish-voice synthesis: no Turkish voice was enumerated")
    else:
        turkish_result = await _synthesize("Synthesize Turkish phrase using enumerated Turkish voice", speech_type, preferred_turkish)
        if turkish_result:
            streams.append((f"Turkish voice {preferred_turkish.display_name}", *turkish_result))
        else:
            print("[FAIL] Explicit Turkish-voice synthesis")

    if playback:
        if not {"MediaSource", "MediaPlayer", "MediaPlayerAudioCategory"}.issubset(imports):
            print("[SKIP] Audio playback: MediaPlayer WinRT imports unavailable")
            for _, stream, synthesizer in streams:
                _close(stream)
                _close(synthesizer)
        elif not streams:
            print("[SKIP] Audio playback: no synthesis stream was generated")
        else:
            for label, stream, synth in streams:
                await _playback(f"Playback ({label})", stream, imports)
                _close(synth)
    else:
        print("[INFO] Playback not requested; pass --playback to test the Windows audio output path.")
        for _, stream, synth in streams:
            _close(stream)
            _close(synth)

    return 0


def _run_in_worker_thread(playback: bool) -> int:
    result: list[int] = []
    errors: list[BaseException] = []

    def run() -> None:
        loop = None
        try:
            print("[PASS] Dedicated diagnostic thread started")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            print("[PASS] Dedicated thread asyncio event loop initialized")
            result.append(loop.run_until_complete(_run(playback)))
        except BaseException as error:
            errors.append(error)
        finally:
            if loop is not None:
                asyncio.set_event_loop(None)
                loop.close()

    worker = Thread(target=run, name="OneCoreDiagnostic", daemon=False)
    try:
        worker.start()
    except Exception as error:
        print(f"[FAIL] Dedicated diagnostic thread start: {_exception_details(error)}")
        return 1
    worker.join()
    if errors:
        print(f"[FAIL] Worker-thread diagnostic: {_exception_details(errors[0])}")
        return 1
    return result[0] if result else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run isolated, stage-by-stage Windows OneCore voice/synthesis diagnostics."
    )
    parser.add_argument(
        "--playback",
        action="store_true",
        help="Play successfully synthesized diagnostic phrases through the default output device.",
    )
    parser.add_argument(
        "--worker-thread",
        action="store_true",
        help="Run the async diagnostic on a dedicated thread, matching the app's TTS worker context.",
    )
    args = parser.parse_args()
    try:
        if args.worker_thread:
            print("Execution context: dedicated worker thread with its own asyncio loop")
            return _run_in_worker_thread(args.playback)
        print("Execution context: process main thread with its own asyncio loop")
        return asyncio.run(_run(args.playback))
    except KeyboardInterrupt:
        print("[ABORT] Diagnostic interrupted by user.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
