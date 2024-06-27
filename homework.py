import logging
import os
import time

import requests
import telegram
from dotenv import load_dotenv
from http import HTTPStatus
from typing import Union

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens() -> None:
    """Функция для проверки наличия переменных окружения."""

    if (
        PRACTICUM_TOKEN is None
        or TELEGRAM_TOKEN is None
        or TELEGRAM_CHAT_ID is None
    ):
        logging.critical('Отсутсвуют обязательные '
                         'переменные окружения.'
                         'Программа принудительно остановлена.')
        exit()


def send_message(bot, message) -> None:
    """Отправка сообщения пользователю."""

    try:
        logging.debug(f'Бот отправил сообщение {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)

    except Exception as error:
        logging.error(error)


def get_api_answer(timestamp: dict) -> Union[dict, str]:
    """Отправка запроса к API."""

    try:
        logging.info(f'Отправка запроса на {ENDPOINT} '
                     f'с параметрами {timestamp}')
        response = requests.get(ENDPOINT, headers=HEADERS, params=timestamp)
        if response.status_code != HTTPStatus.OK:
            logging.error(f'Эндпоинт {response.url} недоступен. '
                          f'Код ответа: {response.status_code}')
    except requests.RequestException as error:
        logging.error(error)

    return response.json()


def check_response(response: dict) -> list:
    """Проверяет ответ API на соответствие документации."""

    if not isinstance(response, dict):
        message = 'Некорректный тип данных ответа.'
        logging.error(message)
        raise TypeError(message)

    if not isinstance(response.get('homeworks'), list):
        message = 'Неверный тип данных в ответе.'
        logging.error(message)
        raise TypeError(message)

    if 'homeworks' not in response:
        message = 'Отсутствуют необходимые данные в ответе.'
        logging.error(message)
        raise KeyError(message)

    return response['homeworks']


def parse_status(homework: dict) -> str:
    """Получение информации о состоянии домашней работы."""

    if not homework.get('homework_name'):
        homework_name = 'Notnamed homework'
        message = 'Отсутствует имя домашней работы.'
        logging.warning(message)
        raise NameError(message)

    else:
        homework_name = homework.get('homework_name')

    status = homework.get('status')
    if 'status' not in homework:
        message = 'Отсутстует ключ homework_status.'
        logging.error(message)

    verdict = HOMEWORK_VERDICTS.get(status)
    if status not in HOMEWORK_VERDICTS:
        message = 'Неизвестный статус работы.'
        logging.error(message)
        raise NameError(message)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""

    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    while True:
        try:
            timestamp = int(time.time())
            payload = {'from_date': timestamp}
            api_answer = get_api_answer(payload)
            checked_answer = check_response(api_answer)

            for homework in checked_answer:
                homework_status = parse_status(homework)
                send_message(bot, homework_status)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s - %(name)s',
        level=logging.INFO,
    )

    main()
