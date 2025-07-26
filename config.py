import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
PRIVATE_CHANNEL_ID =  os.getenv('PRIVATE_CHANNEL_ID')
INVITE_LINK =  os.getenv('INVITE_LINK')

# Состояния для ConversationHandler
CHECK_SUBSCRIPTION = 9
SUBSCRIPTION = -1
CHOOSING, ADDING_PHOTOS, DESCRIPTION, PRICE, CONFIRMATION, EDIT_CHOICE, EDIT_DESCRIPTION, EDIT_PRICE, EDIT_PHOTOS = range(9)
