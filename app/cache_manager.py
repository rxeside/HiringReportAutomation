import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import aiofiles
from . import config, report_generator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

_cached_data: Dict[str, Any] = {"vacancies": [], "coworkers": {}, "last_updated": None}
_cache_lock = asyncio.Lock()


async def load_cache() -> None:
    global _cached_data
    if not config.CACHE_FILE_PATH:
        logging.error("CACHE_FILE_PATH не определен. Кэш не будет загружен.")
        return
    try:
        async with aiofiles.open(config.CACHE_FILE_PATH, mode='r', encoding='utf-8') as f:
            content = await f.read()
            loaded_data = json.loads(content)
            _cached_data = loaded_data

            last_updated_str = _cached_data.get("last_updated")
            if last_updated_str and isinstance(last_updated_str, str):
                _cached_data["last_updated"] = datetime.fromisoformat(last_updated_str)

            logging.info(
                f"Кэш успешно загружен. Вакансий: {len(get_cached_vacancies())}. Последнее обновление: {_cached_data.get('last_updated')}")
    except FileNotFoundError:
        logging.warning(f"Файл кэша {config.CACHE_FILE_PATH} не найден. Инициализирован пустой кэш.")
        _cached_data = {"vacancies": [], "coworkers": {}, "last_updated": None}
    except Exception:
        logging.error(f"Ошибка при чтении или парсинге кэша {config.CACHE_FILE_PATH}. Кэш сброшен.")
        _cached_data = {"vacancies": [], "coworkers": {}, "last_updated": None}


async def _save_cache_internal() -> None:
    if not config.CACHE_FILE_PATH:
        logging.error("CACHE_FILE_PATH не определен. Кэш не будет сохранен.")
        return

    try:
        import os
        cache_dir = os.path.dirname(config.CACHE_FILE_PATH)
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
    except Exception as e:
        logging.error(f"Не удалось создать директорию для кэша {cache_dir}: {e}")
        return

    data_to_save = _cached_data.copy()
    if isinstance(data_to_save.get("last_updated"), datetime):
        data_to_save["last_updated"] = data_to_save["last_updated"].isoformat()

    try:
        async with aiofiles.open(config.CACHE_FILE_PATH, mode='w', encoding='utf-8') as f:
            await f.write(json.dumps(data_to_save, ensure_ascii=False, indent=4))
        logging.info(f"Кэш успешно сохранен в {config.CACHE_FILE_PATH}.")
    except Exception as e:
        logging.error(f"Ошибка при сохранении кэша: {e}", exc_info=True)


async def update_cached_data(token: str) -> None:
    try:
        fetched_data = await report_generator.fetch_and_process_data(token)
        async with _cache_lock:
            if fetched_data is not None:
                existing_comments = {
                    row.get('название вакансии'): row.get('комментарий', '')
                    for row in _cached_data.get("vacancies", []) if row.get('название вакансии')
                }
                new_vacancies = fetched_data.get("vacancies", [])
                for row in new_vacancies:
                    vacancy_name = row.get('название вакансии')
                    row['комментарий'] = existing_comments.get(vacancy_name, "")

                _cached_data["vacancies"] = new_vacancies
                _cached_data["coworkers"] = fetched_data.get("coworkers", {})
                _cached_data["last_updated"] = datetime.now(timezone.utc)

                await _save_cache_internal()
                logging.info("Кэшированные данные успешно обновлены и сохранены.")
            else:
                logging.warning("Сборщик данных вернул None, кэш не будет обновлен.")
    except Exception as e:
        import traceback
        logging.error(f"КРИТИЧЕСКАЯ ОШИБКА во время обновления кэша: {e}")
        logging.error(traceback.format_exc())


async def update_comment(vacancy_name: str, comment: str) -> bool:
    found = False
    async with _cache_lock:
        for row in _cached_data.get("vacancies", []):
            if row.get("название вакансии") == vacancy_name:
                row["комментарий"] = comment
                found = True
                break
        if found:
            _cached_data["last_updated"] = datetime.now(timezone.utc)
            await _save_cache_internal()
            logging.info(f"Комментарий для '{vacancy_name}' обновлен в кэше.")
    if not found:
        logging.warning(f"Попытка обновить комментарий для несуществующей вакансии: '{vacancy_name}'")
    return found


def get_last_updated_time_msk() -> Optional[datetime]:
    last_updated = _cached_data.get("last_updated")
    if isinstance(last_updated, datetime):
        return last_updated.astimezone(timezone(timedelta(hours=3)))
    return None


async def get_cached_vacancies() -> List[Dict[str, Any]]:
    return _cached_data.get("vacancies", [])


async def get_cached_coworkers() -> Dict[int, str]:
    return _cached_data.get("coworkers", {})