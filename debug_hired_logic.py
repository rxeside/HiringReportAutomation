import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime

TARGET_ID = 236211
START = datetime(2026, 3, 1)
END = datetime(2026, 3, 31, 23, 59, 59)

ALLOWED_NAMES = [
    "Королев Илья", "Миргаязов Руслан",
    "Прокопьева Анастасия", "Таныгина Кристина", "Чихалова Татьяна",
    "Щербик Софья", "Игнатенко Валерия", "Бреднева Светлана"
]


def debug_171_formula():
    engine = create_engine("sqlite:///cache/huntflow.db")
    df = pd.read_sql_table("applicants", engine)
    coworkers = pd.read_sql_table("coworkers", engine)

    def is_allowed(name):
        n = name.lower()
        for a in ALLOWED_NAMES:
            parts = a.lower().split()
            if all(p in n for p in parts): return True
        return False

    allowed_ids = set(coworkers[coworkers['name'].apply(is_allowed)]['id'].tolist())
    print(f"✅ Всего разрешенных рекрутеров в системе: {len(allowed_ids)}")

    df['created_clean'] = (
                pd.to_datetime(df['created_at'], errors='coerce', utc=True) + pd.Timedelta(hours=3)).dt.tz_localize(
        None)
    march_apps = df[(df['created_clean'] >= START) & (df['created_clean'] <= END)].copy()

    mask_in_logs = df['stage_history'].str.contains(f'"recruiter_id": {TARGET_ID}', na=False)
    nastya_vacs = set(df[mask_in_logs]['vacancy'].unique())
    nastya_vacs.update(set(df[df['recruiter_id'] == TARGET_ID]['vacancy'].unique()))
    print(f"✅ Найдено вакансий с участием Анастасии: {len(nastya_vacs)}")

    def check_171(row):
        if row['recruiter_id'] == TARGET_ID: return True
        if f'"recruiter_id": {TARGET_ID}' in str(row['stage_history']): return True

        if row['vacancy'] in nastya_vacs:
            if row['recruiter_id'] not in allowed_ids:
                return True

        return False

    march_apps['is_target'] = march_apps.apply(check_171, axis=1)
    final_df = march_apps[march_apps['is_target'] == True].copy()

    print("\n" + "=" * 60)
    print(f"РЕЗУЛЬТАТ РАСЧЕТА:")
    print(f"Всего кандидатов: {len(final_df)} (Цель: 171)")
    print("=" * 60)

    if not final_df.empty:
        target_sources = ["Отклик с HeadHunter", "HeadHunter", "Рекомендация внутренняя", "Политех"]
        final_df['source_hf'] = final_df['source'].apply(lambda x: x if x in target_sources else "Другой")

        summary = final_df['source_hf'].value_counts()
        print(summary.to_string())

        print("\n📊 СВЕРКА С ХАНТФЛОУ:")
        goal = {"Отклик с HeadHunter": 114, "HeadHunter": 50, "Другой": 4, "Рекомендация внутренняя": 2, "Политех": 1}
        for src, val in goal.items():
            curr = summary.get(src, 0)
            status = "✅" if curr == val else "❌"
            print(f"{status} {src}: {curr} (Нужно: {val})")


if __name__ == "__main__":
    debug_171_formula()