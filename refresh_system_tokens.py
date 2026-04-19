import requests
import os
import re

# Путь к твоему .env файлу на продовой машине
ENV_PATH = "/home/denis.leukhin/PycharmProjects/HiringReportAutomation/.env"
REFRESH_URL = "https://api.huntflow.ru/v2/token/refresh"


def update_env_file(access_token, refresh_token):
    with open(ENV_PATH, 'r') as f:
        content = f.read()

    # Заменяем значения токенов в файле с помощью регулярок
    content = re.sub(r'HUNTFLOW_ACCESS_TOKEN=.*', f'HUNTFLOW_ACCESS_TOKEN={access_token}', content)
    content = re.sub(r'HUNTFLOW_REFRESH_TOKEN=.*', f'HUNTFLOW_REFRESH_TOKEN={refresh_token}', content)

    with open(ENV_PATH, 'w') as f:
        f.write(content)


def main():
    # 1. Читаем текущий refresh_token из .env
    with open(ENV_PATH, 'r') as f:
        env_data = f.read()
        refresh_match = re.search(r'HUNTFLOW_REFRESH_TOKEN=(.*)', env_data)
        if not refresh_match:
            print("ОШИБКА: Не нашел HUNTFLOW_REFRESH_TOKEN в .env")
            return
        current_refresh_token = refresh_match.group(1).strip()

    print(f"Обновление токенов через Huntflow...")
    try:
        resp = requests.post(
            REFRESH_URL,
            headers={"Content-Type": "application/json"},
            json={"refresh_token": current_refresh_token}
        )

        if resp.status_code == 200:
            data = resp.json()
            new_access = data.get("access_token")
            new_refresh = data.get("refresh_token")

            update_env_file(new_access, new_refresh)
            print("УСПЕХ: .env файл обновлен новыми токенами.")
            exit(0)
        else:
            print(f"ОШИБКА API: {resp.text}")
            exit(1)
    except Exception as e:
        print(f"СЕТЕВАЯ ОШИБКА: {e}")
        exit(1)


if __name__ == "__main__":
    main()