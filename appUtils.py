import time
import logging
import redis
import json
import threading
import os
from audio_helpers import text_to_speech, save_audio_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

def clean_response(unfiltered_response_text):
    # Remove specific substrings from the response text
    filtered_response_text = unfiltered_response_text.replace("<END_OF_TURN>", "").replace("<END_OF_CALL>", "")
    return filtered_response_text

def delayed_delete(filename, delay=5):
    """ Delete the file after a specified delay in seconds. """
    def attempt_delete():
        time.sleep(delay)
        try:
            os.remove(filename)
            logger.info(f"Successfully deleted temporary audio file: {filename}")
        except Exception as error:
            logger.error(f"Error deleting temporary audio file: {filename} - {error}")

    thread = threading.Thread(target=attempt_delete)
    thread.start()

def save_message_history(call_sid, message_history):
    redis_client.set(call_sid, json.dumps(message_history))

def get_message_history(call_sid):
    message_history_json = redis_client.get(call_sid)
    return json.loads(message_history_json) if message_history_json else []

def process_elevenlabs_audio(initial_message):
    audio_data = text_to_speech(initial_message)
    audio_file_path = save_audio_file(audio_data)
    audio_filename = os.path.basename(audio_file_path)
    return audio_filename