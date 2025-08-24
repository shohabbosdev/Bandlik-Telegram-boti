import asyncio
import io
from collections import Counter
import matplotlib.pyplot as plt
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import ContextTypes, CallbackQueryHandler
from config import REQUIRED_STATUS, ADMIN_IDS
from sheets import load_rows
from utils import safe_cell, escape_md, split_and_send_text, send_error_message, delete_previous_page, export_to_excel, log_user_action, get_user_stats, update_sheet_row
from formatters import format_card, format_results_block
from keyboards import reply_main_menu, pagination_keyboard

logger = logging.getLogger(__name__)

# Ustun indekslari (0-based)
HEMIS_UID    = 0   # A
IDX_HEMIS    = 2   # C
IDX_FIO      = 3   # D
IDX_STAT     = 4   # E
IDX_JSH      = 5   # F
IDX_W        = 22  # W
IDX_LAVOZIM  = 29  # AD
IDX_TASHKILOT= 30  # AE
IDX_SANASI   = 34  # AI
IDX_GURUH    = 14  # O
IDX_FAKULTET = 23  # X
IDX_MUTAXASSISLIK = 22  # W

PER_PAGE = 7

# ---------------- Helper: natijalarni qurish ----------------
def build_results_from_rows(rows, query: str):
    """rows = get_all_values() — list of lists. Returns list of dicts."""
    res = []
    q = (query or "").strip().lower()
    if not q:
        return res
    for r in rows[1:]:
        hemisuid = safe_cell(r, HEMIS_UID)
        fio = safe_cell(r, IDX_FIO)
        guruh = safe_cell(r, IDX_GURUH)
        fakultet = safe_cell(r, IDX_FAKULTET)
        mutaxassislik = safe_cell(r, IDX_MUTAXASSISLIK)
        hemis = safe_cell(r, IDX_HEMIS)
        jsh = safe_cell(r, IDX_JSH)
        status = safe_cell(r, IDX_STAT)
        if not (fio or hemis or jsh or hemisuid):
            continue
        if q in fio.lower() or q in hemis.lower() or q in jsh.lower() or q in hemisuid.lower():
            item = {
                "hemisuid": hemisuid,
                "fakultet": fakultet,
                "mutaxassislik": mutaxassislik,
                "guruh": guruh,
                "fio": fio,
                "hemis": hemis,
                "status": status,
                "jshshir": jsh,
            }
            if REQUIRED_STATUS.lower() in (status or "").lower():
                item["lavozim"]   = safe_cell(r, IDX_LAVOZIM)
                item["tashkilot"] = safe_cell(r, IDX_TASHKILOT)
                item["sanasi"]    = safe_cell(r, IDX_SANASI)
            res.append(item)
    return res

def _results_summary(results):
    total = len(results)
    active = sum(1 for it in results if REQUIRED_STATUS.lower() in (it.get("status","") or "").lower())
    pct = round((active/total*100),2) if total else 0.0
    return total, active, pct

# ---------------- /start ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Clear any previous cache for this chat
    context.user_data.clear()
    await update.message.reply_text(
        "👋 *Assalomu alaykum!*\n\n"
        "Ism/familiya (qismi bo‘lsa ham), HEMIS ID yoki JSHSHIR yuboring — men jadvaldan topib beraman.\n\n"
        "📌 Pastdagi tugmalardan foydalanishingiz mumkin:",
        parse_mode="Markdown",
        reply_markup=reply_main_menu()
    )
    await log_user_action(update.effective_chat.id, "start")

# ---------------- Statistika (/stat yoki tugma) ----------------
async def stat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    try:
        rows = await load_rows()  # Asinxron chaqiruv
        if len(rows) <= 1:
            await send_error_message(chat_id, context, "❌ *Jadval bo‘sh.*")
            return

        total_students = len(rows) - 1
        total_active = 0
        total_per_w = Counter()
        active_per_w = Counter()

        for r in rows[1:]:
            w_val = safe_cell(r, IDX_W) or "Noma'lum"
            status = safe_cell(r, IDX_STAT)
            total_per_w[w_val] += 1
            if REQUIRED_STATUS.lower() in (status or "").lower():
                active_per_w[w_val] += 1
                total_active += 1

        overall_pct = round((total_active / total_students * 100), 2) if total_students else 0.0

        lines = [
            "📊 *Statistika (W ustuni bo‘yicha):*\n",
            f"👥 *Jami talabalar soni:* {total_students} ta",
            f"🟢 *Faol shartnoma ega talabalarning (umumiy) soni:* {total_active} ta ({overall_pct}%)\n",
        ]

        for w_key in sorted(total_per_w.keys(), key=lambda x: (x.lower() if isinstance(x, str) else str(x))):
            tot = total_per_w[w_key]
            act = active_per_w.get(w_key, 0)
            pct_group = round((act / tot * 100), 2) if tot else 0.0
            lines.append(f"✅ *{escape_md(w_key)}:* jami {tot} | faol: {act} ({pct_group}%)")

        text = "\n".join(lines)

        await delete_previous_page(chat_id, context)
        await split_and_send_text(chat_id, text, context)
        await log_user_action(chat_id, "stat")
    except Exception as e:
        logger.error(f"Statistikada xato: {e}")
        await send_error_message(chat_id, context, f"❌ Statistika olishda xato: {str(e)}")

