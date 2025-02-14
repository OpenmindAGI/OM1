from actions.base import ActionConfig, ActionConnector
from actions.speak.interface import SpeakInput
from providers.asr_provider import ASRProvider
from providers.tts_provider import TTSProvider


class SpeakRos2Connector(ActionConnector[SpeakInput]):

    def __init__(self, config: ActionConfig):
        super().__init__(config)

        microphone_device_id = None
        if hasattr(self.config, "microphone_device_id"):
            microphone_device_id = self.config.microphone_device_id

        speaker_device_id = None
        if hasattr(self.config, "speaker_device_id"):
            speaker_device_id = self.config.speaker_device

        microphone_name = None
        if hasattr(self.config, "microphone_name"):
            microphone_name = self.config.microphone_name

        speaker_name = None
        if hasattr(self.config, "speaker_name"):
            speaker_name = self.config.speaker_name

        # Initialize ASR and TTS providers
        self.asr = ASRProvider(
            ws_url="wss://api-asr.openmind.org",
            device_id=microphone_device_id,
            microphone_name=microphone_name,
        )
        self.tts = TTSProvider(
            url="https://api-tts.openmind.org",
            device_id=speaker_device_id,
            speaker_name=speaker_name,
        )
        self.tts.start()

    async def connect(self, output_interface: SpeakInput) -> None:
        # Block ASR until TTS is done
        self.tts.register_tts_state_callback(self.asr.audio_stream.on_tts_state_change)
        # Add pending message to TTS
        self.tts.add_pending_message(output_interface.sentence)
