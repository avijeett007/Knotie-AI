import time
import logging
import redis
import json
import threading
import os
import random
from config import Config  # Import Config to access dynamic configuration
from audio_helpers import text_to_speech, save_audio_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the Redis client (placeholder)
redis_client = None

def get_redis_client():
    """Get or reinitialize the Redis client with the latest configuration."""
    global redis_client

    # Reload the configuration if there are any changes
    Config.reload_if_changed()

    # If Redis client is not initialized or URL has changed, reinitialize
    if not redis_client or redis_client.connection_pool.connection_kwargs['host'] != Config.REDIS_URL:
        redis_client = redis.Redis.from_url(Config.REDIS_URL, decode_responses=False)
        logger.info(f"Reinitialized Redis client with new URL: {Config.REDIS_URL}")
    
    return redis_client

def clean_response(unfiltered_response_text):
    # Check for specific substrings in the response text
    if "<END_OF_TURN>" in unfiltered_response_text or "<END_OF_CALL>" in unfiltered_response_text:
        # Remove specific substrings from the response text
        filtered_response_text = unfiltered_response_text.replace("<END_OF_TURN>", "").replace("<END_OF_CALL>", "")
        return filtered_response_text
    return unfiltered_response_text

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
    logger.info(f"Inside save message history")
    redis_client = get_redis_client()  # Get the latest Redis client
    redis_client.set(call_sid, json.dumps(message_history))

def get_message_history(call_sid):
    redis_client = get_redis_client()  # Get the latest Redis client
    message_history_json = redis_client.get(call_sid)
    return json.loads(message_history_json) if message_history_json else []

def process_elevenlabs_audio(initial_message):
    audio_data = text_to_speech(initial_message)
    audio_file_path = save_audio_file(audio_data)
    audio_filename = os.path.basename(audio_file_path)
    return audio_filename

def generate_diverse_confirmation(speech_result):
    """Generates a diverse confirmation message based on the user's input."""
    confirmation_prompts = [
        f"Just to make sure I heard you correctly, you said '{speech_result}'. Is that right?",
        f"I think I got that. You mentioned '{speech_result}'. Did I understand correctly?",
        f"Let me double-check. You said '{speech_result}', correct?",
        f"I want to ensure I understood you properly. You said '{speech_result}', right?",
        f"To avoid any misunderstanding, can you confirm you said '{speech_result}'?",
        f"I'd like to confirm something. Did you mean to say '{speech_result}'?",
        f"Before we continue, I just want to verify. You said '{speech_result}', didn't you?",
        f"I believe I heard '{speech_result}'. Am I on the right track?",
        f"Quick check - did you say '{speech_result}'?",
        f"I want to make sure we're on the same page. You mentioned '{speech_result}', correct?"
    ]
    
    return random.choice(confirmation_prompts)

