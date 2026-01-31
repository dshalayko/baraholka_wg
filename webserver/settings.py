import logging
import os

from dotenv import load_dotenv

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(levelname)s: %(message)s")

logger = logging.getLogger("webapp")

BOT_TOKEN = os.getenv("BOT_TOKEN")
MEDIA_STORAGE_CHAT_ID = os.getenv("MEDIA_STORAGE_CHAT_ID")

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
WEBAPP_DIR = os.path.join(BASE_DIR, "webapp")

FAVICON_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
    "<rect width='64' height='64' rx='14' fill='#1a1f2b'/>"
    "<circle cx='32' cy='32' r='18' fill='#3f8cff'/>"
    "</svg>"
)
