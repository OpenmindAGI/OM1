from actions.base import ActionConfig, ActionConnector
from actions.speak.interface import SpeakInput
from providers.asr_provider import ASRProvider
from providers.riva_tts_provider import RivaTTSProvider


class SpeakRos2Connector(ActionConnector[SpeakInput]):

    def __init__(self, config: ActionConfig):
        super().__init__(config)

        # Get microphone and speaker device IDs and names
        microphone_device_id = getattr(self.config, "microphone_device_id", None)
        speaker_device_id = getattr(self.config, "speaker_device_id", None)
        microphone_name = getattr(self.config, "microphone_name", None)
        speaker_name = getattr(self.config, "speaker_name", None)

        # OM API key
        api_key = getattr(self.config, "api_key", None)

        # Initialize ASR and TTS providers
        self.asr = ASRProvider(
            ws_url="wss://api-asr.openmind.org",
            device_id=microphone_device_id,
            microphone_name=microphone_name,
        )
        self.tts = RivaTTSProvider(
            url="https://api.openmind.org/api/core/riva/tts",
            device_id=speaker_device_id,
            speaker_name=speaker_name,
            api_key=api_key,
        )
        self.tts.start()

    async def connect(self, output_interface: SpeakInput) -> None:
        # Block ASR until TTS is done
        self.tts.register_tts_state_callback(self.asr.audio_stream.on_tts_state_change)
        # Add pending message to TTS
        self.tts.add_pending_message(output_interface.action)
