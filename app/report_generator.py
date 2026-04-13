import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import httpx
from huntflow_api_client import HuntflowAPI
import traceback

from .token_manager import token_proxy
from .analytics_engine import _is_allowed_recruiter, FUNNEL_STAGES_ORDER

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

HUNTFLOW_STATUSES_TO_COLUMNS = {
    "Коннект": "коннект", "Интервью с HR": "интервью с HR",
    "Интервью с заказчиком": "интервью с заказчиком", "Финальное интервью": "финальное интервью",
    "Финальное интервью с Юрой": "финальное интервью", "Выставлен оффер": "выставлен оффер",
    "Предложение принято": "выставлен оффер", "Вышел на работу": "вышел на работу",
    "Исп. срок пройден": "испытательный срок пройден",
}

KNOWN_SOURCES = {
    "hh": "hh.ru", "headhunter": "hh.ru", "habr": "Хабр Карьера", "хабр": "Хабр Карьера",
    "linkedin": "LinkedIn", "линкедин": "LinkedIn", "telegram": "Telegram", "телеграм": "Telegram",
    "tg": "Telegram", "avito": "Avito", "авито": "Avito", "vk": "ВКонтакте", "вк": "ВКонтакте",
    "рекомендаци": "Рекомендация", "referral": "Рекомендация", "career": "Карьерный сайт", "site": "Карьерный сайт",
    "HeadHunter": "HeadHunter"
}
TRASH_STATUSES = ["Отказ", "Резерв", "На паузе", "Уволен"]


async def _fetch_all_paginated(api_client: HuntflowAPI, url: str, params: Dict = None) -> List[Dict]:
    all_items, current_page, total_pages = [], 1, 1
    base_params = params.copy() if params else {}
    while current_page <= total_pages:
        base_params["page"] = current_page
        base_params["count"] = 100
        try:
            response = await api_client.request("GET", url, params=base_params)
            data = response.json()
            items = data.get("items", [])
            if not items: break
            all_items.extend(items)
            if current_page == 1: total_pages = data.get("total_pages", 1)
            current_page += 1
        except Exception:
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
            if key in tag_name: return real_name
        if "source" in tag_name or "источник" in tag_name: return tag.get("name")
    for log in logs:
        if log.get("type") == "COMMENT":
            comment_text = log.get("comment")
            # БЕЗОПАСНАЯ ПРОВЕРКА НА NULL
            if comment_text:
                text = comment_text.lower()
                if "добавлен" in text or "отклик" in text or "найден" in text:
                    for key, real_name in KNOWN_SOURCES.items():
                        if key in text: return real_name
    externals = applicant.get("externals") or []
    for ext in externals:
        url = ext.get("url", "").lower()
        for key, real_name in KNOWN_SOURCES.items():
            if key in url: return real_name
    return "Не указан"

def _match_recruiter_by_name(log_name: str, coworkers_map: Dict[int, str], default_id: int) -> int:
    if not log_name:
        return default_id

    log_name_lower = log_name.strip().lower()

    for cw_id, cw_name in coworkers_map.items():
        if cw_name.strip().lower() == log_name_lower:
            return cw_id

    log_parts = set(log_name_lower.split())
    best_match_id = default_id
    max_overlap = 0

    for cw_id, cw_name in coworkers_map.items():
        cw_parts = set(cw_name.strip().lower().split())
        overlap = len(log_parts.intersection(cw_parts))

        if overlap > max_overlap and overlap >= 1:
            max_overlap = overlap
            best_match_id = cw_id

    return best_match_id