# ---------------- Qidiruv (foydalanuvchi yuborgan matn) ----------------
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()

    # Reply tugma bosilganda ularni qidiruv deb o'tkazmaymiz
    if text in ("🔎 Qidiruv", "Qidiruv"):
        await update.message.reply_text("🔎 Qidiruvni boshlash uchun: *ism/familiya (qismi)* yoki *HEMIS ID / JSHSHIR* yuboring.", parse_mode="Markdown")
        return
    if text in ("📊 Statistika", "Statistika"):
        await stat(update, context)
        return
    if text in ("📉 Grafik", "grafik", "Grafik"):
        await grafik(update, context)
        return

    if not text:
        await update.message.reply_text("📝 Iltimos, qidirish uchun matn yuboring.")
        return

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    try:
        rows = await load_rows()  # Asinxron chaqiruv
        results = build_results_from_rows(rows, text)

        if not results:
            await delete_previous_page(chat_id, context)
            await send_error_message(chat_id, context, "❌ *Hech qanday ma'lumot topilmadi.*")
            return

        # user_data ga saqlaymiz
        context.user_data.update({"query": text, "results": results, "page_msg_id": None, "page": 1})
        await send_page(chat_id, context, page=1)
        await log_user_action(chat_id, f"search_{text}")
    except Exception as e:
        logger.error(f"Qidiruvda xato: {e}")
        await send_error_message(chat_id, context, f"❌ Qidiruvda xato: {str(e)}")

# ---------------- Sahifa yuborish (yangi xabar qilib) ----------------
async def send_page(chat_id: int, context: ContextTypes.DEFAULT_TYPE, page: int):
    results = context.user_data.get("results")
    if not results:
        return
    total, active, pct = _results_summary(results)
    total_pages = max(1, (len(results) + PER_PAGE - 1)//PER_PAGE)
    page = max(1, min(page, total_pages))
    start = (page-1)*PER_PAGE
    end = start + PER_PAGE
    page_items = results[start:end]

    header = (
        f"📋 *Jami topilgan talabalar soni:* {total} ta\n"
        f"🟢 *my.mehnat.uz da mehnat shartnomasiga ega talabalar soni:* {active} ta ({pct}%)\n"
        f"📄 *Sahifalar:* {page}/{total_pages}\n\n"
    )
    text = header + format_results_block(page_items)

    await delete_previous_page(chat_id, context)
    sent = await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=pagination_keyboard(page, total_pages))
    context.user_data["page_msg_id"] = sent.message_id
    context.user_data["page"] = page

