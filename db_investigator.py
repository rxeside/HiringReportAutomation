import sqlite3
import pandas as pd
from datetime import datetime


def investigate():
    print("РАССЛЕДОВАНИЕ: КУДА ПРОПАЛИ НАЙМЫ КРИСТИНЫ В МАРТЕ?\n")

    conn = sqlite3.connect("cache/huntflow.db")

    query = """
        SELECT 
            a.applicant_id, 
            a.vacancy, 
            a.hired_date, 
            c.name as recruiter_name
        FROM applicants a
        LEFT JOIN coworkers c ON a.recruiter_id = c.id
        WHERE a.hired_date >= '2026-03-01' AND a.hired_date <= '2026-03-23 23:59:59'
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print("В нашей базе ВООБЩЕ НЕТ людей, вышедших на работу в марте.")
        print("Значит, проблема в парсере логов (даты не сохранились).")
        return

    print(f"В нашей базе найдено {len(df)} человек, вышедших на работу в марте (по всей компании).\n")
    print("-" * 80)
    print(f"{'ID Кандидата':<15} | {'Дата выхода':<15} | {'Кому засчитан в нашей базе (Рекрутер)':<30}")
    print("-" * 80)

    for _, row in df.iterrows():
        print(f"{row['applicant_id']:<15} | {str(row['hired_date'])[:10]:<15} | {row['recruiter_name']:<30}")

    print("-" * 80)
    print("\n ПОСМОТРИ В ТАБЛИЦУ ВЫШЕ:")
    print(
        "Если ты видишь там 4 найма, но в колонке 'Кому засчитан' стоит НЕ Кристина (а, например, Илья или Софья) — значит, гипотеза подтвердилась.")
    print("Кристина закрыла людей на чужих вакансиях!")


if __name__ == "__main__":
    investigate()