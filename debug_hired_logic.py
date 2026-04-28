import pandas as pd
import json
from sqlalchemy import create_engine
from datetime import datetime

TARGET_ID = 236211
START = datetime(2026, 3, 1)
END = datetime(2026, 3, 31, 23, 59, 59)


def debug_sources_to_171():
    engine = create_engine("sqlite:///cache/huntflow.db")
    print("🛰️ Загрузка данных из базы...")
    df = pd.read_sql_table("applicants", engine)

    df['created_clean'] = (
                pd.to_datetime(df['created_at'], errors='coerce', utc=True) + pd.Timedelta(hours=3)).dt.tz_localize(
        None)


    print("🔍 Составляю список 'активных' вакансий рекрутера...")

    owned_vacs = set(df[df['recruiter_id'] == TARGET_ID]['vacancy'].unique())

    mask_in_logs = df['stage_history'].str.contains(f'"recruiter_id": {TARGET_ID}', na=False)
    touched_vacs = set(df[mask_in_logs]['vacancy'].unique())

    all_target_vacs = owned_vacs.union(touched_vacs)
    print(f"✅ Найдено вакансий с участием рекрутера: {len(all_target_vacs)}")

    sources_df = df[
        (df['created_clean'] >= START) &
        (df['created_clean'] <= END) &
        (df['vacancy'].isin(all_target_vacs))
        ].copy()

    print("\n" + "=" * 60)
    print(f"ИТОГОВЫЙ РАСЧЕТ (ЛОГИКА УЧАСТИЯ):")
    print(f"Всего кандидатов найдено: {len(sources_df)} (Цель: 171)")
    print("=" * 60)

    if not sources_df.empty:
        known_sources = ["Отклик с HeadHunter", "HeadHunter", "Рекомендация внутренняя", "Политех"]

        def map_source_to_hf(s):
            if s in known_sources:
                return s
            return "Другой"

        sources_df['source_hf'] = sources_df['source'].apply(map_source_to_hf)

        summary = sources_df['source_hf'].value_counts()
        print(summary.to_string())

        print("\n📊 СВЕРКА С ХАНТФЛОУ:")
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
    debug_sources_to_171()