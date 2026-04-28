import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime

START = datetime(2026, 3, 1)
END = datetime(2026, 3, 31, 23, 59, 59)
RECRUITER_NAME = "Татьяна Чихалова"


def audit_hire():
    engine = create_engine("sqlite:///cache/huntflow.db")

    df = pd.read_sql_table("applicants", engine)
    coworkers = pd.read_sql_table("coworkers", engine)

    rec_row = coworkers[coworkers['name'].str.contains(RECRUITER_NAME, na=False)]
    if rec_row.empty:
        print("❌ Рекрутер не найден")
        return
    rec_id = rec_row.iloc[0]['id']

    def process_dt(val):
        if not val: return pd.NaT
        return (pd.to_datetime(val, errors='coerce', utc=True) + pd.Timedelta(hours=3)).tz_localize(None)

    df['hired_date_clean'] = df['hired_date'].apply(process_dt)
    df['vac_created_clean'] = df['vacancy_created_at'].apply(process_dt)

    hired_march = df[
        (df['recruiter_id'] == rec_id) &
        (df['hired_date_clean'] >= START) &
        (df['hired_date_clean'] <= END)
        ].copy()

    print(f"📊 АУДИТ НАЙМОВ: {RECRUITER_NAME} (Март 2026)")
    print(f"Найдено человек в расчете: {len(hired_march)}")
    print("-" * 120)

    if hired_march.empty:
        print("Странно, в этом периоде наймов не найдено.")
        return

    total_days = 0
    for _, row in hired_march.iterrows():
        diff_seconds = (row['hired_date_clean'] - row['vac_created_clean']).total_seconds()
        days = diff_seconds / 86400.0
        total_days += days

        print(f" Кандидат:      {row['name']}")
        print(f" Вакансия:       {row['vacancy']}")
        print(f" Создана (DB):   {row['vac_created_clean']} (Сырая: {row['vacancy_created_at']})")
        print(f" Нанят (DB):     {row['hired_date_clean']} (Сырая: {row['hired_date']})")
        print(f" Срок закрытия:  {days:.2f} дн.")
        print("-" * 40)

    avg = total_days / len(hired_march)
    print(f" ИТОГОВОЕ СРЕДНЕЕ В БАЗЕ: {avg:.1f} дн.")


if __name__ == "__main__": audit_hire()