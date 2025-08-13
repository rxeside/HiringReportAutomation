import os
import asyncio
import openpyxl
from huntflow_api_client import HuntflowAPI
from huntflow_api_client.tokens.token import ApiToken
import httpx

HUNTFLOW_API_TOKEN = "e296077ea7429c6650f3be98a634f0a8d25eaed39391ecef74391c0ecf2a8982"

OUTPUT_FILE_NAME = "voronka_kandidatov_combined.xlsx"

HUNTFLOW_STATUSES_TO_COLUMNS = {
    "Новые": "новые",
    "Коннект": "коннект",
    "Интервью с HR": "интервью с HR",
    "Интервью с заказчиком": "интервью с заказчиком",
    "Финальное интервью": "финальное интервью",
    "Предложение о работе": "выставлен оффер",
    "Вышел на работу": "вышел на работу",
}


async def get_total_applicants_on_stage(api_client, account_id, vacancy_id, status_id):
    """
    (для чисел вне скобок)
    Получает ОБЩЕЕ число кандидатов на этапе, используя applicants/search.
    """
    try:
        search_params = {
            "vacancy": [vacancy_id],
            "status": [status_id],
            "only_current_status": "false",
            "count": 1
        }
        response = await api_client.request(
            "GET", f"/accounts/{account_id}/applicants/search", params=search_params
        )
        data = response.json()
        return data.get("total_items", 0)
    except Exception as e:
        print(f"      - Ошибка при получении общего числа для status_id {status_id}: {e}")
        return 0


async def get_huntflow_data(api_client):
    try:
        accounts_response = await api_client.request("GET", "/accounts")
        accounts_data = accounts_response.json()
        if not accounts_data.get("items"):
            print("Ошибка: Не найдено ни одного аккаунта.")
            return None
        account_id = accounts_data["items"][0]["id"]
        print(f"Успешно подключились к аккаунту: {accounts_data['items'][0]['name']} (ID: {account_id})")

        statuses_response = await api_client.request("GET", f"/accounts/{account_id}/vacancies/statuses")
        statuses_data = statuses_response.json()
        status_name_to_id_map = {status["name"]: status["id"] for status in statuses_data.get("items", [])}
        status_id_to_name_map = {v: k for k, v in status_name_to_id_map.items()}

        vacancies_response = await api_client.request("GET", f"/accounts/{account_id}/vacancies",
                                                      params={"opened": "true"})
        vacancies_data = vacancies_response.json()

        all_vacancies_data = []
        print(f"\nНайдено {len(vacancies_data.get('items', []))} активных вакансий. Начинаю сбор данных...")

        for vacancy in vacancies_data.get("items", []):
            vacancy_id = vacancy["id"]
            vacancy_position = vacancy["position"]
            print(f"  - Обрабатываю вакансию: «{vacancy_position}»")

            funnel_row = {"название вакансии": vacancy_position, "комментарий": ""}
            for column_name in HUNTFLOW_STATUSES_TO_COLUMNS.values():
                funnel_row[column_name] = {"total": 0, "current": 0}

            # (для чисел в скобках)
            # Получаем ТЕКУЩЕЕ число кандидатов на этапах
            applicants_response = await api_client.request("GET", f"/accounts/{account_id}/applicants",
                                                           params={"vacancy": vacancy_id})
            applicants_data = applicants_response.json()

            for applicant in applicants_data.get("items", []):
                for link in applicant.get("links", []):
                    if link.get("vacancy") == vacancy_id:
                        status_id = link.get("status")
                        status_name = status_id_to_name_map.get(status_id)
                        if status_name in HUNTFLOW_STATUSES_TO_COLUMNS:
                            column_name = HUNTFLOW_STATUSES_TO_COLUMNS[status_name]
                            funnel_row[column_name]["current"] += 1
                        break

            # (для чисел вне скобок)
            # Получаем ОБЩЕЕ число кандидатов для каждого этапа.
            print(f"    - Получаю исторические данные по этапам...")
            for status_hf_name, column_name in HUNTFLOW_STATUSES_TO_COLUMNS.items():
                status_id = status_name_to_id_map.get(status_hf_name)
                if status_id:
                    total_count = await get_total_applicants_on_stage(api_client, account_id, vacancy_id, status_id)
                    funnel_row[column_name]["total"] = total_count

            all_vacancies_data.append(funnel_row)

        return all_vacancies_data

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            print("Ошибка 401: Unauthorized. Токен недействителен или истек.")
        else:
            print(f"Произошла HTTP ошибка: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        import traceback
        print(f"Произошла непредвиденная ошибка: {e}")
        traceback.print_exc()
        return None


def create_xlsx_report(data):
    if not data:
        print("Нет данных для создания отчета.")
        return
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Воронка кандидатов"
    headers = ["название вакансии"] + list(HUNTFLOW_STATUSES_TO_COLUMNS.values()) + ["комментарий"]
    sheet.append(headers)

    for row_data in data:
        row_to_append = []
        for header in headers:
            cell_data = row_data.get(header)
            if isinstance(cell_data, dict):
                total = cell_data.get('total', 0)
                current = cell_data.get('current', 0)
                formatted_value = f"{total} ({current})"
                row_to_append.append(formatted_value)
            else:
                row_to_append.append(cell_data if cell_data is not None else "")
        sheet.append(row_to_append)

    try:
        workbook.save(OUTPUT_FILE_NAME)
        print(f"\nОтчет успешно сохранен в файл: {os.path.abspath(OUTPUT_FILE_NAME)}")
    except Exception as e:
        print(f"Не удалось сохранить файл. Ошибка: {e}")


async def main():
    if not HUNTFLOW_API_TOKEN or HUNTFLOW_API_TOKEN == "YOUR_ACCESS_TOKEN":
        print("ОШИБКА: Пожалуйста, укажите ваш токен доступа в переменной HUNTFLOW_API_TOKEN.")
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