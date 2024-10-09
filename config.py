import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')  # Например, '@my_channel'


# Состояния для ConversationHandler
CHECK_SUBSCRIPTION = range(999)
SUBSCRIPTION = -1
CHOOSING, ADDING_PHOTOS, DESCRIPTION, PRICE, CONFIRMATION, EDIT_CHOICE, EDIT_DESCRIPTION, EDIT_PRICE, EDIT_PHOTOS = range(9)
