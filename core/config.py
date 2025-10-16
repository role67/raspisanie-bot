import os
from dotenv import load_dotenv

# Проверяем наличие файла .env
if not os.path.exists(".env"):
    print("ВНИМАНИЕ: Файл .env не найден в корне проекта!")
else:
    load_dotenv()

# Токен Telegram-бота
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ID администраторов (список строк)
ADMIN_IDS = os.getenv("ADMIN_IDS", "").split(',')

# URL для подключения к базе данных
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ВНИМАНИЕ: DATABASE_URL не найден в переменных окружения!")
else:
    print(f"DATABASE_URL загружен: {DATABASE_URL}")

# Интервал парсинга в минутах
try:
    PARSE_INTERVAL_MINUTES = int(os.getenv("PARSE_INTERVAL_MINUTES", "15"))
except (ValueError, TypeError):
    PARSE_INTERVAL_MINUTES = 15

# URL для вебхука
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# URL-адреса для парсинга
SCHEDULE_URL = os.getenv("SCHEDULE_URL")
REPLACEMENTS_URL = os.getenv("REPLACEMENTS_URL")
MAIN_SCHEDULE_URL = os.getenv("MAIN_SCHEDULE_URL")

# Контакт для поддержки
SUPPORT_CONTACT = os.getenv("SUPPORT_CONTACT", "@your_support_username")

# Часовой пояс
TIMEZONE = "Europe/Moscow"
