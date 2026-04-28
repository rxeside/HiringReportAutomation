import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime

# Настройки
START = datetime(2026, 3, 1)
END = datetime(2026, 3, 31, 23, 59, 59)
TARGET_RECRUITER = "Анастасия Прокопьева"

def debug_sources():
    engine = create_engine("sqlite:///cache/huntflow.db")
    df = pd.read_sql_table("applicants", engine)
    coworkers = pd.read_sql_table("coworkers", engine)

    # Находим ID Анастасии
    rec_row = coworkers[coworkers['name'].str.contains(TARGET_RECRUITER, na=False)]
    if rec_row.empty:
        print("Рекрутер не найден")
        return
    rec_id = rec_row.iloc[0]['id']
    print(f"Анализ для: {TARGET_RECRUITER} (ID: {rec_id})")

    df['created_clean'] = (pd.to_datetime(df['created_at'], errors='coerce', utc=True) + pd.Timedelta(hours=3)).dt.tz_localize(None)

    print("\n" + "="*60)
    print(f"ВАРИАНТ 1: Только те, кто закреплен за Анастасией в базе")
    print("="*60)
    v1_df = df[
        (df['recruiter_id'] == rec_id) &
        (df['created_clean'] >= START) &
        (df['created_clean'] <= END)
    ]
    print(f"Итого: {len(v1_df)} (Цель: 171)")
    if not v1_df.empty:
        print(v1_df['source'].value_counts().to_string())

    print("\n" + "="*60)
    print(f"ВАРИАНТ 2: Анастасия + Те, у кого НЕ указан рекрутер")
    print("="*60)
    v2_df = df[
        ((df['recruiter_id'] == rec_id) | (df['recruiter_id'].isna()) | (df['recruiter_id'] == 0)) &
        (df['created_clean'] >= START) &
        (df['created_clean'] <= END)
    ]
    print(f"Итого: {len(v2_df)} (Цель: 171)")

    print("\n" + "="*60)
    print(f"ВАРИАНТ 3: Поиск 'потерянных' кандидатов")
    print("="*60)
    other_march = df[
        (df['recruiter_id'] != rec_id) &
        (df['created_clean'] >= START) &
        (df['created_clean'] <= END)
    ]
    print(f"Всего других кандидатов в марте (на других рекрутерах): {len(other_march)}")
    print("\nТоп вакансий марта, где Анастасия НЕ числится владельцем:")
    if not other_march.empty:
        print(other_march['vacancy'].value_counts().head(10).to_string())

if __name__ == "__main__":
    debug_sources()