"""Queued Windows OneCore speech synthesis and playback via PyWinRT."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from queue import Empty, Full, Queue
import logging
from threading import Event, Lock, Thread
from typing import Any

logger = logging.getLogger(__name__)
_QUEUE_CAPACITY = 8
_MAX_UTTERANCE_CHARS = 700


@dataclass
class _SpeechJob:
    text: str
    stop_event: Event
    finished: Event = field(default_factory=Event)
    cancelled: Event = field(default_factory=Event)


@dataclass(frozen=True)
class VoiceInfo:
    display_name: str
    language: str
    voice_id: str


@dataclass(frozen=True)
class _WinRTApi:
    speech_synthesizer: Any
    media_source: Any
    media_player: Any
    media_player_audio_category: Any


class OneCoreSpeechSynthesizer:
    """SpeechSynthesizer for locally installed Windows OneCore voices.

    WinRT objects and a private asyncio loop are created, used and released on
    one dedicated worker. Speech generation and playback never run on the
    tray/UI thread, and only one response is played at a time.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        voice_id: str | None = None,
        rate: int = 180,
        volume: float = 1.0,
        winrt_api: _WinRTApi | Any | None = None,
    ) -> None:
        if not 80 <= rate <= 350:
            raise ValueError("Speech rate must be between 80 and 350")
        if not 0.0 <= volume <= 1.0:
            raise ValueError("Speech volume must be between 0 and 1")
        self.enabled = enabled
        self.voice_id = voice_id
        self.rate = rate
        self.volume = volume
        self._winrt_api = winrt_api
        self._lock = Lock()
        self._queue: Queue[_SpeechJob | None] = Queue(maxsize=_QUEUE_CAPACITY)
        self._worker: Thread | None = None
        self._synthesizer: Any | None = None
        self._current_job: _SpeechJob | None = None
        self._ready = Event()
        self._shutdown = Event()
        self._opened = False
        self._error: str | None = None
        self._available_voices: tuple[tuple[str, str], ...] = ()
        self._voice_details: tuple[VoiceInfo, ...] = ()

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._opened

    @property
    def worker_alive(self) -> bool:
        with self._lock:
            return self._worker is not None and self._worker.is_alive()

    @property
    def last_error(self) -> str | None:
        with self._lock:
            return self._error

    @property
    def available_voices(self) -> tuple[tuple[str, str], ...]:
        """Compatibility view for existing voice-ID/name consumers."""
        with self._lock:
            return self._available_voices

    @property
    def voice_details(self) -> tuple[VoiceInfo, ...]:
        with self._lock:
            return self._voice_details

    def open(self) -> None:
        with self._lock:
            if self._opened:
                return
            self._opened = True
            self._error = None
            self._ready = Event()
            self._shutdown = Event()
            if not self.enabled:
                self._ready.set()
                return
            worker = Thread(
                target=self._worker_main,
                name="CompAssistantOneCoreSpeech",
                daemon=False,
            )
            self._worker = worker
            try:
                worker.start()
            except Exception:
                self._worker = None
                self._opened = False
                raise

    def speak(self, text: str, stop_event: Event) -> None:
        text = text.strip()
        if not self.enabled or not text or stop_event.is_set():
            return
        if not self.is_open:
            logger.warning("Speech requested while OneCore synthesizer is closed")
            return
        if not self._ready.wait(timeout=8.0):
            self._set_error("Windows OneCore speech service did not initialize in time")
            return
        if self.last_error:
            return

        job = _SpeechJob(text=text, stop_event=stop_event)
        try:
            self._queue.put_nowait(job)
        except Full:
            self._set_error("Speech output queue is full; response was not spoken")
            return
        while not job.finished.wait(timeout=0.05):
            if stop_event.is_set():
                job.cancelled.set()
                self.clear_queue()
        if stop_event.is_set():
            job.cancelled.set()

    def clear_queue(self) -> None:
        while True:
            try:
                job = self._queue.get_nowait()
            except Empty:
                return
            if job is not None:
                job.cancelled.set()
                job.finished.set()
            self._queue.task_done()

    def stop_playback(self) -> None:
        self.clear_queue()
        with self._lock:
            current = self._current_job
        if current is not None:
            current.cancelled.set()

    def close(self) -> None:
        with self._lock:
            if not self._opened:
                return
            self._opened = False
            worker = self._worker
            shutdown = self._shutdown
        self.stop_playback()
        shutdown.set()
        if worker is not None:
            try:
                self._queue.put_nowait(None)
            except Full:
                self.clear_queue()
                self._queue.put_nowait(None)
            worker.join()
        # The worker may exit on _shutdown before dequeuing its sentinel.
        self.clear_queue()
        with self._lock:
            self._worker = None
            self._synthesizer = None
            self._current_job = None

    def _set_error(self, message: str, error: Exception | None = None) -> None:
        with self._lock:
            self._error = message
        if error is None:
            logger.error("%s", message)
        else:
            logger.error("%s: %s", message, error, exc_info=error)

    def _load_api(self) -> _WinRTApi | Any:
        if self._winrt_api is not None:
            return self._winrt_api
        try:
            from winrt.windows.media.core import MediaSource
            from winrt.windows.media.playback import MediaPlayer, MediaPlayerAudioCategory
            from winrt.windows.media.speechsynthesis import SpeechSynthesizer
        except ImportError as error:
            raise RuntimeError(
                "Windows OneCore TTS için PyWinRT paketleri eksik. "
                "requirements-tray.txt dosyasındaki WinRT bağımlılıklarını kurun."
            ) from error
        return _WinRTApi(
            speech_synthesizer=SpeechSynthesizer,
            media_source=MediaSource,
            media_player=MediaPlayer,
            media_player_audio_category=MediaPlayerAudioCategory,
        )

    def _worker_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._initialize())
            self._ready.set()
            self._consume_jobs(loop)
        except Exception as error:
            if isinstance(error, RuntimeError):
                message = str(error)
            else:
                message = (
                    "Windows OneCore TTS başlatılamadı. Windows konuşma hizmetini "
                    "ve kurulu sesleri kontrol edin."
                )
            self._set_error(message, error)
            self._ready.set()
            self._fail_pending_jobs()
        finally:
            if self._synthesizer is not None:
                try:
                    self._synthesizer.close()
                except Exception:
                    logger.exception("Could not close OneCore SpeechSynthesizer")
            with self._lock:
                self._synthesizer = None
                self._current_job = None
            asyncio.set_event_loop(None)
            loop.close()

    async def _initialize(self) -> None:
        api = self._load_api()
        try:
            voices = tuple(api.speech_synthesizer.all_voices)
        except Exception as error:
            raise RuntimeError(
                "Windows OneCore AllVoices envanteri okunamadı "
                f"({error}). OneCore konuşma hizmeti bu oturumda kullanılamıyor."
            ) from error
        self._remember_voices(voices)
        selected = self._select_turkish_voice(voices)
        if selected is None:
            raise RuntimeError(
                "Windows OneCore üzerinden Türkçe (tr-TR) ses bulunamadı. "
                "Varsayılan İngilizce/Almanca ses kullanılmayacak."
            )
        try:
            synthesizer = api.speech_synthesizer()
            with self._lock:
                self._synthesizer = synthesizer
            synthesizer.voice = selected
            options = synthesizer.options
            options.speaking_rate = max(0.5, min(6.0, self.rate / 180.0))
            options.audio_volume = self.volume
        except Exception as error:
            raise RuntimeError("OneCore SpeechSynthesizer oluşturulamadı.") from error
    def _remember_voices(self, voices: tuple[Any, ...]) -> None:
        details = tuple(
            VoiceInfo(
                display_name=str(voice.display_name),
                language=str(voice.language),
                voice_id=str(voice.id),
            )
            for voice in voices
        )
        with self._lock:
            self._voice_details = details
            self._available_voices = tuple(
                (voice.voice_id, voice.display_name) for voice in details
            )
        logger.info(
            "OneCore voices available: %s",
            ", ".join(
                f"{voice.display_name} | {voice.language} | {voice.voice_id}"
                for voice in details
            ) or "none",
        )

    def _select_turkish_voice(self, voices: tuple[Any, ...]) -> Any | None:
        turkish = tuple(
            voice for voice in voices if _is_turkish_language(str(voice.language))
        )
        if self.voice_id:
            requested = self.voice_id.casefold()
            configured = next(
                (
                    voice for voice in voices
                    if str(voice.id).casefold() == requested
                    or str(voice.display_name).casefold() == requested
                ),
                None,
            )
            if configured is None:
                raise RuntimeError(
                    "tts_voice_id ayarındaki OneCore sesi bulunamadı."
                )
            if configured not in turkish:
                raise RuntimeError(
                    "tts_voice_id ayarındaki ses Türkçe (tr-TR) değil; başka dil seçilmeyecek."
                )
            return configured
        tolga = next(
            (voice for voice in turkish if "tolga" in str(voice.display_name).casefold()),
            None,
        )
        return tolga or (turkish[0] if turkish else None)

    def _consume_jobs(self, loop: asyncio.AbstractEventLoop) -> None:
        while not self._shutdown.is_set():
            try:
                job = self._queue.get(timeout=0.1)
            except Empty:
                continue
            if job is None:
                self._queue.task_done()
                break
            with self._lock:
                self._current_job = job
            try:
                for part in _split_text(job.text):
                    if job.cancelled.is_set() or job.stop_event.is_set() or self._shutdown.is_set():
                        break
                    loop.run_until_complete(self._speak_part(part, job))
            except Exception as error:
                self._set_error(
                    f"Windows OneCore speech synthesis or playback failed: {error}",
                    error,
                )
            finally:
                job.finished.set()
                with self._lock:
                    self._current_job = None
                self._queue.task_done()

    async def _speak_part(self, text: str, job: _SpeechJob) -> None:
        synthesizer = self._synthesizer
        if synthesizer is None or _cancelled(job, self._shutdown):
            return

        async def synthesize():
            return await synthesizer.synthesize_text_to_stream_async(text)

        synthesis_task = asyncio.create_task(synthesize())
        try:
            while not synthesis_task.done():
                if _cancelled(job, self._shutdown):
                    synthesis_task.cancel()
                    await asyncio.gather(synthesis_task, return_exceptions=True)
                    return
                await asyncio.wait((synthesis_task,), timeout=0.05)
            stream = synthesis_task.result()
        except Exception:
            if not synthesis_task.done():
                synthesis_task.cancel()
                await asyncio.gather(synthesis_task, return_exceptions=True)
            raise

        api = self._load_api()
        player = None
        media_source = None
        ended = asyncio.Event()
        playback_errors: list[str] = []
        loop = asyncio.get_running_loop()
        ended_token = None
        failed_token = None

        def signal_playback_failure(_sender: Any, args: Any) -> None:
            detail = str(getattr(args, "error", "MediaPlayer reported a playback failure"))

            def finish_with_error() -> None:
                playback_errors.append(detail)
                ended.set()

            loop.call_soon_threadsafe(finish_with_error)

        try:
            player = api.media_player()
            player.audio_category = api.media_player_audio_category.SPEECH
            media_source = api.media_source.create_from_stream(stream, stream.content_type)
            player.source = media_source
            ended_token = player.add_media_ended(
                lambda _sender, _args: loop.call_soon_threadsafe(ended.set)
            )
            failed_token = player.add_media_failed(signal_playback_failure)
            player.play()
            while not ended.is_set() and not _cancelled(job, self._shutdown):
                try:
                    await asyncio.wait_for(ended.wait(), timeout=0.05)
                except asyncio.TimeoutError:
                    continue
            if playback_errors:
                raise RuntimeError(playback_errors[0])
        finally:
            if player is not None:
                if ended_token is not None:
                    try:
                        player.remove_media_ended(ended_token)
                    except Exception:
                        logger.debug("Could not remove OneCore playback event handler")
                if failed_token is not None:
                    try:
                        player.remove_media_failed(failed_token)
                    except Exception:
                        logger.debug("Could not remove OneCore playback failure handler")
                try:
                    player.pause()
                except Exception:
                    logger.debug("Could not pause OneCore playback")
                try:
                    player.source = None
                except Exception:
                    logger.debug("Could not detach OneCore playback source")
                try:
                    player.close()
                except Exception:
                    logger.exception("Could not close OneCore MediaPlayer")
            if media_source is not None:
                try:
                    media_source.close()
                except Exception:
                    logger.debug("Could not close OneCore MediaSource")
            try:
                stream.close()
            except Exception:
                logger.debug("Could not close OneCore SpeechSynthesisStream")

    def _fail_pending_jobs(self) -> None:
        while True:
            try:
                job = self._queue.get_nowait()
            except Empty:
                return
            if job is not None:
                job.finished.set()
            self._queue.task_done()


