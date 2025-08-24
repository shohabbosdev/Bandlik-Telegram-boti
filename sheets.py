import gspread_asyncio
from google.oauth2.service_account import Credentials
from config import SHEET_ID, WORKSHEET_TITLE
from cachetools import TTLCache
import time
import os
import json
import base64

# Kesh sozlamalari: 5 daqiqa (300 soniya) davomida ma'lumotlarni saqlaydi
cache = TTLCache(maxsize=1, ttl=300)

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def get_credentials():
    """
    Environment variable'dan credentials'ni olish va Google Credentials obyektini yaratish
    """
    try:
        # Environment variable'dan base64 encoded credentials'ni olish
        encoded_credentials = os.environ.get('GOOGLE_CREDENTIALS')
        
        if not encoded_credentials:
            # Local development uchun fayl orqali o'qish
            if os.path.exists("credentials.json"):
                return Credentials.from_service_account_file("credentials.json", scopes=SCOPE)
            else:
                raise ValueError("GOOGLE_CREDENTIALS environment variable yoki credentials.json fayli topilmadi")
        
        # Base64'dan decode qilish
        credentials_json = base64.b64decode(encoded_credentials).decode('utf-8')
        credentials_dict = json.loads(credentials_json)
        
        # Google credentials obyektini yaratish
        credentials = Credentials.from_service_account_info(
            credentials_dict,
            scopes=SCOPE
        )
        
        return credentials
        
    except Exception as e:
        raise Exception(f"Credentials yuklashda xatolik: {str(e)}")

# Credentials'ni olish
CREDS = get_credentials()
GC = gspread_asyncio.AsyncioGspreadClientManager(lambda: CREDS)

# Kerakli ustun indekslari
REQUIRED_COLUMNS = [0, 2, 3, 5, 4, 22, 29, 30, 34]  # HEMIS_UID, IDX_HEMIS, IDX_FIO, IDX_JSH, IDX_STAT, IDX_W, IDX_LAVOZIM, IDX_TASHKILOT, IDX_SANASI

async def load_rows():
    """
    Varaqdagi faqat kerakli ustunlarni asinxron o'qiydi va keshlaydi.
    0-qatorda header bo'ladi.
    """
    cache_key = f"sheet_{SHEET_ID}_{WORKSHEET_TITLE}"
    if cache_key in cache:
        return cache[cache_key]

    try:
        # Asinxron klient yaratish
        client = await GC.authorize()
        spreadsheet = await client.open_by_key(SHEET_ID)
        worksheet = await spreadsheet.worksheet(WORKSHEET_TITLE)

        # Faqat kerakli ustunlarni o'qish
        rows = await worksheet.get(f"A1:AI{worksheet.row_count}")

        # Keshga saqlash
        cache[cache_key] = rows
        return rows
    except Exception as e:
        # Xatolarni ushlash va foydalanuvchiga xabar qaytarish uchun
        raise Exception(f"Google Sheets'dan ma'lumot olishda xato: {str(e)}")