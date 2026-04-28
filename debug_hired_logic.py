import asyncio
import httpx
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime

# ВСТАВЬ СВОЙ ТОКЕН
token = ""


async def get_my_vacancies_from_api():
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        acc_resp = await client.get("https://api.huntflow.ru/v2/accounts", headers=headers)
        account_id = acc_resp.json()["items"][0]["id"]

        v_resp = await client.get(
            f"https://api.huntflow.ru/v2/accounts/{account_id}/vacancies",
            headers=headers,
            params={"mine": "true", "count": 100}
        )
        return [v['position'] for v in v_resp.json().get('items', [])]


def run_debug():
    print("⏳ Запрашиваю список ваших вакансий напрямую из Huntflow API...")
    try:
        loop = asyncio.get_event_loop()
        api_vac_names = loop.run_until_complete(get_my_vacancies_from_api())
    except Exception as e:
        print(f"❌ Ошибка API: {e}")
        return

    print(f"✅ Найдено вакансий в API, где вы участник: {len(api_vac_names)}")

    # Подключаемся к нашей базе
    engine = create_engine("sqlite:///cache/huntflow.db")
    df = pd.read_sql_table("applicants", engine)

    # Обрабатываем даты как в движке
    df['created_clean'] = (
                pd.to_datetime(df['created_at'], errors='coerce', utc=True) + pd.Timedelta(hours=3)).dt.tz_localize(
        None)

    START = datetime(2026, 3, 1)
    END = datetime(2026, 3, 31, 23, 59, 59)

    df['vacancy_clean'] = df['vacancy'].str.replace('🚩 ', '', regex=False)

    final_df = df[
        (df['created_clean'] >= START) &
        (df['created_clean'] <= END) &
        (df['vacancy_clean'].isin(api_vac_names))
        ].copy()

    print("\n" + "=" * 60)
    print(f"ИТОГОВЫЙ РАСЧЕТ (По списку вакансий из API):")
    print(f"Всего кандидатов: {len(final_df)} (Цель: 171)")
    print("=" * 60)

    if not final_df.empty:
        def map_source(s):
            if s == 'Не указан' or not s: return 'Другой'
            if 'Telegram' in s: return 'Другой'
            return s

        final_df['source_hf'] = final_df['source'].apply(map_source)
        summary = final_df['source_hf'].value_counts()
        print(summary.to_string())

        print("\nСверка с Хантфлоу:")
        target = {"Отклик с HeadHunter": 114, "HeadHunter": 50, "Другой": 4, "Рекомендация внутренняя": 2, "Политех": 1}
        for src, val in target.items():
            curr = summary.get(src, 0)
            print(f"{'✅' if curr == val else '❌'} {src}: {curr} (Нужно: {val})")


if __name__ == "__main__":
    run_debug()