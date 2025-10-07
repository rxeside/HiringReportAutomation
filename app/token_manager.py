import asyncio
import json
import logging
import os
from typing import Any, Dict
import httpx

from dotenv import load_dotenv
from huntflow_api_client.tokens.proxy import AbstractTokenProxy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

CACHE_DIR = "cache"
TOKEN_FILE_PATH = os.path.join(CACHE_DIR, "tokens.json")
TOKEN_FILE_TMP = os.path.join(CACHE_DIR, "tokens.json.tmp")
TOKEN_FILE_BAK = os.path.join(CACHE_DIR, "tokens.json.bak")

REFRESH_URL = "https://api.huntflow.ru/v2/token/refresh"


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
        self._access_token = os.getenv("HUNTFLOW_API_TOKEN", "") or os.getenv("HUNTFLOW_ACCESS_TOKEN", "")
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

    async def refresh_tokens_manually(self) -> bool:
        logging.warning(f"Запускаю ручное обновление токена...")

        if not self._refresh_token:
            logging.critical("КРИТИЧЕСКАЯ ОШИБКА: Refresh token отсутствует. Обновление невозможно.")
            return False

        payload = {"refresh_token": self._refresh_token}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(REFRESH_URL, json=payload)

            if response.status_code == 200:
                new_tokens = response.json()
                await self.update(new_tokens)
                return True
            else:
                logging.critical("--- ОШИБКА ОБНОВЛЕНИЯ ТОКЕНА! ---")
                logging.critical(f"Статус-код: {response.status_code}")
                logging.critical(f"Ответ сервера: {response.text}")
                return False
        except httpx.RequestError as e:
            logging.critical(f"--- СЕТЕВАЯ ОШИБКА ПРИ ОБНОВЛЕНИИ ТОКЕНА: {e} ---")
            return False

    async def update(self, data: Dict[str, Any]) -> None:
        async with self._update_lock:
            new_access_token = data.get("access_token")
            new_refresh_token = data.get("refresh_token")

            if not new_access_token or not new_refresh_token:
                logging.critical(
                    "ОШИБКА: API вернул неполные данные! Сохранение отменено. Данные: %s", data)
                return

            logging.critical("=" * 80)
            logging.critical("!!! ПОЛУЧЕНЫ НОВЫЕ ТОКЕНЫ. НАЧИНАЮ ОБРАБОТКУ. !!!")
            logging.critical(f"НОВЫЙ ACCESS TOKEN: {new_access_token}")
            logging.critical(f"НОВЫЙ REFRESH TOKEN: {new_refresh_token}")
            logging.critical("=" * 80)

            try:
                os.makedirs(CACHE_DIR, exist_ok=True)
                with open(TOKEN_FILE_TMP, 'w') as f:
                    json.dump({
                        "HUNTFLOW_API_TOKEN": new_access_token,
                        "HUNTFLOW_REFRESH_TOKEN": new_refresh_token
                    }, f, indent=4)
                if os.path.exists(TOKEN_FILE_PATH):
                    os.rename(TOKEN_FILE_PATH, TOKEN_FILE_BAK)
                os.rename(TOKEN_FILE_TMP, TOKEN_FILE_PATH)
                logging.info(f"Токены успешно и безопасно сохранены в {TOKEN_FILE_PATH}")
            except Exception as e:
                logging.critical(f"КРИТИЧЕСКАЯ ОШИБКА ПРИ СОХРАНЕНИИ ТОКЕНОВ НА ДИСК: {e}")
                return

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