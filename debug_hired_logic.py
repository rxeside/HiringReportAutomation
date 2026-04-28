import asyncio
import httpx
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime
import json

token = "69d1aaf232ee966ec79df7613ba02f9966d7c3d0a26f1cf5b65609315b31dd7e"

async def run_debug():
    if not token:
        print("❌ Ошибка: Укажите токен")
        return

    headers = {"Authorization": f"Bearer {token}"}
    base_url = "https://api.huntflow.ru/v2"

    async with httpx.AsyncClient(timeout=20.0) as client:
        acc_resp = await client.get(f"{base_url}/accounts", headers=headers)
        if acc_resp.status_code != 200:
            print(f"❌ Ошибка авторизации: {acc_resp.text}")
            return

        account_id = acc_resp.json()["items"][0]["id"]
        me_resp = await client.get(f"{base_url}/me", headers=headers)
        my_id = me_resp.json()["id"]
        my_name = me_resp.json()["name"]
        print(f"✅ Вы вошли как: {my_name} (ID: {my_id})")

        print("⏳ Запрашиваю список ваших вакансий из API...")
        v_resp = await client.get(f"{base_url}/accounts/{account_id}/vacancies",
                                  headers=headers, params={"mine": "true", "count": 100})

        if v_resp.status_code != 200:
            print(f"❌ Ошибка получения вакансий: {v_resp.text}")
            return

        api_vac_ids = [v['id'] for v in v_resp.json().get('items', [])]
        print(f"✅ Найдено вакансий в API, где вы участник: {len(api_vac_ids)}")

        engine = create_engine("sqlite:///cache/huntflow.db")
        df = pd.read_sql_table("applicants", engine)

        df['created_clean'] = (
                    pd.to_datetime(df['created_at'], errors='coerce', utc=True) + pd.Timedelta(hours=3)).dt.tz_localize(
            None)

        START = datetime(2026, 3, 1)
        END = datetime(2026, 3, 31, 23, 59, 59)

        march_apps = df[(df['created_clean'] >= START) & (df['created_clean'] <= END)].copy()

        api_vac_names = [v['position'] for v in v_resp.json().get('items', [])]

        df['vac_simple'] = df['vacancy'].str.replace('🚩 ', '', regex=False)

        final_df = march_apps[march_apps['vacancy'].str.replace('🚩 ', '', regex=False).isin(api_vac_names)]

        print("\n" + "=" * 60)
        print(f"ИТОГОВЫЙ РАСЧЕТ:")
        print(f"Всего кандидатов на 'ваших' вакансиях: {len(final_df)} (Цель: 171)")
        print("=" * 60)

        if not final_df.empty:
            summary = final_df['source'].value_counts()
            print(summary.to_string())

            print("\nСверка с Хантфлоу (171):")
            target = {"Отклик с HeadHunter": 114, "HeadHunter": 50, "Рекомендация внутренняя": 2, "Политех": 1}
            for src, val in target.items():
                curr = summary.get(src, 0)
                status = "✅" if curr == val else "❌"
                print(f"{status} {src}: {curr} (Нужно: {val})")


if __name__ == "__main__":
    asyncio.run(run_debug())