async def _process_applicant(
        api_client: HuntflowAPI, account_id: int, applicant: Dict, vacancy: Dict,
        statuses_map: Dict, rejections_map: Dict, recruiter_id: int, first_hf_stage: str,
        coworkers_map: Dict[int, str]
) -> Optional[Dict]:
    app_id = applicant["id"]
    vac_id = vacancy["id"]
    vac_name = "🚩 " + vacancy.get("position", "Без названия") if vacancy.get("priority") == 1 else vacancy.get(
        "position", "Без названия")

    first_name = applicant.get("first_name", "") or ""
    last_name = applicant.get("last_name", "") or ""
    full_name = f"{first_name} {last_name}".strip()

    applicant_data = {
        "id": app_id,
        "name": full_name,
        "vacancy": vac_name, "vacancy_state": vacancy.get("state", "OPEN"),
        "recruiter_id": recruiter_id, "source": "Не указан",
        "created_at": applicant.get("created", datetime.now().isoformat()),
        "last_activity_at": applicant.get("created", datetime.now().isoformat()),
        "current_status": None, "hf_status": None, "rejection_reason": None,
        "offer_date": None, "hired_date": None, "is_hired": False, "logs": [],
        "stage_history": "[]"
    }

    try:
        logs_url = f"/accounts/{account_id}/applicants/{app_id}/logs"
        all_logs = await _fetch_all_paginated(api_client, logs_url, params={"vacancy": vac_id})

        if all_logs:
            sorted_all_logs = sorted(all_logs, key=lambda x: x.get("created", ""))
            applicant_data["created_at"] = sorted_all_logs[0].get("created", applicant_data["created_at"])
            applicant_data["last_activity_at"] = sorted_all_logs[-1].get("created", applicant_data["created_at"])

        applicant_data["source"] = _extract_source(applicant, all_logs)

        stage_history = []
        last_real_hf_status = None

        status_logs = [log for log in all_logs if log.get("type") == "STATUS"]
        status_logs.sort(key=lambda x: x.get("created", ""))

        for log in status_logs:
            hf_status_name = statuses_map.get(log.get("status"))
            if hf_status_name not in TRASH_STATUSES: last_real_hf_status = hf_status_name

            if hf_status_name:
                our_stage_name = HUNTFLOW_STATUSES_TO_COLUMNS.get(hf_status_name)
                log_date = log.get("created")

                account_info = log.get("account_info", {})
                log_name = account_info.get("name") if account_info else None
                log_user_id = _match_recruiter_by_name(log_name, coworkers_map, recruiter_id)

                stage_history.append({
                    "hf_stage": hf_status_name,
                    "custom_stage": our_stage_name,
                    "date": log_date,
                    "recruiter_id": log_user_id
                })

                if our_stage_name:
                    curr_idx = FUNNEL_STAGES_ORDER.index(applicant_data["current_status"]) if applicant_data[
                                                                                                  "current_status"] in FUNNEL_STAGES_ORDER else -1
                    new_idx = FUNNEL_STAGES_ORDER.index(our_stage_name) if our_stage_name in FUNNEL_STAGES_ORDER else -1
                    if new_idx >= curr_idx: applicant_data["current_status"] = our_stage_name
                    if our_stage_name == "выставлен оффер" and not applicant_data["offer_date"]: applicant_data[
                        "offer_date"] = log_date
                    if our_stage_name == "вышел на работу" and not applicant_data["hired_date"]:
                        applicant_data["hired_date"] = log_date
                        applicant_data["is_hired"] = True

            rej_id = log.get("rejection_reason")
            if rej_id: applicant_data["rejection_reason"] = rejections_map.get(rej_id, f"Неизвестно ({rej_id})")

        applicant_data["stage_history"] = json.dumps(stage_history, ensure_ascii=False)
        applicant_data["hf_status"] = last_real_hf_status

        return applicant_data

    except Exception as e:
        logging.error(f"Ошибка парсинга кандидата {app_id}: {e}\n{traceback.format_exc()}")
        return None


