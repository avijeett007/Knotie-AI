import os

from dotenv import load_dotenv

from ConversationCache.decorators import singleton


@singleton
class Configuration:
    CACHE_MANAGER_DB_FILE_PATH = False
    CACHE_MANAGER_MEDIA_DIR_PATH = False
    CACHE_MANAGER_CACHING_MEDIA = False
    CACHE_MANAGER_CACHING_AI_RESPONSES = False
    CACHE_MANAGER_CONNECTION_POOL_SIZE = False
    OPENAI_FINE_TUNED_MODEL_ID = False

    def __init__(self) -> None:
        super().__init__()
        load_dotenv()
        self.OPENAI_FINE_TUNED_MODEL_ID = os.getenv('OPENAI_FINE_TUNED_MODEL_ID', False)
        self.CACHE_MANAGER_CONNECTION_POOL_SIZE = os.getenv('CACHE_MANAGER_CONNECTION_POOL_SIZE', 10)
        self.CACHE_MANAGER_DB_FILE_PATH = os.getenv('CACHE_MANAGER_DB_FILE_PATH', False)
        self.CACHE_MANAGER_MEDIA_DIR_PATH = os.getenv('CACHE_MANAGER_MEDIA_DIR_PATH', False)
        self.CACHE_MANAGER_CACHING_MEDIA = os.getenv('CACHE_MANAGER_CACHING_MEDIA', 'FALSE').upper() == 'TRUE'
        self.CACHE_MANAGER_CACHING_AI_RESPONSES = os.getenv('CACHE_MANAGER_CACHING_AI_RESPONSES',
                                                            'FALSE').upper() == 'TRUE'

        # Validations
        if self.CACHE_MANAGER_CACHING_AI_RESPONSES and self.CACHE_MANAGER_DB_FILE_PATH is False:
            raise ValueError("CACHE_MANAGER_DB_FILE_PATH must be defined in ENV")

        if self.CACHE_MANAGER_CACHING_MEDIA and self.CACHE_MANAGER_MEDIA_DIR_PATH is False:
            raise ValueError("CACHE_MANAGER_MEDIA_DIR_PATH must be defined in ENV")
