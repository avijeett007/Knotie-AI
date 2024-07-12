import os
import json
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Load static config from environment variables
    SECRET_KEY = os.getenv('SECRET_KEY')

    # Load dynamic config from config.json
    @staticmethod
    def load_dynamic_config():
        if os.path.exists('config.json'):
            with open('config.json') as config_file:
                config_data = json.load(config_file)
                return config_data
        return {}

    # Initialize dynamic config
    dynamic_config = None

    @classmethod
    def initialize(cls):
        cls.dynamic_config = cls.load_dynamic_config()
        cls.COMPANY_NAME = cls.dynamic_config.get('COMPANY_NAME', 'Default Company Name')
        cls.COMPANY_BUSINESS = cls.dynamic_config.get('COMPANY_BUSINESS', 'Default Company Business')
        cls.COMPANY_PRODUCTS_SERVICES = cls.dynamic_config.get('COMPANY_PRODUCTS_SERVICES', 'Default Products Services')
        cls.CONVERSATION_PURPOSE = cls.dynamic_config.get('CONVERSATION_PURPOSE', 'Default Conversation Purpose')
        cls.AISALESAGENT_NAME = cls.dynamic_config.get('AISALESAGENT_NAME', 'Default Agent Name')
        cls.AI_API_KEY = cls.dynamic_config.get('AI_API_KEY', 'Default AI API Key')
        cls.WHICH_MODEL = cls.dynamic_config.get('WHICH_MODEL', 'Default Model')
        cls.OPENAI_BASE_URL = cls.dynamic_config.get('OPENAI_BASE_URL', 'https://api.default.com')
        cls.VOICE_MODE = cls.dynamic_config.get('VOICE_MODE', 'Default Voice Mode')
        cls.LLM_MODEL = cls.dynamic_config.get('LLM_MODEL', 'Default Model')
        cls.USE_LANGCHAIN_TOOL_CLASS = cls.dynamic_config.get('USE_LANGCHAIN_TOOL_CLASS', False)
        cls.AGENT_CUSTOM_INSTRUCTIONS = cls.dynamic_config.get('AGENT_CUSTOM_INSTRUCTIONS', 'Default Instructions')
        cls.TWILIO_ACCOUNT_SID = cls.dynamic_config.get('TWILIO_ACCOUNT_SID', 'Default Twilio SID')
        cls.TWILIO_AUTH_TOKEN = cls.dynamic_config.get('TWILIO_AUTH_TOKEN', 'Default Twilio Auth Token')
        cls.TWILIO_FROM_NUMBER = cls.dynamic_config.get('TWILIO_FROM_NUMBER', 'Default Twilio Number')
        cls.ELEVENLABS_API_KEY = cls.dynamic_config.get('ELEVENLABS_API_KEY', 'Default Eleven Labs API Key')
        cls.VOICE_ID = cls.dynamic_config.get('VOICE_ID', 'Default Voice ID')
        cls.APP_PUBLIC_URL = cls.dynamic_config.get('APP_PUBLIC_URL', 'https://default-url.com')
        cls.APP_PUBLIC_GATHER_URL = f"{cls.APP_PUBLIC_URL}/gather"
        cls.APP_PUBLIC_EVENT_URL = f"{cls.APP_PUBLIC_URL}/event"

# Initialize the dynamic config
Config.initialize()
