import logging
import os
import sys
import time
from http import HTTPStatus
from typing import Union

import requests
from dotenv import load_dotenv
from telebot import apihelper, TeleBot

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
SOURCE = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')

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
    missing_tokens = []
    for token in SOURCE:
        if not globals()[token]:
            missing_tokens.append(token)

    missing_tokens_message = ', '.join(missing_tokens)

    if missing_tokens_message:
        logging.critical('Отсутствуют обязательные '
                         f'переменные окружения {missing_tokens_message}. '
                         'Программа принудительно завершена.')
        sys.exit(1)


def send_message(bot, message) -> None:
    """Отправка сообщения пользователю."""
    logging.debug(f'Бот отправил сообщение {message}')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)

    except (apihelper.ApiException, requests.RequestException) as error:
        logging.error(error)


def get_api_answer(timestamp: int) -> Union[dict, str]:
    """Отправка запроса к API."""
    payload = {'from_date': timestamp}
    logging.info(f'Отправка запроса на {ENDPOINT} '
                 f'с параметрами {payload}')

    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)

    except requests.RequestException as error:
        raise ConnectionError(f'Ошибка при отправке запроса к {ENDPOINT} '
                              f'с параметрами {payload}: {error}')

    if response.status_code != HTTPStatus.OK:
        raise ValueError(f'Эндпоинт {response.url} недоступен. '
                         f'Код ответа: {response.status_code}')

    return response.json()


def check_response(response: dict) -> list:
    """Проверяет ответ API на соответствие документации."""
    logging.debug('Проверка ответа сервера.')
    if not isinstance(response, dict):
        raise TypeError(f'Ответ типа {type(response)}. Ожидался тип dict.')

    try:
        homeworks = response['homeworks']
    except KeyError:
        raise KeyError('Отсутствует ключ homeworks.')

    if not isinstance(homeworks, list):
        raise TypeError(f'Ответ типа {type(homeworks)}. Ожидался тип list.')

    logging.debug('Ответ сервера успешно проверен.')

    return response['homeworks']


def parse_status(homework: dict) -> str:
    """Получение информации о состоянии домашней работы."""
    logging.debug('Проверка статуса домашней работы.')

    try:
        homework_name = homework['homework_name']
    except KeyError:
        raise KeyError('Отсутствует ключ homework_name.')

    try:
        status = homework['status']
    except KeyError:
        raise KeyError('Отсутстует ключ status.')

    try:
        verdict = HOMEWORK_VERDICTS[status]
    except KeyError:
        raise KeyError(f'Отсутствует ключ {status} '
                       'в HOMEWORK_VERDICTS.')

    logging.debug('Статус домашней работы успешно проверен.')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    last_message = ''
    timestamp = int(time.time())

    while True:
        try:
            api_answer = get_api_answer(timestamp)
            checked_answer = check_response(api_answer)

            if checked_answer:
                homework = checked_answer[0]
                message = parse_status(homework)
                send_message(bot, message)
                last_message = message
                logging.info('Отправлено новое сообщение.')

            else:
                logging.debug('Статус не изменился.')

            timestamp = int(time.time())

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)

            if message != last_message:
                send_message(bot, message)
                last_message = message

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format=('%(asctime)s - %(levelname)s - %(message)s '
                '- %(name)s, line %(lineno)d, in %(funcName)s')
    )
    logging.StreamHandler(stream=sys.stdout)

    main()
