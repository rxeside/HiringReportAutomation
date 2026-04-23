import asyncio
import httpx
import pandas as pd
from datetime import datetime


async def debug_closed():
    token = "ca63999a722d5bf09c4c4c211cca85f749734d7bb165b14cf779c4f8bda9625a"

    headers = {"Authorization": f"Bearer {token}"}
    base_url = "https://api.huntflow.ru/v2"

    async with httpx.AsyncClient() as client:
        print("🔍 Получаю список аккаунтов...")
        acc_resp = await client.get(f"{base_url}/accounts", headers=headers)
        if acc_resp.status_code != 200:
            print(f"❌ Ошибка API: {acc_resp.text}")
            return

        accounts = acc_resp.json().get("items", [])
        account_id = accounts[0]["id"]
        print(f"✅ ID Аккаунта найден: {account_id} ({accounts[0]['name']})")

        print("\n🔍 Ищу последние закрытые вакансии...")
        params = {"state": "CLOSED", "count": 5}
        vac_resp = await client.get(f"{base_url}/accounts/{account_id}/vacancies", headers=headers, params=params)
        vacancies = vac_resp.json().get("items", [])

        if not vacancies:
            print("⚠️ Закрытых вакансий не найдено. Пробую найти открытые для примера...")
            params = {"state": "OPEN", "count": 5}
            vac_resp = await client.get(f"{base_url}/accounts/{account_id}/vacancies", headers=headers, params=params)
            vacancies = vac_resp.json().get("items", [])

        print(f"📊 Найдено вакансий для анализа: {len(vacancies)}")
        print("=" * 80)

        for v in vacancies:
            v_id = v['id']
            v_name = v.get('position', 'Без названия')

            detail_resp = await client.get(f"{base_url}/accounts/{account_id}/vacancies/{v_id}", headers=headers)
            v_detail = detail_resp.json()

            v_created = v_detail.get('created')
            v_req_id = v_detail.get('vacancy_request')

            print(f"📍 ВАКАНСИЯ: {v_name} (ID: {v_id})")
            print(f"   Дата создания вакансии в ХФ: {v_created}")

            if v_req_id:
                req_resp = await client.get(f"{base_url}/accounts/{account_id}/vacancy_requests/{v_req_id}",
                                            headers=headers)
                r_data = req_resp.json()
                r_created = r_data.get('created')
                print(f"   🔥 НАЙДЕНА ЗАЯВКА (ID: {v_req_id})")
                print(f"   Дата создания ЗАЯВКИ: {r_created}  <-- СКОРЕЕ ВСЕГО ЭТО ТО, ЧТО НУЖНО")
            else:
                print(" Вакансия создана напрямую (без заявки)")
            print("-" * 40)


if __name__ == "__main__":
    asyncio.run(debug_closed())