import os
import asyncio
import openpyxl
from huntflow_api_client import HuntflowAPI
from huntflow_api_client.tokens.token import ApiToken
import httpx

HUNTFLOW_API_TOKEN = "e296077ea7429c6650f3be98a634f0a8d25eaed39391ecef74391c0ecf2a8982"

OUTPUT_FILE_NAME = "voronka_kandidatov.xlsx"

HUNTFLOW_STATUSES_TO_COLUMNS = {
    "Новые": "просмотрено резюме",
    "Коннект": "коннект",
    "Интервью с HR": "интервью с HR",
    "Интервью с заказчиком": "интервью с заказчиком",
    "Финальное интервью": "финальное интервью",
    "Предложение о работе": "выставлен оффер",
    "Вышел на работу": "вышел на работу",
}


async def get_huntflow_data(api_client):
    try:
        accounts_response = await api_client.request("GET", "/accounts")
        accounts_data = accounts_response.json()

        if not accounts_data.get("items"):
            print("Ошибка: Не найдено ни одного аккаунта для вашего токена.")
            return None
        account_id = accounts_data["items"][0]["id"]
        print(f"Успешно подключились к аккаунту: {accounts_data['items'][0]['name']} (ID: {account_id})")

        statuses_response = await api_client.request("GET", f"/accounts/{account_id}/vacancies/statuses")
        statuses_data = statuses_response.json()
        status_map = {status["id"]: status["name"] for status in statuses_data.get("items", [])}

        vacancies_response = await api_client.request("GET", f"/accounts/{account_id}/vacancies",
                                                      params={"opened": True})
        vacancies_data = vacancies_response.json()

        vacancy_funnel_data = []
        print(f"Найдено {len(vacancies_data.get('items', []))} активных вакансий. Начинаю сбор данных...")

        for vacancy in vacancies_data.get("items", []):
            vacancy_id = vacancy["id"]
            vacancy_position = vacancy["position"]
            print(f"Обрабатываю вакансию: «{vacancy_position}»")

            funnel = {
                "название вакансии": vacancy_position, "просмотрено резюме": 0, "коннект": 0, "интервью с HR": 0,
                "интервью с заказчиком": 0, "финальное интервью": 0, "выставлен оффер": 0, "вышел на работу": 0,
                "комментарий": ""
            }

            applicants_response = await api_client.request("GET", f"/accounts/{account_id}/applicants",
                                                           params={"vacancy": vacancy_id})
            applicants_data = applicants_response.json()

            for applicant in applicants_data.get("items", []):
                for link in applicant.get("links", []):
                    if link.get("vacancy") == vacancy_id:
                        status_id = link.get("status")
                        status_name = status_map.get(status_id)

                        if status_name in HUNTFLOW_STATUSES_TO_COLUMNS:
                            column_name = HUNTFLOW_STATUSES_TO_COLUMNS[status_name]
                            funnel[column_name] += 1

                        break

            vacancy_funnel_data.append(funnel)

        return vacancy_funnel_data

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            print("Ошибка 401: Unauthorized. Токен недействителен или истек.")
        else:
            print(f"Произошла HTTP ошибка: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        print(f"Произошла непредвиденная ошибка: {e}")
        return None


def create_xlsx_report(data):
    if not data:
        print("Нет данных для создания отчета.")
        return
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Воронка кандидатов"
    headers = [
        "название вакансии", "просмотрено резюме", "коннект", "интервью с HR",
        "интервью с заказчиком", "финальное интервью", "выставлен оффер",
        "вышел на работу", "комментарий"
    ]
    sheet.append(headers)
    for row_data in data:
        row = [row_data.get(header, "") for header in headers]
        sheet.append(row)
    try:
        workbook.save(OUTPUT_FILE_NAME)
        print(f"\nОтчет успешно сохранен в файл: {os.path.abspath(OUTPUT_FILE_NAME)}")
    except Exception as e:
        print(f"Не удалось сохранить файл. Ошибка: {e}")


async def main():
    if HUNTFLOW_API_TOKEN == "ВАШ_НАСТОЯЩИЙ_ТОКЕН":
        print("Ошибка: Пожалуйста, укажите ваш токен в скрипте.")
        return

    api_client = HuntflowAPI(
        base_url="https://api.huntflow.ru",
        token=ApiToken(access_token=HUNTFLOW_API_TOKEN)
    )
    funnel_data = await get_huntflow_data(api_client)
    if funnel_data:
        create_xlsx_report(funnel_data)


if __name__ == "__main__":
    asyncio.run(main())