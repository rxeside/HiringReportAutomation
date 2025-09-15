import os
from dotenv import load_dotenv

load_dotenv()

HUNTFLOW_API_TOKEN = os.getenv("HUNTFLOW_API_TOKEN")

CACHE_FILE_PATH = os.getenv("CACHE_FILE_PATH", "cache/report_cache.json")

UPDATE_INTERVAL_SECONDS = int(os.getenv("UPDATE_INTERVAL_SECONDS", 3600))