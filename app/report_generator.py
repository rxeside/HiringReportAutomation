import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import httpx
from huntflow_api_client import HuntflowAPI
import traceback

from .token_manager import token_proxy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

FUNNEL_STAGES_ORDER = [
    "коннект", "интервью с HR", "интервью с заказчиком", "финальное интервью",
    "выставлен оффер", "вышел на работу", "испытательный срок пройден"
]

HUNTFLOW_STATUSES_TO_COLUMNS = {
    "Коннект": "коннект",
    "Интервью с HR": "интервью с HR",
    "Интервью с заказчиком": "интервью с заказчиком",
    "Финальное интервью": "финальное интервью",
    "Выставлен оффер": "выставлен оффер",
    "Вышел на работу": "вышел на работу",
    "Испытательный срок пройден": "испытательный срок пройден",
    "ИС пройден": "испытательный срок пройден",
    "Испытательный срок завершен": "испытательный срок пройден"
}

KNOWN_SOURCES = {
    "hh": "hh.ru", "headhunter": "hh.ru",
    "habr": "Хабр Карьера", "хабр": "Хабр Карьера",
    "linkedin": "LinkedIn", "линкедин": "LinkedIn",
    "telegram": "Telegram", "телеграм": "Telegram", "tg": "Telegram",
    "avito": "Avito", "авито": "Avito",
    "vk": "ВКонтакте", "вк": "ВКонтакте",
    "рекомендаци": "Рекомендация", "referral": "Рекомендация",
    "career": "Карьерный сайт", "site": "Карьерный сайт"
}


async def _fetch_all_paginated(api_client: HuntflowAPI, url: str, params: Dict = None) -> List[Dict]:
    all_items = []
    current_page = 1
    total_pages = 1
    base_params = params.copy() if params else {}

    while current_page <= total_pages:
        base_params["page"] = current_page
        base_params["count"] = 100
        try:
            response = await api_client.request("GET", url, params=base_params)
            data = response.json()
            items = data.get("items", [])
            if not items:
                break
            all_items.extend(items)
            if current_page == 1:
                total_pages = data.get("total_pages", 1)
            current_page += 1
        except Exception as e:
            logging.error(f"Ошибка пагинации на {url} (стр {current_page}): {e}")
            break
    return all_items


def _extract_source(applicant: Dict, logs: List[Dict]) -> str:
    source_field = applicant.get("source")
    if isinstance(source_field, dict) and source_field.get("name"):
        return source_field.get("name")
    elif isinstance(source_field, str) and source_field.strip():
        return source_field

    tags = applicant.get("tags") or []
    for tag in tags:
        tag_name = tag.get("name", "").lower()
        for key, real_name in KNOWN_SOURCES.items():
            if key in tag_name:
                return real_name
        if "source" in tag_name or "источник" in tag_name:
            return tag.get("name")

    for log in logs:
        if log.get("type") == "COMMENT":
            text = log.get("comment", "").lower()
            if "добавлен" in text or "отклик" in text or "найден" in text:
                for key, real_name in KNOWN_SOURCES.items():
                    if key in text:
                        return real_name

    externals = applicant.get("externals") or []
    for ext in externals:
        url = ext.get("url", "").lower()
        for key, real_name in KNOWN_SOURCES.items():
            if key in url:
                return real_name

    return "Не указан"


async def _process_applicant(
        api_client: HuntflowAPI, account_id: int, applicant: Dict, vacancy: Dict,
        statuses_map: Dict, rejections_map: Dict, recruiter_id: int
) -> Optional[Dict]:
    app_id = applicant["id"]
    vac_id = vacancy["id"]

    applicant_data = {
        "id": app_id,
        "vacancy": vacancy.get("position", "Без названия"),
        "vacancy_state": vacancy.get("state", "OPEN"),
        "recruiter_id": recruiter_id,
        "source": "Не указан",
        "created_at": applicant.get("created", datetime.now().isoformat()),
        "current_status": None,
        "rejection_reason": None,
        "offer_date": None,
        "hired_date": None,
        "is_hired": False,
        "logs": []
    }

    try:
        logs_url = f"/accounts/{account_id}/applicants/{app_id}/logs"
        all_logs = await _fetch_all_paginated(api_client, logs_url, params={"vacancy": vac_id})

        applicant_data["source"] = _extract_source(applicant, all_logs)

        status_logs = [log for log in all_logs if log.get("type") == "STATUS"]
        status_logs.sort(key=lambda x: x.get("created", ""))

        for log in status_logs:
            hf_status_name = statuses_map.get(log.get("status"))
            our_stage_name = HUNTFLOW_STATUSES_TO_COLUMNS.get(hf_status_name)

            if our_stage_name:
                log_date = log.get("created")
                applicant_data["logs"].append({"stage": our_stage_name, "date": log_date})
                applicant_data["current_status"] = our_stage_name

                if our_stage_name == "выставлен оффер":
                    applicant_data["offer_date"] = log_date
                if our_stage_name == "вышел на работу":
                    applicant_data["hired_date"] = log_date
                    applicant_data["is_hired"] = True

            rej_id = log.get("rejection_reason")
            if rej_id:
                applicant_data["rejection_reason"] = rejections_map.get(rej_id, f"Неизвестно ({rej_id})")

        return applicant_data

    except Exception as e:
        logging.warning(f"Ошибка при обработке кандидата {app_id}: {e}")
        return None


