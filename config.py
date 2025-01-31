import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
PRIVATE_CHANNEL_ID =  os.getenv('PRIVATE_CHANNEL_ID')
INVITE_LINK =  os.getenv('INVITE_LINK')
API_ID =  os.getenv('API_ID')
API_HASH =  os.getenv('API_HASH')
CHAT_NAME =  os.getenv('CHAT_NAME')
CHAT_ID =  os.getenv('CHAT_ID')
DB_PATH =  os.getenv('DB_PATH')

# Состояния для ConversationHandler
CHECK_SUBSCRIPTION = range(999)
SUBSCRIPTION = -1
CHOOSING, ADDING_PHOTOS, EDIT_CHOICE, EDIT_DESCRIPTION, EDIT_PRICE, EDIT_PHOTOS = range(6)
ASK_PHOTO_ACTION = range(10)