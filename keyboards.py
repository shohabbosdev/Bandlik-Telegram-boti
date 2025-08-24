from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

def reply_main_menu():
    """Asosiy menyuni qaytaradi."""
    keyboard = [
        [KeyboardButton("🔎 Qidiruv"), KeyboardButton("📊 Statistika")],
        [KeyboardButton("📉 Grafik")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=False)

def pagination_keyboard(page: int, total_pages: int):
    """Sahifalash tugmalari."""
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"pg|{page-1}"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"pg|{page+1}"))
    buttons.append(InlineKeyboardButton("📤 Excel'ga eksport", callback_data="export_excel"))
    return InlineKeyboardMarkup([buttons])

def direction_keyboard(directions, page: int, per_page: int = 10):
    """W qiymatlari uchun inline tugmalar sahifalab."""
    total_pages = max(1, (len(directions) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    page_directions = directions[start:end]

    buttons = []
    for dir in page_directions:
        buttons.append([InlineKeyboardButton(dir, callback_data=f"dir_{dir}")])

    pagination = []
    if page > 1:
        pagination.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"dir_pg|{page-1}"))
    if page < total_pages:
        pagination.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"dir_pg|{page+1}"))
    if pagination:
        buttons.append(pagination)

    return InlineKeyboardMarkup(buttons)