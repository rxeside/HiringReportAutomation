import asyncio
import json
import logging
import os
from typing import Any, Dict

from dotenv import load_dotenv
from huntflow_api_client.tokens.proxy import AbstractTokenProxy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

TOKEN_FILE_PATH = "cache/tokens.json"


class FileTokenProxy(AbstractTokenProxy):
    def __init__(self):
        self._access_token: str = ""
        self._refresh_token: str = ""
        self._update_lock = asyncio.Lock()
        self._is_updated = False
        self._load_initial_tokens()

    def _load_initial_tokens(self) -> None:
        try:
            with open(TOKEN_FILE_PATH, 'r') as f:
                tokens = json.load(f)
                self._access_token = tokens.get("HUNTFLOW_API_TOKEN", "")
                self._refresh_token = tokens.get("HUNTFLOW_REFRESH_TOKEN", "")
                if self._access_token and self._refresh_token:
                    logging.info(f"Токены успешно загружены из файла {TOKEN_FILE_PATH}")
                    return
        except (FileNotFoundError, KeyError, json.JSONDecodeError):
            pass

        logging.warning(f"Токены не найдены/некорректны в {TOKEN_FILE_PATH}. Загрузка из .env...")
        self._access_token = os.getenv("HUNTFLOW_API_TOKEN", "")
        self._refresh_token = os.getenv("HUNTFLOW_REFRESH_TOKEN", "")
        if self._access_token:
            logging.info("Токены успешно загружены из .env файла.")

    def get_access_token(self) -> str:
        return self._access_token

    async def get_auth_header(self) -> Dict[str, str]:
        self._is_updated = False
        return {"Authorization": f"Bearer {self._access_token}"}

    async def get_refresh_data(self) -> Dict[str, str]:
        return {"refresh_token": self._refresh_token}


    async def update(self, data: Dict[str, Any]) -> None:
        async with self._update_lock:
            if data["access_token"] == self._access_token:
                logging.warning("Попытка обновить токен на тот же самый. Пропуск.")
                return

            new_access_token = data["access_token"]
            new_refresh_token = data["refresh_token"]

            logging.critical("=" * 60)
            logging.critical("ПОЛУЧЕНА НОВАЯ ПАРА ТОКЕНОВ ОТ СЕРВЕРА HUNTFLOW")
            logging.critical(f"НОВЫЙ ACCESS TOKEN: {new_access_token}")
            logging.critical(f"НОВЫЙ REFRESH TOKEN: {new_refresh_token}")
            logging.critical("СКОПИРУЙТЕ ЭТИ ТОКЕНЫ В НАДЕЖНОЕ МЕСТО ПРЯМО СЕЙЧАС!")
            logging.critical("=" * 60)

            try:
                os.makedirs(os.path.dirname(TOKEN_FILE_PATH), exist_ok=True)
                with open(TOKEN_FILE_PATH, 'w') as f:
                    json.dump({
                        "HUNTFLOW_API_TOKEN": new_access_token,
                        "HUNTFLOW_REFRESH_TOKEN": new_refresh_token
                    }, f, indent=4)

                logging.info(f"Токены ОБНОВЛЕНЫ и СИНХРОННО СОХРАНЕНЫ в {TOKEN_FILE_PATH}")

            except Exception as e:
                logging.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось сохранить токены на диск: {e}")
                raise

            self._access_token = new_access_token
            self._refresh_token = new_refresh_token
            self._is_updated = True


    async def is_updated(self) -> bool:
        return self._is_updated

    async def lock_for_update(self) -> bool:
        return await self._update_lock.acquire()

    async def release_lock(self) -> None:
        self._update_lock.release()


token_proxy = FileTokenProxy()