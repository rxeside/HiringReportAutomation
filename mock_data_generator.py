import json
import random
from datetime import datetime, timedelta
import os

OUTPUT_FILE = "cache/analytics_data.json"
COUNT = 300

VACANCIES = [
    "Проджект в PD с потенциалом лида",
    "Performance Marketing Manager",
    "System Administrator",
    "SMM Specialist",
    "Frontend Developer"
]

RECRUITERS = {
    101: "Анна Иванова",
    102: "Петр Петров",
    103: "Мария Сидорова"
}

SOURCES = ["hh.ru", "LinkedIn", "Telegram", "Рекомендация", "Career.habr"]

REJECTION_REASONS = [
    "Не подходит по софтам",
    "Не подходит график работы",
    "Низкий уровень квалификации",
    "Отказ кандидата (оффер)",
    "Дорого"
]

STAGES = [
    "коннект",
    "интервью с HR",
    "интервью с заказчиком",
    "финальное интервью",
    "выставлен оффер",
    "вышел на работу",
    "испытательный срок пройден"
]


def random_date(start, end):
    return start + timedelta(
        seconds=random.randint(0, int((end - start).total_seconds()))
    )


def generate_mock_data():
    data = []

    # Генерируем данные за последние 3 месяца
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    for i in range(COUNT):
        vacancy = random.choice(VACANCIES)
        recruiter_id = random.choice(list(RECRUITERS.keys()))
        source = random.choice(SOURCES)

        max_stage_index = random.choices(
            range(len(STAGES)),
            weights=[30, 20, 15, 10, 5, 3, 2],
            k=1
        )[0]

        reached_stages = STAGES[:max_stage_index + 1]
        current_status = reached_stages[-1]

        created_at = random_date(start_date, end_date - timedelta(days=10))

        logs = []
        current_log_date = created_at

        for stage in reached_stages:
            current_log_date += timedelta(days=random.randint(1, 5))
            if current_log_date > end_date:
                current_log_date = end_date

            logs.append({
                "status": stage,
                "date": current_log_date.isoformat(),
                "type": "status_change"
            })

        rejection_reason = None
        if current_status != "испытательный срок пройден":
            if random.random() < 0.8:
                rejection_reason = random.choice(REJECTION_REASONS)
                logs.append({
                    "status": "Отказ",
                    "date": (current_log_date + timedelta(days=1)).isoformat(),
                    "type": "rejection"
                })

        is_hired = "вышел на работу" in reached_stages

        offer_date = next((l["date"] for l in logs if l["status"] == "выставлен оффер"), None)
        hired_date = next((l["date"] for l in logs if l["status"] == "вышел на работу"), None)

        applicant = {
            "id": i + 1000,
            "vacancy": vacancy,
            "recruiter_id": recruiter_id,
            "recruiter_name": RECRUITERS[recruiter_id],
            "source": source,
            "current_status": current_status,
            "rejection_reason": rejection_reason,
            "created_at": created_at.isoformat(),
            "offer_date": offer_date,
            "hired_date": hired_date,
            "is_hired": is_hired,
            "logs": logs
        }
        data.append(applicant)

    # Сохраняем
    os.makedirs("cache", exist_ok=True)
    final_structure = {
        "last_updated": datetime.now().isoformat(),
        "applicants": data,
        "coworkers": RECRUITERS
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_structure, f, indent=4, ensure_ascii=False)

    print(f"Сгенерировано {COUNT} кандидатов в файле {OUTPUT_FILE}")


if __name__ == "__main__":
    generate_mock_data()