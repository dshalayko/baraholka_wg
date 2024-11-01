import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Получаем значения из переменных окружения
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PRIVATE_CHANNEL_ID = os.getenv('PRIVATE_CHANNEL_ID')
SESSION_NAME = os.getenv('SESSION_NAME')
MAIN_BOT_USERNAME = os.getenv('MAIN_BOT_USERNAME')
