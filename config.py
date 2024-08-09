import os
import json
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Static config from environment variables
    SECRET_KEY = os.getenv('SECRET_KEY')

    @staticmethod
    def load_dynamic_config():
        if os.path.exists('config.json'):
            with open('config.json') as config_file:
                return json.load(config_file)
        return {}

    @classmethod
    def initialize(cls):
        cls.dynamic_config = cls.load_dynamic_config()
        cls.update_dynamic_config()

    @classmethod
    def update_dynamic_config(cls):
        dynamic_config = cls.load_dynamic_config()
        cls.COMPANY_NAME = dynamic_config.get('COMPANY_NAME', 'Default Company Name')
        cls.COMPANY_BUSINESS = dynamic_config.get('COMPANY_BUSINESS', 'Default Company Business')
        cls.COMPANY_PRODUCTS_SERVICES = dynamic_config.get('COMPANY_PRODUCTS_SERVICES', 'Default Products Services')
        cls.CONVERSATION_PURPOSE = dynamic_config.get('CONVERSATION_PURPOSE', 'Default Conversation Purpose')
        cls.AISALESAGENT_NAME = dynamic_config.get('AISALESAGENT_NAME', 'Default Agent Name')
        cls.AI_API_KEY = dynamic_config.get('AI_API_KEY', 'Default AI API Key')
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

Config.initialize()

