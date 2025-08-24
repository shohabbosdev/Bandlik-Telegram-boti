import logging
from environs import Env
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from handlers import start, stat, search, grafik, inline_pagination_handler, admin_panel, admin_inline_handler, admin_edit
from config import BOT_TOKEN

# Loglashni sozlash
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def error_handler(update, context):
    """Xatolarni loglash va foydalanuvchiga xabar yuborish."""
    logger.error(f"Xato yuz berdi: {context.error}")
    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Botda xato yuz berdi. Iltimos, qaytadan urinib ko‘ring."
        )
    except Exception:
        pass

def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stat", stat))
    app.add_handler(CommandHandler("grafik", grafik))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit))
    app.add_handler(CallbackQueryHandler(inline_pagination_handler, pattern="pg|.*|export_excel"))
    app.add_handler(CallbackQueryHandler(admin_inline_handler, pattern="admin_.*"))

    # Xato handleri qo‘shish
    app.add_error_handler(error_handler)

    app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()