import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime

TARGET_ID = 236211
START = datetime(2026, 3, 1)
END = datetime(2026, 3, 31, 23, 59, 59)


def debug_171_split():
    engine = create_engine("sqlite:///cache/huntflow.db")
    df = pd.read_sql_table("applicants", engine)

    df['created_clean'] = (
                pd.to_datetime(df['created_at'], errors='coerce', utc=True) + pd.Timedelta(hours=3)).dt.tz_localize(
        None)
    march_apps = df[(df['created_clean'] >= START) & (df['created_clean'] <= END)].copy()

    mask_in_logs = df['stage_history'].str.contains(f'"recruiter_id": {TARGET_ID}', na=False)
    nastya_vacs = set(df[mask_in_logs]['vacancy'].unique())
    nastya_vacs.update(set(df[df['recruiter_id'] == TARGET_ID]['vacancy'].unique()))

    def check_eligibility(row):
        source = row['source']

        if source == "HeadHunter":
            return row['recruiter_id'] == TARGET_ID

        if source == "Отклик с HeadHunter":
            return row['vacancy'] in nastya_vacs

        if row['vacancy'] in nastya_vacs:
            return True

        if f'"recruiter_id": {TARGET_ID}' in str(row['stage_history']):
            return True

        return False

    march_apps['is_target'] = march_apps.apply(check_eligibility, axis=1)
    final_df = march_apps[march_apps['is_target'] == True].copy()

    print("\n" + "=" * 60)
    print(f"ИТОГОВЫЙ РАСЧЕТ (РАЗДЕЛЬНАЯ ЛОГИКА):")
    print(f"Всего кандидатов: {len(final_df)} (Цель: 171)")
    print("=" * 60)

    if not final_df.empty:
        # Маппинг для "Другой"
        target_sources = ["Отклик с HeadHunter", "HeadHunter", "Рекомендация внутренняя", "Политех"]
        final_df['source_hf'] = final_df['source'].apply(lambda x: x if x in target_sources else "Другой")

        summary = final_df['source_hf'].value_counts()
        print(summary.to_string())

        print("\n📊 СВЕРКА:")
        target = {
            "Отклик с HeadHunter": 114,
            "HeadHunter": 50,
            "Другой": 4,
            "Рекомендация внутренняя": 2,
            "Политех": 1
        }
        for src, val in target.items():
            curr = summary.get(src, 0)
            status = "✅" if curr == val else "❌"
            print(f"{status} {src}: {curr} (Нужно: {val})")


if __name__ == "__main__":
    debug_171_split()