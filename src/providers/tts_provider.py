import logging
import threading
import time
from typing import Callable, Optional

from om1_speech import AudioOutputStream

from .singleton import singleton


@singleton
class TTSProvider:
    """
    Text-to-Speech Provider that manages an audio output stream.

    A singleton class that handles text-to-speech conversion and audio output
    through a dedicated thread.

    Parameters
    ----------
    url : str
        The URL endpoint for the TTS service
    device : int, optional
        The audio device index for audio output (default is None)
    speaker_name : str, optional
        The name of the speaker for audio output (default is None)
    """

    def __init__(
        self,
        url: str,
        device_id: Optional[int] = None,
        speaker_name: Optional[str] = None,
    ):
        """
        Initialize the TTS provider with given URL.

        Parameters
        ----------
        url : str
            The URL endpoint for the TTS service
        """
        self.running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._audio_stream: AudioOutputStream = AudioOutputStream(
            url=url, device=device_id, device_name=speaker_name
        )

    def register_tts_state_callback(self, tts_state_callback: Optional[Callable]):
        """
        Register a callback for TTS state changes.

        Parameters
        ----------
        tts_state_callback : callable
            The callback function to receive TTS state changes.
        """
        self._audio_stream.set_tts_state_callback(tts_state_callback)

    def add_pending_message(self, text: str):
        """
        Add text to the pending queue for TTS processing.

        Parameters
        ----------
        text : str
            Text to be converted to speech
        """
        logging.info(f"audio_stream: {text}")
        self._audio_stream.add(text)

    def start(self):
        """
        Start the TTS provider and its audio stream.
        """
        if self.running:
            return

        self.running = True
        self._audio_stream.start()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """
        Internal method to run the TTS processing loop.
        """
        while self.running:
            try:
                time.sleep(0.1)
            except Exception as e:
                logging.error(f"TTSProvider error: {e}")

    def stop(self):
        """
        Stop the TTS provider and cleanup resources.
        """
        self.running = False
        if self._thread:
            self._audio_stream.stop()
            self._thread.join(timeout=5)
