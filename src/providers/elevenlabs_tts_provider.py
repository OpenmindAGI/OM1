import logging
import threading
import time
from typing import Callable, Optional

from om1_speech import AudioOutputStream

from .singleton import singleton


@singleton
class ElevenLabsTTSProvider:
    """
    Text-to-Speech Provider that manages an audio output stream.

    A singleton class that handles text-to-speech conversion and audio output
    through a dedicated thread.

    Parameters
    ----------
    url : str
        The URL endpoint for the TTS service
    api_key : str
        The API key for the TTS service
    device : int, optional
        The audio device index for audio output (default is None)
    speaker_name : str, optional
        The name of the speaker for audio output (default is None)
    voice_id : str, optional
        The name of the voice for Eleven Labs TTS service (default is JBFqnCBsd6RMkjVDRZzb)
    model_id : str, optional
        The name of the model for Eleven Labs TTS service (default is eleven_multilingual
    output_format : str, optional
        The output format for the audio stream (default is mp3_44100_128)
    """

    def __init__(
        self,
        url: str,
        api_key: Optional[str] = None,
        elevenlabs_api_key: Optional[str] = None,
        device_id: Optional[int] = None,
        speaker_name: Optional[str] = None,
        voice_id: Optional[str] = "JBFqnCBsd6RMkjVDRZzb",
        model_id: Optional[str] = "eleven_flash_v2_5",
        output_format: Optional[str] = "mp3_44100_128",
    ):
        """
        Initialize the TTS provider with given URL.
        """
        self.api_key: str = api_key
        self.elevenlabs_api_key: str = elevenlabs_api_key

        # Initialize TTS provider
        self.running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._audio_stream: AudioOutputStream = AudioOutputStream(
            url=url,
            device=device_id,
            device_name=speaker_name,
            headers={"x-api-key": api_key} if api_key else None,
        )

        # Set Eleven Labs TTS parameters
        self._voice_id = voice_id
        self._model_id = model_id
        self._output_format = output_format

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
        elevenlabs_api_key = (
            {"elevenlabs_api_key": self.elevenlabs_api_key}
            if self.elevenlabs_api_key
            else {}
        )
        self._audio_stream.add_request(
            {
                "text": text,
                "voice_id": self._voice_id,
                "model_id": self._model_id,
                "output_format": self._output_format,
                **elevenlabs_api_key,
            }
        )

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
