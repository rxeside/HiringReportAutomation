import logging
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Query, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from .analytics_engine import engine
from . import cache_manager
from .token_manager import token_proxy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI(title="Hiring Report Dashboard 2.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
async def startup_event():
    logging.info("Загрузка данных в аналитический движок...")
    await cache_manager.load_cache()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/analytics")
async def get_analytics(
        start_date: str = Query(..., description="YYYY-MM-DD"),
        end_date: str = Query(..., description="YYYY-MM-DD"),
        vacancies: Optional[List[str]] = Query(None),
        recruiters: Optional[List[str]] = Query(None),
        states: Optional[List[str]] = Query(None)
):
    """
    Основной метод API. Принимает фильтры, возвращает JSON со всей статистикой.
    """
    try:
        s_date = datetime.strptime(start_date, "%Y-%m-%d")
        e_date = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

        stats = engine.get_filtered_stats(
            start_date=s_date,
            end_date=e_date,
            vacancy_filter=vacancies,
            recruiter_filter=recruiters,
            state_filter=states
        )
        return stats
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD"}


@app.get("/api/filters")
async def get_filters_data():
    """
    Возвращает список доступных вакансий и рекрутеров для заполнения селектов на фронте
    """
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
    """Запускает фоновый парсинг Huntflow"""
    if not token_proxy._access_token:
        return JSONResponse(status_code=403, content={"message": "Токен API не задан. Проверьте .env"})

    if cache_manager.get_update_status():
        return JSONResponse(
            status_code=409,
            content={"message": "Обновление уже выполняется."}
        )

    logging.info("Запрос на принудительное обновление отчета.")
    background_tasks.add_task(cache_manager.update_cached_data)

    return {"message": "Обновление запущено в фоновом режиме."}