async def generate_raw_analytics_data() -> Optional[Dict[str, Any]]:
    if not token_proxy._access_token: return None
    api_client = HuntflowAPI("https://api.huntflow.ru", token_proxy=token_proxy, auto_refresh_tokens=False)

    try:
        try:
            accounts_response = await api_client.request("GET", "/accounts")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                if await token_proxy.refresh_tokens_manually():
                    accounts_response = await api_client.request("GET", "/accounts")
                else:
                    return None
            else:
                raise

        account_id = accounts_response.json()["items"][0]["id"]

        # 2. Загружаем справочники
        coworkers_raw = await _fetch_all_paginated(api_client, f"/accounts/{account_id}/coworkers")
        coworkers_map = {item["id"]: item["name"] for item in coworkers_raw}

        statuses_resp = await api_client.request("GET", f"/accounts/{account_id}/vacancies/statuses")
        raw_statuses = statuses_resp.json().get("items", [])
        statuses_map = {s["id"]: s["name"] for s in raw_statuses}

        sorted_statuses = sorted([s for s in raw_statuses if s["name"] not in TRASH_STATUSES],
                                 key=lambda x: x.get("order", 0))
        statuses_order_list = [s["name"] for s in sorted_statuses]

        rej_resp = await api_client.request("GET", f"/accounts/{account_id}/rejection_reasons")
        rejections_map = {r["id"]: r["name"] for r in rej_resp.json().get("items", [])}

        all_vacancies = await _fetch_all_paginated(api_client, f"/accounts/{account_id}/vacancies",
                                                   params={"state": ["OPEN", "CLOSED", "HOLD"]})

        vacancy_recruiters = {}
        sem_cws = asyncio.Semaphore(5)

        async def fetch_recruiter(vac):
            async with sem_cws:
                try:
                    cws = await _fetch_all_paginated(api_client, f"/accounts/{account_id}/coworkers",
                                                     params={"vacancy_id": vac["id"]})
                    if cws:
                        assigned_id = None
                        for cw in cws:
                            if _is_allowed_recruiter(cw["name"]):
                                assigned_id = cw["id"]
                                break
                        if not assigned_id:
                            for cw in cws:
                                if cw.get("type") == "manager":
                                    assigned_id = cw["id"]
                                    break
                        if not assigned_id: assigned_id = cws[0]["id"]
                        vacancy_recruiters[vac["id"]] = assigned_id
                except Exception:
                    pass

        logging.info(f"Определение ответственных для {len(all_vacancies)} вакансий...")
        await asyncio.gather(*(fetch_recruiter(v) for v in all_vacancies))

        filtered_vacancies = all_vacancies

        logging.info(f"Итого к обработке: {len(filtered_vacancies)} вакансий разрешенных рекрутеров.")

        first_hf_stage = statuses_order_list[0] if statuses_order_list else "New"
        all_applicants_data = []
        semaphore = asyncio.Semaphore(5)

        async def process_vacancy(vacancy):
            vac_applicants = await _fetch_all_paginated(api_client, f"/accounts/{account_id}/applicants/search",
                                                        params={"vacancy": vacancy["id"]})
            tasks = []
            for app in vac_applicants:
                async def sem_task(a=app, v=vacancy):
                    async with semaphore:
                        await asyncio.sleep(0.05)
                        rec_id = vacancy_recruiters.get(v["id"])
                        return await _process_applicant(
                            api_client, account_id, a, v,
                            statuses_map, rejections_map,
                            rec_id, first_hf_stage,
                            coworkers_map
                        )

                tasks.append(sem_task())

            results = await asyncio.gather(*tasks)
            return [r for r in results if r]

        for i, vacancy in enumerate(filtered_vacancies, 1):
            logging.info(f"[{i}/{len(filtered_vacancies)}] Сбор: {vacancy.get('position')}...")
            vac_results = await process_vacancy(vacancy)
            all_applicants_data.extend(vac_results)

        logging.info(f"--- СБОР ЗАВЕРШЕН: {len(all_applicants_data)} кандидатов ---")
        return {
            "applicants": all_applicants_data,
            "coworkers": coworkers_map,
            "statuses_order": statuses_order_list,
            "vacancies": [{"id": v["id"], "name": v.get("position", ""), "state": v.get("state")} for v in
                          filtered_vacancies]
        }
    except Exception as e:
        logging.error(f"Глобальная ошибка сбора: {e}")
        logging.error(traceback.format_exc())
        return None