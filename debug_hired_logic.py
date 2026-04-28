import pandas as pd
import json
from sqlalchemy import create_engine
from datetime import datetime

TARGET_NAME = "Анастасия Прокопьева"
START = datetime(2026, 3, 1)
END = datetime(2026, 3, 31, 23, 59, 59)


def belongs_to_recruiter(recruiter_id_in_db, stage_history_json, target_parts, target_id):
    if str(recruiter_id_in_db) == str(target_id):
        return True

    try:
        if f'"recruiter_id": {target_id}' in str(stage_history_json):
            return True
    except:
        pass
    return False


def debug_final_sources():
    engine = create_engine("sqlite:///cache/huntflow.db")
    print("🛰️ Загрузка данных из базы...")
    df = pd.read_sql_table("applicants", engine)
    coworkers = pd.read_sql_table("coworkers", engine)

    target_parts = TARGET_NAME.lower().split()
    target_id = None
    for _, cw in coworkers.iterrows():
        cw_name_lower = cw['name'].lower()
        if all(part in cw_name_lower for part in target_parts):
            target_id = cw['id']
            break

    print(f"✅ Определен ID рекрутера: {target_id}")

    df['created_clean'] = (
                pd.to_datetime(df['created_at'], errors='coerce', utc=True) + pd.Timedelta(hours=3)).dt.tz_localize(
        None)

    march_df = df[(df['created_clean'] >= START) & (df['created_clean'] <= END)].copy()

    march_df['is_target'] = march_df.apply(
        lambda row: belongs_to_recruiter(row['recruiter_id'], row['stage_history'], target_parts, target_id),
        axis=1
    )

    vac_stats = []

    final_df = march_df[march_df['is_target'] == True].copy()

    print("\n" + "=" * 60)
    print(f"ИТОГОВЫЙ РАСЧЕТ (Владение + Логи):")
    print(f"Всего кандидатов: {len(final_df)} (Цель: 171)")
    print("=" * 60)

    if not final_df.empty:
        target_sources = ["Отклик с HeadHunter", "HeadHunter", "Рекомендация внутренняя", "Политех"]
        final_df['source_hf'] = final_df['source'].apply(lambda x: x if x in target_sources else "Другой")

        summary = final_df['source_hf'].value_counts()
        print(summary.to_string())

        print("\n📊 СВЕРКА:")
        target = {"Отклик с HeadHunter": 114, "HeadHunter": 50, "Другой": 4, "Рекомендация внутренняя": 2, "Политех": 1}
        for src, val in target.items():
            curr = summary.get(src, 0)
            print(f"{'✅' if curr == val else '❌'} {src}: {curr} (Нужно: {val})")

    if len(final_df) < 171:
        print("\n🔍 Ищу кандидатов на 'совместных' вакансиях...")
        nastya_touched_vacs = set(
            df[df['stage_history'].str.contains(f'"recruiter_id": {target_id}', na=False)]['vacancy'].unique())

        missing = march_df[(march_df['is_target'] == False) & (march_df['vacancy'].isin(nastya_touched_vacs))]
        print(f"Найдено еще {len(missing)} кандидатов на 'её' вакансиях, но без её логов.")
        if not missing.empty:
            print("Топ вакансий с 'потерянными' людьми:")
            print(missing['vacancy'].value_counts().head(5))


if __name__ == "__main__":
    debug_final_sources()