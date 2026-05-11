import asyncio
import json
import logging
import os
from typing import Any, Dict
import httpx
from dotenv import load_dotenv
from huntflow_api_client.tokens.proxy import AbstractTokenProxy

load_dotenv()
CACHE_DIR = "cache"
TOKEN_FILE_PATH = os.path.join(CACHE_DIR, "tokens.json")
REFRESH_URL = "https://api.huntflow.ru/v2/token/refresh"


class FileTokenProxy(AbstractTokenProxy):
    def __init__(self):
        self._access_token: str = ""
        self._refresh_token: str = ""
        self._update_lock = asyncio.Lock()
        self._load_initial_tokens()

    def _load_initial_tokens(self) -> None:
        if os.path.exists(TOKEN_FILE_PATH):
            try:
                with open(TOKEN_FILE_PATH, 'r') as f:
                    data = json.load(f)
                    self._access_token = data.get("access_token") or data.get("HUNTFLOW_API_TOKEN", "")
                    self._refresh_token = data.get("refresh_token") or data.get("HUNTFLOW_REFRESH_TOKEN", "")
                    if self._access_token and self._refresh_token:
                        logging.info("✅ Токены загружены из tokens.json")
                        return
            except Exception as e:
                logging.error(f"Ошибка чтения файла токенов: {e}")

        self._access_token = os.getenv("HUNTFLOW_API_TOKEN") or os.getenv("HUNTFLOW_ACCESS_TOKEN", "")
        self._refresh_token = os.getenv("HUNTFLOW_REFRESH_TOKEN", "")
        logging.info("⚠️ Токены загружены из .env")

    async def get_auth_header(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    async def get_refresh_data(self) -> Dict[str, str]:
        return {"refresh_token": self._refresh_token}

    async def refresh_tokens_manually(self) -> bool:
        async with self._update_lock:
            logging.warning("🔄 Запуск автоматического обновления токена...")
            if not self._refresh_token:
                return False

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        REFRESH_URL,
                        json={"refresh_token": self._refresh_token},
                        headers={"Content-Type": "application/json"}
                    )

                if response.status_code == 200:
                    data = response.json()
                    self._access_token = data["access_token"]
                    self._refresh_token = data["refresh_token"]

                    os.makedirs(CACHE_DIR, exist_ok=True)
                    with open(TOKEN_FILE_PATH, 'w') as f:
                        json.dump({
                            "access_token": self._access_token,
                            "refresh_token": self._refresh_token
                        }, f, indent=4)

                    logging.critical("✅ ТОКЕНЫ УСПЕШНО ОБНОВЛЕНЫ И СОХРАНЕНЫ В ФАЙЛ")
                    return True
                else:
                    logging.error(f"❌ Ошибка API при обновлении: {response.text}")
                    return False
            except Exception as e:
                logging.error(f"❌ Сетевая ошибка обновления: {e}")
                return False

    async def update(self, data: Dict[str, Any]) -> None:
        """Для совместимости с клиентом библиотеки"""
        self._access_token = data.get("access_token", self._access_token)
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        with open(TOKEN_FILE_PATH, 'w') as f:
            json.dump({"access_token": self._access_token, "refresh_token": self._refresh_token}, f)

    async def is_updated(self) -> bool:
        return True

    async def lock_for_update(self) -> bool:
        return await self._update_lock.acquire()

    async def release_lock(self) -> None:
        self._update_lock.release()


token_proxy = FileTokenProxy()