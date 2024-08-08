import os.path
import sqlite3

from ConversationCache.decorators import singleton
from ConversationCache.environment import Configuration


@singleton
class CacheManager:
    configuration = Configuration()
    connection = None

    def __init__(self) -> None:
        super().__init__()
        if self.configuration.CACHE_MANAGER_CACHING_MEDIA:
            self._create_media_folder()
        if self.configuration.CACHE_MANAGER_CACHING_AI_RESPONSES:
            self.connection = sqlite3.connect(self.configuration.CACHE_MANAGER_DB_FILE_PATH)
            self._create_database()

    def _create_database(self):
        cursor = self.connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS queries_and_responses (
                id INTEGER PRIMARY KEY,
                user_input TEXT NOT NULL UNIQUE,
                agent_output TEXT NOT NULL,
                media_temp_file_path VARCHAR(255) NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS queries_and_responses_fts USING fts5(user_input, agent_output, media_temp_file_path)
        ''')
        self.connection.commit()
        cursor.close()

        self._sync_fts()

    def put(self, user_input: str, agent_output: str, media_temp_file_path: str = ""):
        cursor = self.connection.cursor()

        cursor.execute('''
            INSERT INTO queries_and_responses (user_input, agent_output, media_temp_file_path)
                VALUES (?, ?, ?)
        ''', (user_input, agent_output, media_temp_file_path))
        self.connection.commit()
        cursor.close()
        self._sync_fts()

    def _sync_fts(self):
        cursor = self.connection.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO queries_and_responses_fts (rowid, user_input, agent_output, media_temp_file_path)
            SELECT id, user_input, agent_output, media_temp_file_path FROM queries_and_responses
        ''')

        self.connection.commit()
        cursor.close()

    def get(self, user_input: str):
        cursor = self.connection.cursor()

        cursor.execute('''
            SELECT * FROM queries_and_responses WHERE user_input=?
        ''', (user_input,))
        result = cursor.fetchone()
        cursor.close()
        return result

    def search(self, query: str):
        cursor = self.connection.cursor()

        cursor.execute('''
            SELECT user_input, agent_output, media_temp_file_path
            FROM queries_and_responses_fts
            WHERE queries_and_responses_fts MATCH ?
            LIMIT 1
        ''', (query,))

        result = cursor.fetchone()
        cursor.close()
        return result

    def __del__(self):
        if self.connection is not None:
            self.connection.close()

    def _create_media_folder(self):
        if not os.path.isdir(self.configuration.CACHE_MANAGER_MEDIA_DIR_PATH):
            os.mkdir(self.configuration.CACHE_MANAGER_MEDIA_DIR_PATH)

    def _create_media_file_temp_name(self):
        pass
