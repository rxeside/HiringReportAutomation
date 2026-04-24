import pandas as pd
import json
from sqlalchemy import create_engine
from datetime import datetime

# Настройки периода (как на фронтенде)
START = datetime(2026, 3, 1)
END = datetime(2026, 3, 31, 23, 59, 59)


def debug_hired():
    engine = create_engine("sqlite:///cache/huntflow.db")
    print("🛰️ Загрузка данных из базы...")

    df = pd.read_sql("SELECT name, hired_date, current_status, stage_history FROM applicants WHERE is_hired = 1",
                     engine)

    if df.empty:
        print("ОШИБКА: В базе вообще нет пометок 'is_hired = 1'. Проблема в парсере.")
        return

    print(f"✅ Всего нанятых в базе: {len(df)}")

    df['hired_date_dt'] = pd.to_datetime(df['hired_date'], errors='coerce')

    df['hired_date_shifted'] = (df['hired_date_dt'] + pd.Timedelta(hours=3)).dt.tz_localize(None)

    print("\n🧐 Проверка конкретных дат (первые 5):")
    print("-" * 100)
    print(f"{'Имя':<25} | {'Сырая дата':<20} | {'После shift+3h':<20} | {'Входит в Март?'}")
    print("-" * 100)

    for _, row in df.head(10).iterrows():
        in_march = START <= row['hired_date_shifted'] <= END
        status = "✅ ДА" if in_march else "❌ НЕТ"
        print(
            f"{row['name'][:25]:<25} | {str(row['hired_date']):<20} | {str(row['hired_date_shifted']):<20} | {status}")

    # 3. Проверка истории событий (events_df)
    print("\n🔍 Проверка истории этапов (stage_history):")
    all_events = []
    for _, row in df.iterrows():
        history = json.loads(row['stage_history'])
        for ev in history:
            if ev.get('custom_stage') == 'вышел на работу':
                all_events.append({
                    'name': row['name'],
                    'date_in_history': ev.get('date')
                })

    events_df = pd.DataFrame(all_events)
    if not events_df.empty:
        events_df['date_dt'] = pd.to_datetime(events_df['date_in_history'], errors='coerce')
        events_df['date_final'] = (events_df['date_dt'] + pd.Timedelta(hours=3)).dt.tz_localize(None)

        march_events = events_df[(events_df['date_final'] >= START) & (events_df['date_final'] <= END)]
        print(f"Наймов в марте через events_df: {len(march_events)}")
    else:
        print("❌ В stage_history не найдено этапов 'вышел на работу'!")


if __name__ == "__main__":
    debug_hired()