# ---------------- Inline pagination (callback) ----------------
async def inline_pagination_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query
    if not cq:
        logger.warning("Callback query topilmadi.")
        return
    await cq.answer()
    data = cq.data  # format: "pg|<page>" yoki "export_excel"
    
    chat_id = cq.message.chat.id
    logger.info(f"Inline tugma bosildi: callback_data={data}, chat_id={chat_id}")

    if data == "export_excel":
        try:
            results = context.user_data.get("results")
            if not results:
                logger.warning("Eksport uchun natijalar topilmadi.")
                await send_error_message(chat_id, context, "❌ Eksport qilish uchun natijalar topilmadi.")
                return
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
            await export_to_excel(results, chat_id, context)
            await log_user_action(chat_id, "export_excel")
        except Exception as e:
            logger.error(f"Excel eksport handlerida xato: {e}")
            await send_error_message(chat_id, context, f"❌ Excel eksportida xato: {str(e)}")
        return

    try:
        _, raw_page = data.split("|", 1)
        page = int(raw_page)
    except Exception:
        logger.warning(f"Noto‘g‘ri callback data: {data}")
        return

    try:
        results = context.user_data.get("results")
        if not results:
            logger.warning("Sahifalash uchun natijalar topilmadi.")
            return

        total, active, pct = _results_summary(results)
        total_pages = max(1, (len(results) + PER_PAGE - 1)//PER_PAGE)
        page = max(1, min(page, total_pages))
        start = (page-1)*PER_PAGE
        end = start + PER_PAGE
        page_items = results[start:end]

        header = (
            f"📋 *Jami topilgan talabalar soni:* {total} ta\n"
            f"🟢 *my.mehnat.uz da mehnat shartnomasiga ega talabalar soni:* {active} ta ({pct}%)\n"
            f"📄 *Sahifa:* {page}/{total_pages}\n\n"
        )
        new_text = header + format_results_block(page_items)

        await cq.edit_message_text(text=new_text, parse_mode="Markdown", reply_markup=pagination_keyboard(page, total_pages))
        context.user_data["page"] = page
        await log_user_action(chat_id, f"page_{page}")
    except Exception as e:
        logger.error(f"Sahifa o‘zgartirishda xato: {e}")
        await send_error_message(chat_id, context, f"❌ Sahifa o‘zgartirishda xato: {str(e)}")

# ---------------- Grafik (Grafik tugmasi yoki /grafik) ----------------
async def grafik(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import matplotlib
    matplotlib.use('Agg')  # Headless mode
    import matplotlib.pyplot as plt
    from io import BytesIO
    from collections import Counter
    from sheets import load_rows
    from utils import safe_cell

    chat_id = update.effective_chat.id
    
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)

        rows = await load_rows()  # Asinxron chaqiruv
        vals = [safe_cell(r, IDX_W) for r in rows[1:] if safe_cell(r, IDX_W)]
        
        if not vals:
            await send_error_message(chat_id, context, "❌ Grafik uchun ma'lumot topilmadi.")
            return

        counts = Counter(vals).most_common()
        labels = [str(t[0]) for t in counts]
        data = [t[1] for t in counts]

        # Fontni Liberation Sans ga o‘zgartirish
        plt.rcParams['axes.unicode_minus'] = False
        
        # Grafik o'lchamlari
        fig_width = max(10, min(16, len(labels) * 0.8))
        fig_height = max(6, len(labels) * 0.4)
        
        plt.figure(figsize=(fig_width, fig_height), dpi=100)
        
        # Horizontal bar chart
        colors = plt.cm.Set3(range(len(labels)))
        bars = plt.barh(range(len(labels)), data, color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)

        # Labels va formatting
        plt.yticks(range(len(labels)), labels, fontsize=10)
        plt.xlabel("Talabalar soni", fontsize=11, fontweight='bold')
        plt.title("Yo'nalishlar bo'yicha taqsimot", fontsize=13, fontweight='bold', pad=15)  # Emoji olib tashlandi
        plt.grid(axis="x", linestyle="--", alpha=0.5)

        # Values on bars
        max_val = max(data) if data else 1
        for bar, val in zip(bars, data):
            plt.text(bar.get_width() + max_val * 0.01, 
                    bar.get_y() + bar.get_height()/2,
                    str(val), ha="left", va="center", fontsize=9, fontweight="bold")

        plt.tight_layout()
        
        # BytesIO orqali grafikni yuborish
        buffer = BytesIO()
        plt.savefig(buffer, format="png", bbox_inches="tight", facecolor='white', dpi=100)
        plt.close()
        buffer.seek(0)
        
        await context.bot.send_photo(
            chat_id=chat_id, 
            photo=buffer, 
            caption="📊 Yo'nalishlar kesimi bo'yicha taqsimot grafigi",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔀 To'liq ma'lumot", url='https://t.me/shohabbosdev')]])
        )
        await log_user_action(chat_id, "grafik")
    except Exception as e:
        logger.error(f"Grafik yaratishda xato: {e}")
        await send_error_message(chat_id, context, f"❌ Grafik yaratishda xato: {str(e)}")

# ---------------- Admin paneli ----------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in ADMIN_IDS:
        await send_error_message(chat_id, context, "❌ Sizda admin paneliga kirish huquqi yo‘q.")
        return

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    keyboard = [
        [InlineKeyboardButton("📊 Statistika ma'lumotlari", callback_data="admin_stats")],
        [InlineKeyboardButton("📝 Qatorlarni tahrirlash", callback_data="admin_edit_row")],
        [InlineKeyboardButton("🔙 Chiqish", callback_data="admin_exit")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await update.message.reply_text(
            "🛠 *Admin paneli*\n\n"
            "Quyidagi amallarni tanlang:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        await log_user_action(chat_id, "admin_panel")
    except Exception as e:
        logger.error(f"Admin panelini ochishda xato: {e}")
        await send_error_message(chat_id, context, f"❌ Admin panelini ochishda xato: {str(e)}")

# ---------------- Admin inline handler ----------------
async def admin_inline_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query
    if not cq:
        logger.warning("Callback query topilmadi.")
        return
    await cq.answer()
    chat_id = cq.message.chat.id
    data = cq.data
    logger.info(f"Admin inline tugma bosildi: callback_data={data}, chat_id={chat_id}")

    if chat_id not in ADMIN_IDS:
        logger.warning(f"Chat ID {chat_id} admin huquqiga ega emas.")
        await send_error_message(chat_id, context, "❌ Sizda admin paneliga kirish huquqi yo‘q.")
        return

    if data == "admin_stats":
        try:
            stats = await get_user_stats()
            if not stats:
                logger.info("Statistika mavjud emas.")
                await cq.edit_message_text(
                    text="❌ Hozircha statistika mavjud emas.",
                    parse_mode="Markdown"
                )
                return

            lines = ["📊 *Bot statistikasi*\n"]
            for action, count in stats.items():
                lines.append(f"✅ *{escape_md(action)}*: {count} marta")
            text = "\n".join(lines)

            await cq.edit_message_text(text=text, parse_mode="Markdown")
            await log_user_action(chat_id, "admin_stats")
        except Exception as e:
            logger.error(f"Admin statistikada xato: {e}")
            await send_error_message(chat_id, context, f"❌ Statistika olishda xato: {str(e)}")

    elif data == "admin_edit_row":
        try:
            await cq.edit_message_text(
                "📝 Tahrir qilmoqchi bo‘lgan qator indeksini va yangi ma'lumotlarni kiriting.\n"
                "Format: `row_index|hemisuid|fio|hemis|jshshir|status|lavozim|tashkilot|sanasi`\n"
                "Masalan: `2|12345|Aliyev Ali|67890|12345678901234|Faol|Muhandis|ABC kompaniyasi|2023-10-01`",
                parse_mode="Markdown"
            )
            context.user_data["admin_action"] = "edit_row"
            await log_user_action(chat_id, "admin_edit_row")
        except Exception as e:
            logger.error(f"Qator tahrirlash so‘rovida xato: {e}")
            await send_error_message(chat_id, context, f"❌ Qator tahrirlash so‘rovida xato: {str(e)}")

    elif data == "admin_exit":
        try:
            await cq.edit_message_text("🛠 Admin panelidan chiqildi.")
            await log_user_action(chat_id, "admin_exit")
        except Exception as e:
            logger.error(f"Admin panelidan chiqishda xato: {e}")
            await send_error_message(chat_id, context, f"❌ Chiqishda xato: {str(e)}")
    else:
        logger.warning(f"Noma'lum callback data: {data}")
        await send_error_message(chat_id, context, f"❌ Noma'lum buyruq: {data}")

# ---------------- Admin qator tahrirlash (matn orqali) ----------------
async def admin_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in ADMIN_IDS:
        logger.warning(f"Chat ID {chat_id} admin huquqiga ega emas.")
        await send_error_message(chat_id, context, "❌ Sizda admin paneliga kirish huquqi yo‘q.")
        return

    if context.user_data.get("admin_action") != "edit_row":
        return

    text = (update.message.text or "").strip()
    try:
        parts = text.split("|")
        if len(parts) != 9:
            logger.warning(f"Noto‘g‘ri formatda ma'lumot kiritildi: {text}")
            await send_error_message(chat_id, context, "❌ Noto‘g‘ri format. Iltimos, to‘g‘ri formatda kiriting: `row_index|hemisuid|fio|hemis|jshshir|status|lavozim|tashkilot|sanasi`")
            return

        row_index = int(parts[0])
        values = parts[1:]

        await update_sheet_row(row_index, values)
        await update.message.reply_text(f"✅ Qator {row_index} muvaffaqiyatli yangilandi.")
        context.user_data["admin_action"] = None
        await log_user_action(chat_id, f"edit_row_{row_index}")
    except ValueError:
        logger.warning(f"Qator indeksi noto‘g‘ri: {text}")
        await send_error_message(chat_id, context, "❌ Qator indeksi raqam bo‘lishi kerak.")
    except Exception as e:
        logger.error(f"Qator tahrirlashda xato: {e}")
        await send_error_message(chat_id, context, f"❌ Qator tahrirlashda xato: {str(e)}")