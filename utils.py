from typing import List
from telegram.ext import ContextTypes
from telegram import Update
import pandas as pd
import io
import logging
import json
from datetime import datetime
from sheets import GC, SHEET_ID, WORKSHEET_TITLE
from time import localtime

logger = logging.getLogger(__name__)

def safe_cell(row: List[str], idx: int) -> str:
    """Index dan tashqarida bo'lsa yoki bo'sh bo'lsa '' qaytaradi."""
    try:
        v = row[idx]
    except Exception:
        return ""
    if v is None:
        return ""
    return str(v).strip()

def escape_md(text: str) -> str:
    """Markdown uchun minimal escape (asterisk, underscore, backtick)."""
    if text is None:
        return ""
    return str(text).replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")

async def split_and_send_text(chat_id, text, context, limit: int = 3900):
    """Uzoq matnni Telegram limitiga mos bo'lib bo'lib yuboradi."""
    parts = []
    if len(text) <= limit:
        parts = [text]
    else:
        cur = []
        cur_len = 0
        for line in text.splitlines(keepends=True):
            if cur_len + len(line) > limit:
                parts.append("".join(cur))
                cur = [line]
                cur_len = len(line)
            else:
                cur.append(line)
                cur_len += len(line)
        if cur:
            parts.append("".join(cur))

    for p in parts:
        try:
            await context.bot.send_message(chat_id=chat_id, text=p, parse_mode="Markdown",protect_content=True)
        except Exception as e:
            logger.error(f"Matn yuborishda xato: {e}")

async def send_error_message(chat_id, context, message: str = "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring."):
    """Umumiy xato xabarini yuborish."""
    try:
        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown",protect_content=True)
    except Exception as e:
        logger.error(f"Xato xabarini yuborishda muammo: {e}")

async def delete_previous_page(chat_id, context: ContextTypes.DEFAULT_TYPE):
    """Avvalgi sahifa xabarini o‘chirish."""
    if context.user_data.get("page_msg_id"):
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data["page_msg_id"])
        except Exception as e:
            logger.error(f"Sahifani o‘chirishda xato: {e}")
        context.user_data["page_msg_id"] = None

async def export_to_excel(results, chat_id, context):
    """Qidiruv natijalarini Excel faylga aylantirib, Telegram orqali yuborish."""
    try:
        logger.info(f"Excel fayl yaratilmoqda, natijalar soni: {len(results)}")
        
        # Ma'lumotlarni DataFrame'ga aylantirish
        df = pd.DataFrame(results)
        columns = ["hemisuid", "hemis", "fio", "fakultet", "mutaxassislik", "guruh", "jshshir", "status", "lavozim", "tashkilot", "sanasi"]
        df = df[[col for col in columns if col in df.columns]]

        # Excel faylni xotirada yaratish
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False, engine='openpyxl')
        buffer.seek(0)

        # Fayl hajmini tekshirish (Telegram chegarasi: 50 MB)
        file_size = buffer.getbuffer().nbytes
        logger.info(f"Excel fayl hajmi: {file_size / 1024 / 1024:.2f} MB")
        if file_size > 50 * 1024 * 1024:  # 50 MB dan katta bo‘lsa
            await send_error_message(chat_id, context, "❌ Fayl hajmi juda katta (50 MB dan ortiq). Iltimos, qidiruvni qisqartiring.")
            return

        # Telegram orqali yuborish
        await context.bot.send_document(
            chat_id=chat_id,
            document=buffer,
            filename=f"Result-{localtime()[0]}_{localtime()[1]}_{localtime()[2]}_{localtime()[3]}_{localtime()[4]}_{localtime()[5]}_{localtime()[6]}_{localtime()[7]}_{localtime()[8]}.xlsx",
            caption="📤 Qidiruv natijalarini Excel fayl sifatida yuklab oling."
        )
        logger.info("Excel fayl muvaffaqiyatli yuborildi.")
    except Exception as e:
        logger.error(f"Excel eksportida xato: {e}")
        await send_error_message(chat_id, context, f"❌ Excel eksportida xato: {str(e)}")

async def log_user_action(chat_id, action: str):
    """Foydalanuvchi harakatlarini log fayliga saqlash."""
    try:
        log_entry = {
            "chat_id": chat_id,
            "action": action,
            "timestamp": datetime.utcnow().isoformat()
        }
        with open("user_actions.json", "a") as f:
            json.dump(log_entry, f)
            f.write("\n")
        logger.info(f"Harakat loglandi: {action}, chat_id={chat_id}")
    except Exception as e:
        logger.error(f"Log saqlashda xato: {e}")

async def get_user_stats():
    """Foydalanuvchi statistikasini o‘qish."""
    try:
        stats = {}
        with open("user_actions.json", "r") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line.strip())
                    action = entry["action"]
                    stats[action] = stats.get(action, 0) + 1
        logger.info(f"Statistika o‘qildi: {stats}")
        return stats
    except FileNotFoundError:
        logger.warning("user_actions.json fayli topilmadi.")
        return {}
    except Exception as e:
        logger.error(f"Statistikani o‘qishda xato: {e}")
        return {}

async def update_sheet_row(row_index: int, values: List[str]):
    """Google Sheets’da qatorni yangilash."""
    try:
        client = await GC.authorize()
        spreadsheet = await client.open_by_key(SHEET_ID)
        worksheet = await spreadsheet.worksheet(WORKSHEET_TITLE)
        await worksheet.update(f"A{row_index}", [values])
        logger.info(f"Qator {row_index} muvaffaqiyatli yangilandi.")
    except Exception as e:
        logger.error(f"Qator yangilashda xato: {e}")
        raise Exception(f"Qator yangilashda xato: {str(e)}")