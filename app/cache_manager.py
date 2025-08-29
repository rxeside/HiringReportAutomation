import json
import asyncio
from datetime import datetime, timezone, timedelta
import logging
import aiofiles
from . import config, report_generator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

_cached_data = None
_last_updated = None
_cache_lock = asyncio.Lock()

async def load_cache():
    global _cached_data, _last_updated
    if not config.CACHE_FILE_PATH:
        logging.error("CACHE_FILE_PATH не задан в config.py")
        return

    try:
        async with aiofiles.open(config.CACHE_FILE_PATH, mode='r', encoding='utf-8') as f:
            content = await f.read()
            data = json.loads(content)
            _cached_data = data.get("report_data")
            _last_updated = datetime.fromisoformat(data.get("last_updated")) if data.get("last_updated") else None
            logging.info(f"Кэш успешно загружен из {config.CACHE_FILE_PATH}. Последнее обновление: {_last_updated}")
    except FileNotFoundError:
        logging.warning(f"Файл кэша {config.CACHE_FILE_PATH} не найден. Кэш пуст.")
    except json.JSONDecodeError:
        logging.error(f"Ошибка декодирования JSON в файле {config.CACHE_FILE_PATH}. Кэш пуст.")
        _cached_data = None
        _last_updated = None
    except Exception as e:
        logging.error(f"Неожиданная ошибка при загрузке кэша: {e}")
        _cached_data = None
        _last_updated = None


async def save_cache(data, last_updated):
    if not config.CACHE_FILE_PATH:
        logging.error("CACHE_FILE_PATH не задан в config.py. Кэш не будет сохранен.")
        return

    try:
        # Создаем директорию, если она не существует
        cache_dir = "/".join(config.CACHE_FILE_PATH.split("/")[:-1])
        if cache_dir:
            import os
            os.makedirs(cache_dir, exist_ok=True)

        async with aiofiles.open(config.CACHE_FILE_PATH, mode='w', encoding='utf-8') as f:
            cache_content = {
                "report_data": data,
                "last_updated": last_updated.isoformat() if last_updated else None
            }
            await f.write(json.dumps(cache_content, ensure_ascii=False, indent=4))
            logging.info(f"Кэш успешно сохранен в {config.CACHE_FILE_PATH}.")
    except Exception as e:
        logging.error(f"Ошибка при сохранении кэша в {config.CACHE_FILE_PATH}: {e}")

async def update_cached_data(token: str):
    global _cached_data, _last_updated
    async with _cache_lock:
        logging.info("Начинаю обновление кэшированных данных...")
        new_data = await report_generator.fetch_and_process_data(token, {})
        if new_data is not None:
            _cached_data = new_data
            _last_updated = datetime.now(timezone.utc)
            await save_cache(_cached_data, _last_updated)
            logging.info("Кэшированные данные успешно обновлены.")
        else:
            logging.warning("Не удалось обновить кэшированные данные. Использую старые.")
        return _cached_data

def get_last_updated_time_msk():
    if _last_updated:
        msk_offset = timedelta(hours=3)
        return _last_updated + msk_offset
    return None

async def get_cached_data():
    if _cached_data is None:
        logging.warning("Запрос к данным, но кэш пуст. Попытка загрузки...")
        return []
    return _cached_data

def get_last_updated_time():
    return _last_updated