import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import logging

from . import report_generator
from . import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI(title="Hiring Report Dashboard")
templates = Jinja2Templates(directory="templates")

HUNTFLOW_API_TOKEN = config.HUNTFLOW_API_TOKEN

if HUNTFLOW_API_TOKEN:
    logging.info(f"Токен успешно импортирован из config.py. (Начинается с: {HUNTFLOW_API_TOKEN[:4]}... )")
else:
    logging.error("ВНИМАНИЕ: Токен НЕ найден или не изменен в файле app/config.py!")


@app.get("/", response_class=HTMLResponse)
async def show_report_table(request: Request):
    """Отображает главную страницу с таблицей отчета."""
    if not HUNTFLOW_API_TOKEN or HUNTFLOW_API_TOKEN == "ВАШ_ДЛИННЫЙ_ТОКЕН_ЗДЕСЬ":
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": "Токен не задан в файле app/config.py"
        })

    logging.info("Запрос на отображение отчета. Начинаю сбор данных...")
    report_data = await report_generator.fetch_and_process_data(HUNTFLOW_API_TOKEN)

    headers = ["Название вакансии"] + report_generator.FUNNEL_STAGES_ORDER + ["Комментарий"]

    return templates.TemplateResponse("index.html", {
        "request": request,
        "headers": headers,
        "report_data": report_data
    })


@app.get("/download-report")
async def download_report_endpoint():
    """Генерирует и отдает отчет в формате XLSX."""
    if not HUNTFLOW_API_TOKEN or HUNTFLOW_API_TOKEN == "ВАШ_ДЛИННЫЙ_ТОКЕН_ЗДЕСЬ":
        raise HTTPException(status_code=500, detail="Токен не задан в файле app/config.py.")

    logging.info("Запрос на скачивание XLSX. Начинаю сбор данных...")
    report_data = await report_generator.fetch_and_process_data(HUNTFLOW_API_TOKEN)

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