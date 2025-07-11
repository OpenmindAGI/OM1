from actions.base import ActionConfig, ActionConnector
from actions.speak.interface import SpeakInput
from providers.asr_provider import ASRProvider
from providers.elevenlabs_tts_provider import ElevenLabsTTSProvider

import time
import math
import logging

import zenoh

# unstable / not released
#from zenoh.ext import HistoryConfig, Miss, RecoveryConfig, declare_advanced_subscriber

from zenoh_idl.status_msgs import AudioStatus
from zenoh_idl.std_msgs import Header, Time, String
from pycdr2.types import array, float32, float64, int8, int32, sequence, uint8, uint16, uint32

class SpeakElevenLabsTTSConnector(ActionConnector[SpeakInput]):

    def __init__(self, config: ActionConfig):
        
        super().__init__(config)

        # Get microphone and speaker device IDs and names
        microphone_device_id = getattr(self.config, "microphone_device_id", None)
        microphone_name = getattr(self.config, "microphone_name", None)

        # OM API key
        api_key = getattr(self.config, "api_key", None)

        # Eleven Labs TTS configuration
        elevenlabs_api_key = getattr(self.config, "elevenlabs_api_key", None)
        voice_id = getattr(self.config, "voice_id", "JBFqnCBsd6RMkjVDRZzb")
        model_id = getattr(self.config, "model_id", "eleven_flash_v2_5")
        output_format = getattr(self.config, "output_format", "mp3_44100_128")

        self.topic = 'robot/status/audio'
        self.session = None
        self.pub = None
        self.sentence_counter = 0

        self.audio_status = AudioStatus(
            header = self.prepare_header(),
            status_mic = AudioStatus.STATUS_MIC.ENABLED.value,
            status_speaker = AudioStatus.STATUS_SPEAKER.READY.value,
            sentence_to_speak = String(""),
            sentence_counter = self.sentence_counter
        )

        try:
            self.session = zenoh.open(zenoh.Config())
            self.pub = self.session.declare_publisher(self.topic)
            self.session.declare_subscriber(self.topic, self.audio_message)
            
            # advanced_sub = declare_advanced_subscriber(
            #     self.session,
            #     self.topic,
            #     self.audio_message,
            #     history=HistoryConfig(detect_late_publishers=True),
            #     recovery=RecoveryConfig(heartbeat=True),
            #     subscriber_detection=True,
            # )

            # advanced_sub.sample_miss_listener(self.miss_listener)

            if self.pub:
                new_state = self.audio_status.serialize()
                logging.info(f"TTS new state: {new_state}")
                self.pub.put(new_state)
            logging.info("TTS Zenoh client opened")
        except Exception as e:
            logging.error(f"Error opening TTS Zenoh client: {e}")

        # Initialize ASR and TTS providers
        self.asr = ASRProvider(
            ws_url="wss://api-asr.openmind.org",
            device_id=microphone_device_id,
            microphone_name=microphone_name,
        )

        self.tts = ElevenLabsTTSProvider(
            url="https://api.openmind.org/api/core/elevenlabs/tts",
            api_key=api_key,
            elevenlabs_api_key=elevenlabs_api_key,
            voice_id=voice_id,
            model_id=model_id,
            output_format=output_format,
        )
        self.tts.start()
        self.tts.add_pending_message("Woof Woof")

    def audio_message(self, data):
        self.audio_status = AudioStatus.deserialize(data.payload.to_bytes())
        logging.info(f"TTS Received: {self.audio_status} {time.time()}") 

    # def miss_listener(self, miss: Miss):
    #     logging.error(f">> [Subscriber] Missed {miss.nb} samples from {miss.source} !!!")

    def prepare_header(self) -> Header:
        ts = time.time()
        remainder, seconds = math.modf(ts)
        timestamp = Time(
            sec = int32(seconds), 
            nanosec = uint32(remainder * 1000000000)
        )
        header = Header(
            stamp = timestamp,
            frame_id = str(self.sentence_counter)
        )
        return header

    async def connect(self, output_interface: SpeakInput) -> None:
        # Block ASR until TTS is done
        # Send message to ASR to blank
        # No idea how to reset this once the speaker is done
        self.tts.register_tts_state_callback(self.asr.audio_stream.on_tts_state_change)
        
        # Add pending message to TTS
        # The TTS takes the string, sends it to the cloud, 
        # turns it into an audio file, and then plays that file
        string_to_speak = output_interface.action
        self.sentence_counter += 1

        new_state = self.audio_status
        new_state.header = self.prepare_header()
        new_state.STATUS_SPEAKER = AudioStatus.STATUS_SPEAKER.ACTIVE.value
        new_state.sentence_to_speak = String(string_to_speak)
        new_state.sentence_counter = self.sentence_counter

        logging.debug(f"Publishing AUDIO: {new_state}") 

        if self.pub:
            self.pub.put(new_state.serialize())

        self.tts.add_pending_message(string_to_speak)
