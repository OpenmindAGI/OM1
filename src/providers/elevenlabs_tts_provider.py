import base64
import io
import logging
import threading
import time
from typing import Callable, Optional

from om1_speech import AudioOutputStream
from pydub import AudioSegment

from .singleton import singleton


class ElevenLabsAudioOutputStream(AudioOutputStream):
    """
    Audio output stream for Eleven Labs TTS service.

    This class extends the base AudioOutputStream class to provide
    additional functionality for the Eleven Labs TTS service.
    """

    def __init__(
        self,
        url,
        rate=8000,
        device=None,
        device_name=None,
        tts_state_callback=None,
        headers=None,
    ):
        super().__init__(url, rate, device, device_name, tts_state_callback, headers)

    def _write_audio(self, audio_data: bytes):
        """
        Override the base class method to write audio data from the Eleven Labs TTS service.
        """

        self._tts_callback(True)

        audio_bytes = base64.b64decode(audio_data)

        audio_segment = AudioSegment.from_mp3(io.BytesIO(audio_bytes))
        raw_data = audio_segment.raw_data

        current_format = self.stream._format
        needed_format = self._audio_interface.get_format_from_width(
            audio_segment.sample_width
        )

        if (
            current_format != needed_format
            or self.stream._channels != audio_segment.channels
            or self.stream._rate != audio_segment.frame_rate
        ):
            self.stream.stop_stream()
            self.stream.close()

            # Reopen the stream with the new format
            self.stream = self._audio_interface.open(
                output_device_index=self._device,
                format=needed_format,
                channels=audio_segment.channels,
                rate=audio_segment.frame_rate,
                output=True,
                frames_per_buffer=8192,
            )

        chunk_size = 8192
        for i in range(0, len(raw_data), chunk_size):
            self.stream.write(
                raw_data[i : i + chunk_size], exception_on_underflow=False
            )

        self._tts_callback(False)


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
        self._audio_stream: ElevenLabsAudioOutputStream = ElevenLabsAudioOutputStream(
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
