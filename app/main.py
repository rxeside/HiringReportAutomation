import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from .analytics_engine import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI(title="Hiring Report Dashboard 2.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
async def startup_event():
    logging.info("Загрузка данных в аналитический движок...")
    engine.load_data()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/analytics")
async def get_analytics(
        start_date: str = Query(..., description="YYYY-MM-DD"),
        end_date: str = Query(..., description="YYYY-MM-DD"),
        vacancies: Optional[List[str]] = Query(None),
        recruiters: Optional[List[str]] = Query(None)
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
            recruiter_filter=recruiters
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
