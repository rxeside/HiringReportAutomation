import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime

# Настройки
START = datetime(2026, 3, 1)
END = datetime(2026, 3, 31, 23, 59, 59)
TARGET_RECRUITER_NAME = "Анастасия Прокопьева"


def debug_final_171():
    engine = create_engine("sqlite:///cache/huntflow.db")
    df = pd.read_sql_table("applicants", engine)
    coworkers = pd.read_sql_table("coworkers", engine)

    rec_row = coworkers[coworkers['name'].str.contains(TARGET_RECRUITER_NAME, na=False)]
    rec_id = int(rec_row.iloc[0]['id'])

    df['created_clean'] = (
                pd.to_datetime(df['created_at'], errors='coerce', utc=True) + pd.Timedelta(hours=3)).dt.tz_localize(
        None)

    print("📊 Ищу 'свои' вакансии по активности...")

    vac_activity = {}
    for _, row in df.iterrows():
        if f'"recruiter_id": {rec_id}' in str(row['stage_history']):
            v = row['vacancy']
            vac_activity[v] = vac_activity.get(v, 0) + 1

    active_vacs = [v for v, count in vac_activity.items() if count > 0]

    def is_171_candidate(row):
        if row['recruiter_id'] == rec_id: return True
        if f'"recruiter_id": {rec_id}' in str(row['stage_history']): return True
        if (row['recruiter_id'] == 0 or pd.isna(row['recruiter_id'])) and row['vacancy'] in active_vacs: return True
        return False

    march_apps = df[(df['created_clean'] >= START) & (df['created_clean'] <= END)].copy()
    march_apps['is_target'] = march_apps.apply(is_171_candidate, axis=1)

    final_df = march_apps[march_apps['is_target'] == True]

    print("\n" + "=" * 60)
    print(f"ИТОГОВЫЙ РАСЧЕТ:")
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
    debug_final_171()