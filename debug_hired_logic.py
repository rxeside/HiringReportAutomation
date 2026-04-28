import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime

target_names_list = [
    "Glotov", "Kiselev", "Безгачёва", "Бова", "Бородина", "Власова", "Война",
    "Гогорева", "Григорьева", "Гриценко", "Зайцева", "Касьянов", "Ким",
    "Ковряженкова", "Курбатова", "Лавренко", "Липкина", "Любко", "Магомедова",
    "Марковская", "Матвеева", "Нестеров", "Нехаев", "Никишина", "Николаева",
    "Панова", "Пантелеева", "Романов", "Савин", "Сидорова", "Смирнова",
    "Солодовник", "Ткачук", "Чаюсупов", "Черепанов", "Чибисова", "Шлапак",
    "Шопина", "Шпичак", "Шумный", "Шумских"
]


def debug_by_names():
    engine = create_engine("sqlite:///cache/huntflow.db")
    df = pd.read_sql_table("applicants", engine)

    print(f"🔎 Ищу {len(target_names_list)} человек из твоего списка в базе...")

    found_apps = []
    for surname in target_names_list:
        match = df[df['name'].str.contains(surname, case=False, na=False)]
        if not match.empty:
            found_apps.append(match)

    if not found_apps:
        print("❌ Никого не нашли. Проверь базу.")
        return

    found_df = pd.concat(found_apps).drop_duplicates(subset=['applicant_id', 'vacancy'])
    print(f"✅ Найдено в базе: {len(found_df)} из {len(target_names_list)}")

    analysis = found_df.groupby(['vacancy', 'recruiter_id']).size().reset_index(name='count')
    analysis = analysis.sort_values('count', ascending=False)

    print("\n📊 АНАЛИЗ ВАКАНСИЙ ЭТИХ ЛЮДЕЙ:")
    print("-" * 80)
    print(f"{'Название вакансии':<50} | {'ID Рекр':<10} | {'Кол-во'}")
    print("-" * 80)
    for _, row in analysis.iterrows():
        print(f"{row['vacancy'][:50]:<50} | {str(row['recruiter_id']):<10} | {row['count']}")

    print("\n🚀 ПРОВЕРКА ГИПОТЕЗЫ 'ВАКАНСИИ ЦЕЛИКОМ':")
    target_vacancies = found_df['vacancy'].unique()

    df['created_clean'] = (
                pd.to_datetime(df['created_at'], errors='coerce', utc=True) + pd.Timedelta(hours=3)).dt.tz_localize(
        None)
    START, END = datetime(2026, 3, 1), datetime(2026, 3, 31, 23, 59, 59)

    march_apps_on_these_vacs = df[
        (df['created_clean'] >= START) &
        (df['created_clean'] <= END) &
        (df['vacancy'].isin(target_vacancies))
        ]

    print(f"Всего кандидатов в марте на этих вакансиях: {len(march_apps_on_these_vacs)}")
    print(march_apps_on_these_vacs['source'].value_counts())


if __name__ == "__main__":
    debug_by_names()