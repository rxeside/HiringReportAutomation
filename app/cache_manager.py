import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import aiofiles
from . import config, report_generator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

_cached_data: Dict[str, Any] = {"vacancies": [], "coworkers": {}}
_last_updated: Optional[datetime] = None
_cache_lock = asyncio.Lock()


async def load_cache() -> None:
    global _cached_data, _last_updated
    if not config.CACHE_FILE_PATH:
        logging.error("CACHE_FILE_PATH не определен. Кэш не будет загружен.")
        return

    try:
        async with aiofiles.open(config.CACHE_FILE_PATH, mode='r', encoding='utf-8') as f:
            content = await f.read()
            data = json.loads(content)
            _cached_data = data.get("data", {"vacancies": [], "coworkers": {}})
            last_updated_str = data.get("last_updated")
            _last_updated = datetime.fromisoformat(last_updated_str) if last_updated_str else None
            logging.info(f"Кэш успешно загружен. Вакансий: {len(_cached_data.get('vacancies', []))}. Последнее обновление: {_last_updated}")
    except FileNotFoundError:
        logging.warning(f"Файл кэша {config.CACHE_FILE_PATH} не найден. Инициализирован пустой кэш.")
        _cached_data = {"vacancies": [], "coworkers": {}}
        _last_updated = None
    except (json.JSONDecodeError, TypeError):
        logging.error(f"Ошибка декодирования JSON в {config.CACHE_FILE_PATH}. Кэш сброшен.")
        _cached_data = {"vacancies": [], "coworkers": {}}
        _last_updated = None
    except Exception as e:
        logging.error(f"Неожиданная ошибка при загрузке кэша: {e}", exc_info=True)
        _cached_data = {"vacancies": [], "coworkers": {}}
        _last_updated = None


async def save_cache() -> None:
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

    async with _cache_lock:
        try:
            cache_content = {
                "data": _cached_data,
                "last_updated": _last_updated.isoformat() if _last_updated else None
            }
            async with aiofiles.open(config.CACHE_FILE_PATH, mode='w', encoding='utf-8') as f:
                await f.write(json.dumps(cache_content, ensure_ascii=False, indent=4))
            logging.info(f"Кэш успешно сохранен в {config.CACHE_FILE_PATH}.")
        except Exception as e:
            logging.error(f"Ошибка при сохранении кэша: {e}", exc_info=True)


async def update_cached_data(token: str) -> None:
    global _cached_data, _last_updated
    logging.info("Начинаю плановое обновление кэшированных данных...")

    async with _cache_lock:
        existing_comments = {
            row.get('название вакансии'): row.get('комментарий', '')
            for row in _cached_data.get("vacancies", []) if row.get('название вакансии')
        }

        fetched_data = await report_generator.fetch_and_process_data(token)

        if fetched_data and fetched_data.get("vacancies"):
            new_vacancies = fetched_data["vacancies"]
            for row in new_vacancies:
                vacancy_name = row.get('название вакансии')
                row['комментарий'] = existing_comments.get(vacancy_name, "")

            # ИЗМЕНЕНИЕ: обновляем обе части кэша
            _cached_data["vacancies"] = new_vacancies
            _cached_data["coworkers"] = fetched_data.get("coworkers", {})
            _last_updated = datetime.now(timezone.utc)
            await save_cache()
            logging.info("Кэшированные данные успешно обновлены и сохранены.")
        else:
            logging.warning("Не удалось получить новые данные от API. Используются старые данные.")


async def update_comment(vacancy_name: str, comment: str) -> bool:
    global _cached_data
    found = False
    async with _cache_lock:
        # ИЗМЕНЕНИЕ: ищем вакансию в списке вакансий
        for row in _cached_data.get("vacancies", []):
            if row.get("название вакансии") == vacancy_name:
                row["комментарий"] = comment
                found = True
                break
    if found:
        await save_cache()
        logging.info(f"Комментарий для '{vacancy_name}' обновлен в кэше.")
    else:
        logging.warning(f"Попытка обновить комментарий для несуществующей вакансии: '{vacancy_name}'")
    return found


def get_last_updated_time_msk() -> Optional[datetime]:
    if _last_updated:
        return _last_updated.astimezone(timezone(timedelta(hours=3)))
    return None


# ИЗМЕНЕНИЕ: Старую функцию get_cached_data() заменяем на две новые
async def get_cached_vacancies() -> List[Dict[str, Any]]:
    return _cached_data.get("vacancies", [])

async def get_cached_coworkers() -> Dict[int, str]:
    return _cached_data.get("coworkers", {})


def get_last_updated_time() -> Optional[datetime]:
    return _last_updated