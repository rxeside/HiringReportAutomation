import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from . import cache_manager, config, report_generator
from .token_manager import token_proxy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI(title="Hiring Report Dashboard", version="1.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
scheduler = AsyncIOScheduler()
class CommentUpdateRequest(BaseModel):
    vacancy_name: str
    comment: str


@app.on_event("startup")
async def startup_event():
    logging.info("Инициализация приложения...")
    await cache_manager.load_cache()

    if token_proxy.get_access_token():
        logging.info("Токен Huntflow успешно загружен.")
        cache_exists = bool(cache_manager.get_cached_vacancies())
        if not cache_exists:
            logging.info("Кэш пуст. Запускаю ПЕРВОЕ обновление (блокирующее)...")
            await cache_manager.update_cached_data()
        else:
            logging.info("Кэш найден. Запускаю ПЛАНОВОЕ обновление в фоновом режиме...")
            asyncio.create_task(cache_manager.update_cached_data())

        scheduler.add_job(
            cache_manager.update_cached_data, "interval",
            seconds=config.UPDATE_INTERVAL_SECONDS, id="update_report_job",
            replace_existing=True,
            next_run_time=datetime.now() + timedelta(seconds=config.UPDATE_INTERVAL_SECONDS)
        )
        scheduler.start()
        logging.info(f"Планировщик запущен. Следующее обновление через {config.UPDATE_INTERVAL_SECONDS} секунд.")
    else:
        logging.error("ВНИМАНИЕ: Токены HUNTFLOW не найдены. Проверьте .env или cache/tokens.json")
        logging.warning("Планировщик не запущен, т.к. токен API не предоставлен.")


@app.on_event("shutdown")
async def shutdown_event():
    logging.info("Остановка приложения...")
    if scheduler.running:
        scheduler.shutdown()
    logging.info("Планировщик остановлен.")


@app.get("/", response_class=HTMLResponse)
async def show_report_table(request: Request):
    report_data = cache_manager.get_cached_vacancies()
    coworkers = cache_manager.get_cached_coworkers()
    last_updated = cache_manager.get_last_updated_time_msk()
    headers = ["Название вакансии"] + report_generator.FUNNEL_STAGES_ORDER + ["Комментарий"]
    return templates.TemplateResponse("index.html", {
        "request": request,
        "headers": headers,
        "report_data": report_data,
        "last_updated": last_updated,
        "coworkers": coworkers
    })


@app.post("/update-comment", status_code=200)
async def update_comment_endpoint(request_data: CommentUpdateRequest):
    logging.info(f"Запрос на обновление комментария для: '{request_data.vacancy_name}'")
    success = await cache_manager.update_comment(
        request_data.vacancy_name,
        request_data.comment
    )
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Вакансия '{request_data.vacancy_name}' не найдена в кэше."
        )
    return {"message": "Комментарий успешно сохранен."}


@app.get("/download-report")
async def download_report_endpoint():
    report_data = cache_manager.get_cached_vacancies()
    if not report_data:
        raise HTTPException(status_code=404, detail="Нет данных для генерации отчета.")
    xlsx_file = report_generator.create_xlsx_report(report_data)
    return StreamingResponse(
        xlsx_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={'Content-Disposition': 'attachment; filename="hiring_funnel_report.xlsx"'}
    )


@app.post("/refresh-report")
async def refresh_report_endpoint():
    if not token_proxy._access_token:
        raise HTTPException(status_code=403, detail="Токен API не задан.")
    logging.info("Запрос на принудительное обновление отчета.")
    await cache_manager.update_cached_data()
    return {"message": "Отчет успешно обновлен!"}