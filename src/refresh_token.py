import requests
import json
from datetime import timedelta

EXISTING_REFRESH_TOKEN = "4bd9decc764775ecad0ca754109e6adf30b3925015a7aa9867cd1e3d528f7054"

REFRESH_URL = "https://api.huntflow.ru/v2/token/refresh"


def update_token():
    """
    Отправляет запрос на обновление токена и выводит результат.
    """
    if not EXISTING_REFRESH_TOKEN:
        print("ОШИБКА: Проверьте ваш refresh_token")
        return

    payload = {
        "refresh_token": EXISTING_REFRESH_TOKEN
    }

    headers = {
        "Content-Type": "application/json"
    }

    print(f"Отправка запроса на {REFRESH_URL} для обновления токена...")

    try:
        response = requests.post(REFRESH_URL, headers=headers, data=json.dumps(payload))

        if response.status_code == 200:
            new_tokens = response.json()
            access_token = new_tokens.get("access_token")
            new_refresh_token = new_tokens.get("refresh_token")
            access_token_expires = new_tokens.get("expires_in", 0)
            refresh_token_expires = new_tokens.get("refresh_token_expires_in", 0)

            access_days = access_token_expires / (60 * 60 * 24)
            refresh_days = refresh_token_expires / (60 * 60 * 24)

            print("\n--- УСПЕХ! Ваши токены обновлены. ---")
            print("\nНОВЫЙ access_token (скопируйте его в основной скрипт):")
            print(f"{access_token}")
            print(f"(Действителен: {access_token_expires} секунд, примерно {access_days:.1f} дней)")

            print("\nВАЖНО: Сохраните и этот НОВЫЙ refresh_token для следующего обновления!")
            print(f"{new_refresh_token}")
            print(f"(Действителен: {refresh_token_expires} секунд, примерно {refresh_days:.1f} дней)")

        else:
            print(f"\n--- ОШИБКА! Не удалось обновить токен. ---")
            print(f"Статус-код: {response.status_code}")
            print("Ответ сервера:")
            print(response.text)
            print("\nВозможная причина: ваш refresh_token недействителен или истек.")

    except requests.exceptions.RequestException as e:
        print(f"\n--- СЕТЕВАЯ ОШИБКА! ---")
        print(f"Не удалось подключиться к серверу Huntflow: {e}")


if __name__ == "__main__":
    update_token()