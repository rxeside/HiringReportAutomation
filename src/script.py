import os
from datetime import datetime
import openpyxl
from huntflow_api_client import HuntflowAPI

HUNTFLOW_API_TOKEN = "YOUR_ACCESS_TOKEN"

HUNTFLOW_DOMAIN = "yourcompany.huntflow.ru"

OUTPUT_FILE_NAME = "voronka_kandidatov.xlsx"


HUNTFLOW_STATUSES_TO_COLUMNS = {
    "Новые": "просмотрено резюме",
    "Контакт": "коннект",
    "Интервью с HR": "интервью с HR",
    "Техническое интервью": "интервью с заказчиком",
    "Финальное интервью": "финальное интервью",
    "Оффер": "выставлен оффер",
    "Выход на работу": "вышел на работу",
}

def get_huntflow_data(api_client):
    """
    Получает данные о вакансиях и кандидатах из Huntflow.
    """
    try:
        # Получаем ID организации
        accounts = api_client.accounts.list()
        if not accounts.items:
            print("Ошибка: Не найдено ни одного аккаунта (организации).")
            return None
        account_id = accounts.items[0].id

        statuses = api_client.vacancy_statuses.list(account_id=account_id)
        status_map = {status.id: status.name for status in statuses.items}

        vacancies = api_client.vacancies.list(account_id=account_id)

        vacancy_funnel_data = []

        print(f"Найдено {len(vacancies.items)} вакансий. Начинаю сбор данных...")

        for vacancy in vacancies.items:
            print(f"Обрабатываю вакансию: {vacancy.position}")

            funnel = {
                "название вакансии": vacancy.position,
                "просмотрено резюме": 0,
                "коннект": 0,
                "интервью с HR": 0,
                "интервью с заказчиком": 0,
                "финальное интервью": 0,
                "выставлен оффер": 0,
                "вышел на работу": 0,
                "комментарий": ""
            }

            applicants = api_client.vacancy_applicants.list(
                account_id=account_id,
                vacancy_id=vacancy.id
            )

            for applicant in applicants.items:
                status_name = status_map.get(applicant.status)
                if status_name in HUNTFLOW_STATUSES_TO_COLUMNS:
                    column_name = HUNTFLOW_STATUSES_TO_COLUMNS[status_name]
                    funnel[column_name] += 1

            vacancy_funnel_data.append(funnel)

        return vacancy_funnel_data

    except Exception as e:
        print(f"Произошла ошибка при работе с API Huntflow: {e}")
        return None


def create_xlsx_report(data):
    """
    Создает XLSX файл на основе полученных данных.
    """
    if not data:
        print("Нет данных для создания отчета.")
        return

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Воронка кандидатов"

    headers = [
        "название вакансии",
        "просмотрено резюме",
        "коннект",
        "интервью с HR",
        "интервью с заказчиком",
        "финальное интервью",
        "выставлен оффер",
        "вышел на работу",
        "комментарий"
    ]
    sheet.append(headers)

    for row_data in data:
        row = [row_data.get(header, "") for header in headers]
        sheet.append(row)

    try:
        workbook.save(OUTPUT_FILE_NAME)
        print(f"Отчет успешно сохранен в файл: {os.path.abspath(OUTPUT_FILE_NAME)}")
    except Exception as e:
        print(f"Не удалось сохранить файл. Ошибка: {e}")


if __name__ == "__main__":
    if HUNTFLOW_API_TOKEN == "YOUR_ACCESS_TOKEN":
        print("Ошибка: Пожалуйста, укажите ваш токен доступа (HUNTFLOW_API_TOKEN) в скрипте.")
    else:
        api_client = HuntflowAPI(
            base_url=f"https://{HUNTFLOW_DOMAIN}/v2",
            access_token=HUNTFLOW_API_TOKEN
        )

        funnel_data = get_huntflow_data(api_client)

        if funnel_data:
            create_xlsx_report(funnel_data)