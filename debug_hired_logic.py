import pandas as pd
import json
from sqlalchemy import create_engine
from datetime import datetime

# Настройки
START = datetime(2026, 3, 1)
END = datetime(2026, 3, 31, 23, 59, 59)
TARGET_RECRUITER_NAME = "Анастасия Прокопьева"

def debug_to_171():
    engine = create_engine("sqlite:///cache/huntflow.db")
    df = pd.read_sql_table("applicants", engine)
    coworkers = pd.read_sql_table("coworkers", engine)

    # 1. Находим ID Анастасии
    rec_row = coworkers[coworkers['name'].str.contains(TARGET_RECRUITER_NAME, na=False)]
    rec_id = int(rec_row.iloc[0]['id'])
    print(f"🔎 Ищем источники для {TARGET_RECRUITER_NAME} (ID: {rec_id})")

    # 2. Обрабатываем даты создания
    df['created_clean'] = (
                pd.to_datetime(df['created_at'], errors='coerce', utc=True) + pd.Timedelta(hours=3)).dt.tz_localize(
        None)

    # 3. Фильтруем ВСЕХ кандидатов, пришедших в Марте
    march_apps = df[(df['created_clean'] >= START) & (df['created_clean'] <= END)].copy()
    print(f"Всего новых кандидатов в компании за Март: {len(march_apps)}")

    # 4. ЛОГИКА АССОЦИАЦИИ:
    # Кандидат считается Настиным, если:
    # - Либо она владелец (recruiter_id)
    # - Либо она есть в stage_history

    def belongs_to_nastya(row):
        # Условие 1: Владение
        if row['recruiter_id'] == rec_id:
            return True

        # Условие 2: Участие (ищем ID в JSON истории)
        try:
            history_str = str(row['stage_history'])
            if f'"recruiter_id": {rec_id}' in history_str:
                return True
        except:
            pass

        return False

    march_apps['is_nastya'] = march_apps.apply(belongs_to_nastya, axis=1)
    final_df = march_apps[march_apps['is_nastya'] == True]

    print("\n" + "=" * 60)
    print(f"ИТОГОВЫЙ РЕЗУЛЬТАТ СКРИПТА:")
    print(f"Всего найдено кандидатов: {len(final_df)}")
    print("=" * 60)

    if not final_df.empty:
        # Группируем как в Хантфлоу
        summary = final_df['source'].value_counts()
        print(summary.to_string())

        print("\nСравнение с целью из Хантфлоу:")
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
    debug_to_171()