import os
import asyncio
import socketio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BACKEND_WS_URL = os.getenv("BACKEND_WS_URL")
print("TELEGRAM_TOKEN =", TELEGRAM_TOKEN)
print("BACKEND_WS_URL =", BACKEND_WS_URL)

sio = socketio.AsyncClient()

async def send_to_backend(message: str):
    try:
        await sio.connect(BACKEND_WS_URL)
        await sio.emit("bot_message", {"msg": message})
        response_future = asyncio.Future()

        @sio.on("bot_response")
        def on_response(data):
            response_future.set_result(data["msg"])

        return await response_future
    except Exception as e:
        return f"❌ Backend unavailable: {e}"
    finally:
        await sio.disconnect()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot online ✅")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    await update.message.reply_text("⏳ Sending to backend...")
    response = await send_to_backend(msg)
    await update.message.reply_text(f"📘 Backend says:\n{response}")


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