def _is_turkish_language(language: str) -> bool:
    return language.strip().replace("_", "-").casefold().split("-", 1)[0] == "tr"


def _cancelled(job: _SpeechJob, shutdown: Event) -> bool:
    return job.cancelled.is_set() or job.stop_event.is_set() or shutdown.is_set()


def _split_text(text: str, maximum: int = _MAX_UTTERANCE_CHARS) -> tuple[str, ...]:
    parts: list[str] = []
    remaining = text.strip()
    while len(remaining) > maximum:
        split_at = max(
            remaining.rfind(". ", 0, maximum),
            remaining.rfind("? ", 0, maximum),
            remaining.rfind("! ", 0, maximum),
            remaining.rfind(" ", 0, maximum),
        )
        if split_at <= 0:
            split_at = maximum
        parts.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        parts.append(remaining)
    return tuple(parts)


def list_onecore_voices(api: _WinRTApi | Any | None = None) -> tuple[VoiceInfo, ...]:
    """Return OneCore AllVoices metadata; intended for the local diagnostic."""
    if api is None:
        try:
            from winrt.windows.media.speechsynthesis import SpeechSynthesizer
        except ImportError as error:
            raise RuntimeError(
                "OneCore tanılaması için winrt-Windows.Media.SpeechSynthesis kurun."
            ) from error
        synthesizer_type = SpeechSynthesizer
    else:
        synthesizer_type = api.speech_synthesizer
    try:
        return tuple(
            VoiceInfo(str(voice.display_name), str(voice.language), str(voice.id))
            for voice in synthesizer_type.all_voices
        )
    except Exception as error:
        raise RuntimeError(
            f"Windows OneCore AllVoices envanteri okunamadı ({error})."
        ) from error
