import requests
import os
import re
import sys

ENV_PATH = "/home/denis.leukhin/HiringReportAutomation/.env"
REFRESH_URL = "https://api.huntflow.ru/v2/token/refresh"


def main():
    if not os.path.exists(ENV_PATH):
        print(f"ОШИБКА: Файл {ENV_PATH} не найден")
        sys.exit(1)

    with open(ENV_PATH, 'r') as f:
        content = f.read()

    refresh_match = re.search(r'HUNTFLOW_REFRESH_TOKEN=(.*)', content)
    if not refresh_match:
        print("ОШИБКА: HUNTFLOW_REFRESH_TOKEN не найден в .env")
        sys.exit(1)

    current_refresh_token = refresh_match.group(1).strip().strip('"').strip("'")

    print(f"Обновляем токены через Huntflow...")
    try:
        resp = requests.post(
            REFRESH_URL,
            headers={"Content-Type": "application/json"},
            json={"refresh_token": current_refresh_token},
            timeout=30
        )

        if resp.status_code == 200:
            data = resp.json()
            new_access = data.get("access_token")
            new_refresh = data.get("refresh_token")

            content = re.sub(r'HUNTFLOW_ACCESS_TOKEN=.*', f'HUNTFLOW_ACCESS_TOKEN={new_access}', content)
            content = re.sub(r'HUNTFLOW_REFRESH_TOKEN=.*', f'HUNTFLOW_REFRESH_TOKEN={new_refresh}', content)

            with open(ENV_PATH, 'w') as f:
                f.write(content)

            print("УСПЕХ: Токены в .env обновлены.")
            sys.exit(0)
        else:
            print(f"ОШИБКА API: {resp.status_code} - {resp.text}")
            sys.exit(1)

    except Exception as e:
        print(f"ОШИБКА: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()