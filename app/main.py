import logging
import traceback
from datetime import datetime
from typing import List, Optional

import pytz
from fastapi import FastAPI, Query, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .analytics_engine import engine
from . import cache_manager
from .token_manager import token_proxy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI(title="Hiring Report Dashboard 2.0")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

scheduler = AsyncIOScheduler()

async def scheduled_report_update():
    logging.info("⏰ [CRON] Проверка токенов перед обновлением...")
    is_authorized = await token_proxy.refresh_tokens_manually()

    if is_authorized:
        logging.info("🚀 [CRON] Начинаю сбор данных...")
        await cache_manager.update_cached_data()
        logging.info("✅ [CRON] Отчет успешно обновлен.")
    else:
        if await token_proxy.check_token_validity():
            await cache_manager.update_cached_data()
        else:
            logging.error("❌ [CRON] Нет доступа к API. Обновление невозможно.")


@app.on_event("startup")
async def startup_event():
    """Действия при старте сервера"""
    logging.info("🚀 Запуск сервера. Загрузка данных в аналитический движок...")

    await cache_manager.load_cache()

    moscow_tz = pytz.timezone('Europe/Moscow')
    scheduler.add_job(
        scheduled_report_update,
        CronTrigger(hour=0, minute=0, timezone=moscow_tz),
        id="daily_sync",
        replace_existing=True
    )

    scheduler.start()
    logging.info("🛠 Планировщик запущен: обновление ежедневно в 00:00 МСК")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request}
    )


@app.get("/api/analytics")
async def get_analytics(
        start_date: str = Query(..., description="YYYY-MM-DD"),
        end_date: str = Query(..., description="YYYY-MM-DD"),
        vacancies: Optional[List[str]] = Query(None),
        recruiters: Optional[List[str]] = Query(None),
        states: Optional[List[str]] = Query(None)
):
    """API для получения данных аналитики с фильтрами"""
    try:
        s_date = datetime.strptime(start_date, "%Y-%m-%d")
        e_date = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid date format: {str(e)}"})

    try:
        stats = engine.get_filtered_stats(
            start_date=s_date,
            end_date=e_date,
            vacancy_filter=vacancies,
            recruiter_filter=recruiters,
            state_filter=states
        )
        return stats
    except Exception as e:
        logging.error(f"Engine Error: {str(e)}")
        logging.error(traceback.format_exc())
        return JSONResponse(status_code=500, content={"error": f"Internal Calculation Error: {str(e)}"})

@app.get("/api/filters")
async def get_filters_data():
    """Возвращает списки для выпадающих меню фильтров"""
    return {
        "vacancies": sorted(engine.df['vacancy'].unique().tolist()) if not engine.df.empty else [],
        "coworkers": engine.coworkers
    }


@app.get("/status")
async def get_status():
    """Отдает статус текущего фонового обновления"""
    last_upd = engine.last_updated
    if last_upd:
        try:
            dt = datetime.fromisoformat(last_upd)
            last_upd_str = dt.strftime('%d.%m.%Y %H:%M:%S')
        except:
            last_upd_str = str(last_upd)
    else:
        last_upd_str = "Никогда"

    return {
        "is_updating": cache_manager.get_update_status(),
        "last_updated_str": last_upd_str
    }


@app.post("/refresh-report")
async def refresh_report_endpoint(background_tasks: BackgroundTasks):
    """Ручной запуск обновления через кнопку в интерфейсе"""
    if not token_proxy.get_access_token():
        return JSONResponse(status_code=403, content={"message": "Токен API не задан. Проверьте .env или tokens.json"})

    if cache_manager.get_update_status():
        return JSONResponse(
            status_code=409,
            content={"message": "Обновление уже выполняется."}
        )

    logging.info("Запрос на принудительное обновление отчета.")
    background_tasks.add_task(scheduled_report_update)

    return {"message": "Обновление запущено в фоновом режиме."}