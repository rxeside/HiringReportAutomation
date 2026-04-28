import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime

# Настройки
START = datetime(2026, 3, 1)
END = datetime(2026, 3, 31, 23, 59, 59)
TARGET_RECRUITER_NAME = "Анастасия Прокопьева"


def debug_vacancy_membership():
    engine = create_engine("sqlite:///cache/huntflow.db")
    df = pd.read_sql_table("applicants", engine)
    coworkers = pd.read_sql_table("coworkers", engine)

    rec_row = coworkers[coworkers['name'].str.contains(TARGET_RECRUITER_NAME, na=False)]
    rec_id = int(rec_row.iloc[0]['id'])

    # Приводим даты
    df['created_clean'] = (
                pd.to_datetime(df['created_at'], errors='coerce', utc=True) + pd.Timedelta(hours=3)).dt.tz_localize(
        None)

    # 1. Находим список ВСЕХ вакансий, к которым Анастасия имеет отношение
    # (Где она либо владелец, либо хоть раз мелькнула в логах любого кандидата)
    print(f"🔍 Определяю список вакансий Анастасии...")

    nastya_vacancies = set(df[df['recruiter_id'] == rec_id]['vacancy'].unique())

    # Добавляем вакансии, где она просто работала с людьми (через логи)
    for _, row in df.iterrows():
        if f'"recruiter_id": {rec_id}' in str(row['stage_history']):
            nastya_vacancies.add(row['vacancy'])

    print(f"✅ Найдено вакансий с участием Анастасии: {len(nastya_vacancies)}")

    # 2. Берем ВСЕХ кандидатов марта на ЭТИХ вакансиях
    march_apps = df[
        (df['created_clean'] >= START) &
        (df['created_clean'] <= END) &
        (df['vacancy'].isin(nastya_vacancies))
        ].copy()

    print("\n" + "=" * 60)
    print(f"РЕЗУЛЬТАТ ПО ЛОГИКЕ 'УЧАСТИЕ В ВАКАНСИИ':")
    print(f"Всего найдено кандидатов: {len(march_apps)}")
    print("=" * 60)

    if not march_apps.empty:
        # Хантфлоу в отчетах маппит "Не указан" в "Другой"
        march_apps['source_mapped'] = march_apps['source'].replace('Не указан', 'Другой')

        summary = march_apps['source_mapped'].value_counts()
        print(summary.to_string())

        print("\nСравнение с Хантфлоу (Цель: 171):")
        target = {
            "Отклик с HeadHunter": 114,
            "HeadHunter": 50,
            "Другой": 4,
            "Рекомендация внутренняя": 2,
            "Политех": 1
        }
        for src, val in target.items():
            current = summary.get(src, 0)
            diff = current - val
            status = "✅" if diff == 0 else "❌"
            print(f"{status} {src}: {current} (Нужно: {val})")


if __name__ == "__main__":
    debug_vacancy_membership()