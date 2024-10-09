import os
import json
import base64
import sqlite3
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

class Config:
    # Static config from environment variables
    SECRET_KEY = os.getenv('SECRET_KEY')

    # Store the last loaded config timestamp
    last_loaded_timestamp = None

    @staticmethod
    def load_dynamic_config():
        # Load configuration from the SQLite database
        config_data = {}
        try:
            conn = sqlite3.connect('knotie.db')
            cursor = conn.cursor()
            cursor.execute('SELECT key, value FROM config')
            rows = cursor.fetchall()
            config_data = {row[0]: row[1] for row in rows}
        except sqlite3.Error as e:
            logger.error(f"Error loading config from database: {e}")
        finally:
            conn.close()
        return config_data

    @staticmethod
    def save_dynamic_config(config_data):
        # Save configuration to the SQLite database
        try:
            conn = sqlite3.connect('knotie.db')
            cursor = conn.cursor()
            for key, value in config_data.items():
                cursor.execute('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', (key, value))
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Error saving config to database: {e}")
        finally:
            conn.close()

    @classmethod
    def initialize(cls):
        cls.dynamic_config = cls.load_dynamic_config()
        cls.update_dynamic_config()

    @classmethod
    def reload_if_changed(cls):
        """Reload the configuration if the config data in the database has changed."""
        # You may implement a logic to check if the database entry has changed, if required.
        # For now, we'll just reload dynamically without a timestamp comparison
        cls.dynamic_config = cls.load_dynamic_config()
        cls.update_dynamic_config()
        logger.info("Configuration reloaded from database.")

    @classmethod
    def update_dynamic_config(cls):
        dynamic_config = cls.load_dynamic_config()
        cls.COMPANY_NAME = dynamic_config.get('COMPANY_NAME', 'Default Company Name')
        cls.COMPANY_BUSINESS = dynamic_config.get('COMPANY_BUSINESS', 'Default Company Business')
        cls.COMPANY_PRODUCTS_SERVICES = dynamic_config.get('COMPANY_PRODUCTS_SERVICES', 'Default Products Services')
        cls.CONVERSATION_PURPOSE = dynamic_config.get('CONVERSATION_PURPOSE', 'Default Conversation Purpose')
        cls.AISALESAGENT_NAME = dynamic_config.get('AISALESAGENT_NAME', 'Default Agent Name')
        cls.AI_API_KEY = dynamic_config.get('AI_API_KEY', 'Default AI API Key')
        cls.ENCRYPTION_KEY = dynamic_config.get('ENCRYPTION_KEY', 'Default Encryption Key')
        cls.WHICH_MODEL = dynamic_config.get('WHICH_MODEL', 'Default Model')
        cls.OPENAI_BASE_URL = dynamic_config.get('OPENAI_BASE_URL', 'https://api.default.com')
        cls.VOICE_MODE = dynamic_config.get('VOICE_MODE', 'Default Voice Mode')
        cls.LLM_MODEL = dynamic_config.get('LLM_MODEL', 'Default Model')
        cls.OPENAI_FINE_TUNED_MODEL_ID = dynamic_config.get('OPENAI_FINE_TUNED_MODEL_ID', 'gpt-3.5-turbo')
        cls.OPENAI_FINE_TUNED_TOOLS_MODEL_ID = dynamic_config.get('OPENAI_FINE_TUNED_TOOLS_MODEL_ID', 'gpt-3.5-turbo')
        cls.USE_LANGCHAIN_TOOL_CLASS = dynamic_config.get('USE_LANGCHAIN_TOOL_CLASS', False)
        cls.AGENT_CUSTOM_INSTRUCTIONS = dynamic_config.get('AGENT_CUSTOM_INSTRUCTIONS', 'Default Instructions')
        cls.TWILIO_ACCOUNT_SID = dynamic_config.get('TWILIO_ACCOUNT_SID', 'Default Twilio SID')
        cls.TWILIO_AUTH_TOKEN = dynamic_config.get('TWILIO_AUTH_TOKEN', 'Default Twilio Auth Token')
        cls.TWILIO_FROM_NUMBER = dynamic_config.get('TWILIO_FROM_NUMBER', 'Default Twilio Number')
        cls.ELEVENLABS_API_KEY = dynamic_config.get('ELEVENLABS_API_KEY', 'Default Eleven Labs API Key')
        cls.NGROK_AUTH_TOKEN = dynamic_config.get('NGROK_AUTH_TOKEN', 'NGROK Default Auth Token')
        cls.USE_NGROK = dynamic_config.get('USE_NGROK', 'true')
        cls.VOICE_ID = dynamic_config.get('VOICE_ID', 'Default Voice ID')
        cls.APP_PUBLIC_URL = dynamic_config.get('APP_PUBLIC_URL', 'https://default-url.com')
        cls.APP_PUBLIC_GATHER_URL = f"{cls.APP_PUBLIC_URL}/gather"
        cls.APP_PUBLIC_EVENT_URL = f"{cls.APP_PUBLIC_URL}/event"
        cls.CACHE_ENABLED = dynamic_config.get('CACHE_ENABLED', False)
        cls.REDIS_URL = dynamic_config.get('REDIS_URL', 'redis://redis:6379')  # Set default to local Redis

    @classmethod
    def validate_encryption_key(cls):
        if cls.ENCRYPTION_KEY and cls.ENCRYPTION_KEY != "Enter a strong ENCRYPTION_KEY":
            try:
                # Ensure the key is base64 url-safe encoded and 32 bytes long
                base64.urlsafe_b64decode(cls.ENCRYPTION_KEY)
                logger.info("ENCRYPTION_KEY is valid and set.")
            except Exception as e:
                logger.error("Invalid ENCRYPTION_KEY. It must be a 32-byte base64-encoded string.")
                cls.ENCRYPTION_KEY = None
        else:
            logger.warning("ENCRYPTION_KEY is not set or is invalid. Please ensure it is updated by the admin.")
            cls.ENCRYPTION_KEY = None

Config.initialize()
