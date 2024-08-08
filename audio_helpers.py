# This code is licensed under the Custom License for Paid Community Members.
# For more information, see the LICENSE file in the root directory of this repository.

import requests
import tempfile
import os
from werkzeug.utils import secure_filename
from config import Config
import os
from io import BytesIO
from typing import IO
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ElevenLabs client initialization
elevenlabs_client = None

def initialize_elevenlabs_client():
    global elevenlabs_client
    logger.info(f"Initiating ElevenLabs client")
    elevenlabs_client = ElevenLabs(api_key=Config.ELEVENLABS_API_KEY)

# client = ElevenLabs(
#     api_key=Config.ELEVENLABS_API_KEY,
# )

def text_to_speech(text):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{Config.VOICE_ID}"
    headers = {
        'Content-Type': 'application/json',
        'xi-api-key': Config.ELEVENLABS_API_KEY
    }
    data = {
        "model_id": "eleven_turbo_v2",
        "text": text,
        "optimize_streaming_latency": 2,
        "voice_settings": {
            "similarity_boost": 0.75,
            "stability": 0.5,
            "use_speaker_boost": True
        }
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.content
    else:
        raise Exception(f"Failed to generate speech: {response.text}")

def text_to_speech_stream(text: str) -> IO[bytes]:
    """
    Converts text to speech and returns the audio data as a byte stream.

    This function invokes a text-to-speech conversion API with specified parameters, including
    voice ID and various voice settings, to generate speech from the provided text. Instead of
    saving the output to a file, it streams the audio data into a BytesIO object.

    Args:
        text (str): The text content to be converted into speech.

    Returns:
        IO[bytes]: A BytesIO stream containing the audio data.
    """
    # Perform the text-to-speech conversion
    response = elevenlabs_client.text_to_speech.convert(
        voice_id=Config.VOICE_ID,  # Adam pre-made voice
        optimize_streaming_latency="2",
        output_format="mp3_22050_32",
        text=text,
        model_id="eleven_multilingual_v2",
        voice_settings=VoiceSettings(
            stability=0.5,
            similarity_boost=0.8,
            use_speaker_boost=True,
        ),
    )

    logger.info(f"Streaming audio data")

    # Create a BytesIO object to hold audio data
    audio_stream = BytesIO()

    # Write each chunk of audio data to the stream
    for chunk in response:
        if chunk:
            audio_stream.write(chunk)

    # Reset stream position to the beginning
    audio_stream.seek(0)

    # Return the stream for further use
    return audio_stream

def save_audio_file(audio_data):
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir='audio_files') as tmpfile:
        tmpfile.write(audio_data)
        return tmpfile.name
