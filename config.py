from environs import Env

env = Env()
env.read_env()

BOT_TOKEN = env.str("BOT_TOKEN")
SHEET_ID = env.str("SHEET_ID")
WORKSHEET_TITLE = env.str("WORKSHEET_TITLE", default="Sheet1")
REQUIRED_STATUS = env.str("REQUIRED_STATUS", default="faol mehnat shartnomasiga ega")
ADMIN_IDS = env.list("ADMIN_IDS", subcast=int, default=[]) 