async def generate_raw_analytics_data() -> Optional[Dict[str, Any]]:
    if not token_proxy._access_token:
        return None

    api_client = HuntflowAPI("https://api.huntflow.ru", token_proxy=token_proxy, auto_refresh_tokens=False)

    try:
        logging.info("--- СТАРТ СБОРА ДАННЫХ ИЗ HUNTFLOW ---")
        try:
            accounts_response = await api_client.request("GET", "/accounts")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logging.warning("Токен истек. Обновляем...")
                if await token_proxy.refresh_tokens_manually():
                    accounts_response = await api_client.request("GET", "/accounts")
                else:
                    return None
            else:
                raise

        account_id = accounts_response.json()["items"][0]["id"]

        coworkers_raw = await _fetch_all_paginated(api_client, f"/accounts/{account_id}/coworkers")
        coworkers_map = {item["id"]: item["name"] for item in coworkers_raw}

        statuses_resp = await api_client.request("GET", f"/accounts/{account_id}/vacancies/statuses")
        statuses_map = {s["id"]: s["name"] for s in statuses_resp.json().get("items", [])}

        rej_resp = await api_client.request("GET", f"/accounts/{account_id}/rejection_reasons")
        rejections_map = {r["id"]: r["name"] for r in rej_resp.json().get("items", [])}

        logging.info("Сбор списка вакансий...")
        all_vacancies = await _fetch_all_paginated(api_client, f"/accounts/{account_id}/vacancies")

        logging.info("Определение рекрутеров для вакансий (около 1 минуты)...")
        vacancy_recruiters = {}
        sem_cws = asyncio.Semaphore(10)

        async def fetch_recruiter(vac):
            async with sem_cws:
                try:
                    cws = await _fetch_all_paginated(api_client, f"/accounts/{account_id}/coworkers",
                                                     params={"vacancy_id": vac["id"]})
                    if cws: vacancy_recruiters[vac["id"]] = cws[0]["id"]
                except Exception:
                    pass

        await asyncio.gather(*(fetch_recruiter(v) for v in all_vacancies))

        all_applicants_data = []
        semaphore = asyncio.Semaphore(5)

        async def process_vacancy(vacancy):
            vac_applicants = await _fetch_all_paginated(api_client, f"/accounts/{account_id}/applicants/search",
                                                        params={"vacancy": vacancy["id"]})
            tasks = []
            for app in vac_applicants:
                async def sem_task(a=app, v=vacancy):
                    async with semaphore:
                        rec_id = vacancy_recruiters.get(v["id"])
                        return await _process_applicant(api_client, account_id, a, v, statuses_map, rejections_map,
                                                        rec_id)

                tasks.append(sem_task())
            results = await asyncio.gather(*tasks)
            return [r for r in results if r]

        for i, vacancy in enumerate(all_vacancies, 1):
            logging.info(f"Обработка вакансии {i}/{len(all_vacancies)}: {vacancy.get('position')}...")
            vac_results = await process_vacancy(vacancy)
            all_applicants_data.extend(vac_results)

        logging.info(f"--- СБОР ЗАВЕРШЕН! Собрано {len(all_applicants_data)} кандидатов ---")
        return {
            "applicants": all_applicants_data,
            "coworkers": coworkers_map,
            "vacancies": [{"id": v["id"], "name": v["position"], "state": v.get("state")} for v in all_vacancies]
        }
    except Exception as e:
        logging.error(f"Ошибка сбора: {e}")
        return None