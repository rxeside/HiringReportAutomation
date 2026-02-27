import asyncio
import json
import logging
import os
from datetime import datetime, timezone
import aiofiles

from . import config, report_generator
from .analytics_engine import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

_update_lock = asyncio.Lock()
_is_updating = False


async def load_cache() -> None:
    logging.info("Инициализация кэша и загрузка в Pandas...")
    engine.load_data()


async def update_cached_data() -> None:
    global _is_updating
    if _update_lock.locked():
        logging.info("Обновление уже идет. Пропуск.")
        return

    async with _update_lock:
        _is_updating = True
        logging.info(">>> Начало загрузки реальных данных из API Huntflow...")
        try:
            fetched_data = await report_generator.generate_raw_analytics_data()

            if fetched_data:
                fetched_data["last_updated"] = datetime.now(timezone.utc).isoformat()

                os.makedirs(os.path.dirname(config.CACHE_FILE_PATH), exist_ok=True)

                async with aiofiles.open(config.CACHE_FILE_PATH, mode='w', encoding='utf-8') as f:
                    await f.write(json.dumps(fetched_data, ensure_ascii=False, indent=4))

                logging.info(f"Кэш успешно сохранен в {config.CACHE_FILE_PATH}.")

                engine.load_data()
            else:
                logging.warning("Сборщик вернул None, данные не обновлены.")
        except Exception as e:
            import traceback
            logging.error(f"Ошибка обновления: {e}\n{traceback.format_exc()}")
        finally:
            _is_updating = False
            logging.info("<<< Процесс обновления данных завершен.")


def get_update_status() -> bool:
    return _is_updating