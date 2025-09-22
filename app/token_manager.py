import asyncio
import json
import logging
import os
from typing import Any, Dict

import aiofiles
from dotenv import load_dotenv
from huntflow_api_client.tokens.proxy import AbstractTokenProxy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

TOKEN_FILE_PATH = "cache/tokens.json"


class FileTokenProxy(AbstractTokenProxy):
    def __init__(self):
        self._access_token: str = ""
        self._refresh_token: str = ""
        self._lock = asyncio.Lock()
        self._is_updated = False
        self._load_initial_tokens()

    def _load_initial_tokens(self) -> None:
        try:
            with open(TOKEN_FILE_PATH, 'r') as f:
                tokens = json.load(f)
                self._access_token = tokens["HUNTFLOW_API_TOKEN"]
                self._refresh_token = tokens["HUNTFLOW_REFRESH_TOKEN"]
                logging.info(f"Токены успешно загружены из файла {TOKEN_FILE_PATH}")
                return
        except (FileNotFoundError, KeyError):
            logging.warning(f"{TOKEN_FILE_PATH} не найден. Загрузка из .env...")
            self._access_token = os.getenv("HUNTFLOW_API_TOKEN")
            self._refresh_token = os.getenv("HUNTFLOW_REFRESH_TOKEN")
            if self._access_token:
                logging.info("Токены успешно загружены из .env файла.")

    def get_access_token(self) -> str:
        return self._access_token

    async def get_auth_header(self) -> Dict[str, str]:
        async with self._lock:
            self._is_updated = False
            return {"Authorization": f"Bearer {self._access_token}"}

    async def update(self, data: Dict[str, Any]) -> None:
        async with self._lock:
            self._access_token = data["access_token"]
            self._refresh_token = data["refresh_token"]
            self._is_updated = True

            logging.info(f"Токены успешно обновлены. Сохранение в {TOKEN_FILE_PATH}...")
            new_tokens = {
                "HUNTFLOW_API_TOKEN": self._access_token,
                "HUNTFLOW_REFRESH_TOKEN": self._refresh_token
            }
            try:
                os.makedirs(os.path.dirname(TOKEN_FILE_PATH), exist_ok=True)
                async with aiofiles.open(TOKEN_FILE_PATH, mode='w') as f:
                    await f.write(json.dumps(new_tokens, indent=4))
                logging.info(f"Новые токены СОХРАНЕНЫ в {TOKEN_FILE_PATH}")
            except Exception as e:
                logging.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось сохранить токены: {e}")

    async def get_refresh_data(self) -> Dict[str, str]:
        return {"refresh_token": self._refresh_token}

    async def is_updated(self) -> bool:
        return self._is_updated

    async def lock_for_update(self) -> bool:
        await self._lock.acquire()
        return True

    async def release_lock(self) -> None:
        self._lock.release()


token_proxy = FileTokenProxy()