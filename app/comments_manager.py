import json
import asyncio
import os

import aiofiles
import logging
from . import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

_all_comments = {}
_comments_lock = asyncio.Lock()
COMMENTS_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'comments.json')


async def load_comments():
    global _all_comments
    try:
        if not os.path.exists(COMMENTS_FILE_PATH):
            logging.warning(f"Файл комментариев {COMMENTS_FILE_PATH} не найден. Создаю пустой.")
            async with aiofiles.open(COMMENTS_FILE_PATH, mode='w', encoding='utf-8') as f:
                await f.write(json.dumps({}))
            _all_comments = {}
            return

        async with aiofiles.open(COMMENTS_FILE_PATH, mode='r', encoding='utf-8') as f:
            content = await f.read()
            _all_comments = json.loads(content)
            logging.info(f"Комментарии успешно загружены из {COMMENTS_FILE_PATH}.")
    except json.JSONDecodeError:
        logging.error(f"Ошибка декодирования JSON в файле {COMMENTS_FILE_PATH}. Комментарии сброшены.")
        _all_comments = {}
    except Exception as e:
        logging.error(f"Неожиданная ошибка при загрузке комментариев: {e}")
        _all_comments = {}

async def save_comments():
    async with _comments_lock:
        try:
            async with aiofiles.open(COMMENTS_FILE_PATH, mode='w', encoding='utf-8') as f:
                await f.write(json.dumps(_all_comments, ensure_ascii=False, indent=4))
                logging.info(f"Комментарии успешно сохранены в {COMMENTS_FILE_PATH}.")
        except Exception as e:
            logging.error(f"Ошибка при сохранении комментариев в {COMMENTS_FILE_PATH}: {e}")

async def get_all_comments():
    async with _comments_lock:
        return _all_comments.copy()

async def update_comment(vacancy_name: str, comment: str):
    async with _comments_lock:
        _all_comments[vacancy_name] = comment
        await save_comments()
        logging.info(f"Комментарий для вакансии '{vacancy_name}' обновлен.")