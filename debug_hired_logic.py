import asyncio
import httpx
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime

token = "69d1aaf232ee966ec79df7613ba02f9966d7c3d0a26f1cf5b65609315b31dd7e"
ANASTASIA_ID = 236211


async def run_debug():
    if not token:
        print("❌ Ошибка: Укажите токен")
        return

    headers = {"Authorization": f"Bearer {token}"}
    base_url = "https://api.huntflow.ru/v2"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Получаем ID аккаунта
        acc_resp = await client.get(f"{base_url}/accounts", headers=headers)
        account_id = acc_resp.json()["items"][0]["id"]
        print(f"✅ Аккаунт iSpring (ID: {account_id})")

        # 2. Получаем список ВСЕХ вакансий (не только своих)
        print("⏳ Запрашиваю список всех вакансий компании...")
        v_resp = await client.get(f"{base_url}/accounts/{account_id}/vacancies",
                                  headers=headers, params={"count": 500})
        all_vacs = v_resp.json().get('items', [])
        print(f"✅ Всего вакансий найдено: {len(all_vacs)}")

        # 3. Ищем вакансии, где Анастасия - участник
        print("🔍 Сканирую участников вакансий (ищу Анастасию)...")
        nastya_vac_names = []

        # Чтобы не спамить API, будем проверять по 10 вакансий за раз
        semaphore = asyncio.Semaphore(10)

        async def check_membership(v):
            async with semaphore:
                try:
                    c_resp = await client.get(
                        f"{base_url}/accounts/{account_id}/coworkers",
                        headers=headers,
                        params={"vacancy_id": v['id']}
                    )
                    members = c_resp.json().get('items', [])
                    if any(m['id'] == ANASTASIA_ID for m in members):
                        return v['position']
                except:
                    pass
                return None

        tasks = [check_membership(v) for v in all_vacs]
        results = await asyncio.gather(*tasks)
        nastya_vac_names = [r for r in results if r]

        print(f"✅ Найдено вакансий, где Анастасия участник: {len(nastya_vac_names)}")

        # 4. Подключаемся к нашей базе
        engine = create_engine("sqlite:///cache/huntflow.db")
        df = pd.read_sql_table("applicants", engine)

        # Обрабатываем даты и названия
        df['created_clean'] = (
                    pd.to_datetime(df['created_at'], errors='coerce', utc=True) + pd.Timedelta(hours=3)).dt.tz_localize(
            None)
        df['vac_simple'] = df['vacancy'].str.replace('🚩 ', '', regex=False)

        START = datetime(2026, 3, 1)
        END = datetime(2026, 3, 31, 23, 59, 59)

        # 5. Считаем кандидатов на этих вакансиях за Март
        final_df = df[
            (df['created_clean'] >= START) &
            (df['created_clean'] <= END) &
            (df['vac_simple'].isin(nastya_vac_names))
            ].copy()

        print("\n" + "=" * 60)
        print(f"ИТОГОВЫЙ РАСЧЕТ:")
        print(f"Всего кандидатов за Март на этих вакансиях: {len(final_df)} (Цель: 171)")
        print("=" * 60)

        if not final_df.empty:
            # Маппинг источников (Хантфлоу часто объединяет Не указан/Другое)
            final_df['source_hf'] = final_df['source'].replace('Не указан', 'Другой')
            summary = final_df['source_hf'].value_counts()
            print(summary.to_string())

            print("\nСверка с Хантфлоу (Цель 171):")
            target = {"Отклик с HeadHunter": 114, "HeadHunter": 50, "Рекомендация внутренняя": 2, "Политех": 1}
            for src, val in target.items():
                curr = summary.get(src, 0)
                status = "✅" if curr == val else "❌"
                print(f"{status} {src}: {curr} (Нужно: {val})")


if __name__ == "__main__":
    asyncio.run(run_debug())