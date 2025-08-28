import os
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import logging
from . import report_generator, config, cache_manager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import aiofiles
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI(title="Hiring Report Dashboard")
templates = Jinja2Templates(directory="templates")

HUNTFLOW_API_TOKEN = config.HUNTFLOW_API_TOKEN

if HUNTFLOW_API_TOKEN:
    logging.info(f"Токен успешно импортирован из config.py. (Начинается с: {HUNTFLOW_API_TOKEN[:4]}... )")
else:
    logging.error("ВНИМАНИЕ: Токен НЕ найден или не изменен в файле app/config.py")


@app.get("/", response_class=HTMLResponse)
async def show_report_table(request: Request):
    """Отображает главную страницу с таблицей отчета."""
    if not HUNTFLOW_API_TOKEN:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": "Токен не задан в файле app/config.py"
        })

    logging.info("Запрос на отображение отчета. Начинаю сбор данных...")
    report_data = await cache_manager.get_cached_data()
    last_updated = cache_manager.get_last_updated_time()
    headers = ["Название вакансии"] + report_generator.FUNNEL_STAGES_ORDER + ["Комментарий"]

    return templates.TemplateResponse("index.html", {
        "request": request,
        "headers": headers,
        "report_data": report_data,
        "last_updated": last_updated,
    })


@app.get("/download-report")
async def download_report_endpoint():
    """Генерирует и отдает отчет в формате XLSX."""
    if not HUNTFLOW_API_TOKEN:
        raise HTTPException(status_code=500, detail="Токен не задан в файле app/config.py.")

    logging.info("Запрос на скачивание XLSX. Начинаю сбор данных...")
    report_data = await cache_manager.get_cached_data()
    if report_data is None:
        raise HTTPException(status_code=500, detail="Не удалось получить данные для отчета.")

    xlsx_file = report_generator.create_xlsx_report(report_data)
    if xlsx_file is None:
        raise HTTPException(status_code=500, detail="Не удалось создать XLSX файл.")

    headers = {'Content-Disposition': 'attachment; filename="hiring_funnel_report.xlsx"'}
    return StreamingResponse(
        xlsx_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )

@app.post("/refresh-report")
async def refresh_report_endpoint():
    """Обновляет данные отчета немедленно."""
    if not HUNTFLOW_API_TOKEN:
        raise HTTPException(status_code=500, detail="Токен не задан в файле app/config.py.")
    logging.info("Запрос на принудительное обновление отчета.")
    await cache_manager.update_cached_data(HUNTFLOW_API_TOKEN)
    return {"message": "Отчет успешно обновлен!"}

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    logging.info("Инициализация кэша и планировщика задач...")
    await cache_manager.load_cache()
    scheduler.add_job(
        cache_manager.update_cached_data,
        "interval",
        seconds=config.UPDATE_INTERVAL_SECONDS,
        args=(HUNTFLOW_API_TOKEN,),
        max_instances=1,
        next_run_time=datetime.now()
    )
    scheduler.start()
    logging.info(f"Планировщик запущен, обновление каждые {config.UPDATE_INTERVAL_SECONDS} секунд.")

@app.on_event("shutdown")
async def shutdown_event():
    logging.info("Останавливаю планировщик задач...")
    scheduler.shutdown()