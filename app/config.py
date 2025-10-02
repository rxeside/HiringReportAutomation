import os
from dotenv import load_dotenv

load_dotenv()

CACHE_FILE_PATH = os.getenv("CACHE_FILE_PATH", "cache/report_cache.json")