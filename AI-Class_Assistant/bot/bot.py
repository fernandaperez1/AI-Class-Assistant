import os
import asyncio
import socketio
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    ConversationHandler,
    filters, 
    ContextTypes
)

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BACKEND_WS_URL = os.getenv("BACKEND_WS_URL", "http://backend:5000")
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://backend:5000")

print("TELEGRAM_TOKEN =", TELEGRAM_TOKEN)
print("BACKEND_WS_URL =", BACKEND_WS_URL)
print("BACKEND_API_URL =", BACKEND_API_URL)

# Conversation states
WAITING_FOR_CODE = 1

sio = socketio.AsyncClient()

async def send_question_to_backend(telegram_chat_id: int, question: str, presentation_id: int = None):
    """
    Send a question to the backend and get AI response
    For now, just returns a placeholder message
    TODO: Integrate with OpenAI/Gemini for real AI responses
    """
    try:
        # For now, we'll just acknowledge the question
        # fuenzalida must work here, adding the options and all to go to the next slide
        return (
            "I received your question!\n\n"
            "Note: AI-powered answers will be available once you're in an active presentation.\n\n"
            f"Your question: _{question}_"
        )
    except Exception as e:
        print(f"Error sending question to backend: {e}")
        return "Sorry, I couldn't process your question right now. Please try again later."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    chat_id = update.effective_chat.id
    
    # Check if user is already linked
    try:
        response = requests.get(
            f"{BACKEND_API_URL}/api/telegram/check/{chat_id}",
            timeout=5
        )
        
        if response.status_code == 200:
            user_data = response.json()
            # User is already linked
            welcome_message = (
                f"*Welcome back to Class Assistant Bot!* 🎓\n\n"
                f"✅ Your account is linked to: `{user_data.get('email', 'your account')}`\n\n"
                "*Available Commands:*\n"
                "• `/help` - Show help message\n"
                "• Send any message to ask questions during presentations\n\n"
                "Ready to assist you during your classes! 🚀"
            )
            await update.message.reply_text(welcome_message, parse_mode='Markdown')
        else:
            # User is not linked yet - show button
            welcome_message = (
                "*Welcome to Class Assistant Bot!* 🎓\n\n"
                "I'm your AI-powered educational assistant.\n\n"
                "To get started, you need to link your Telegram account with the web app.\n\n"
                "*How to link:*\n"
                "1. Click the button below\n"
                "2. Get your code from the web app\n"
                "3. Send it here\n\n"
                "Let's connect your account!"
            )
            
            keyboard = [
                [InlineKeyboardButton("Link My Account", callback_data="start_link")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                welcome_message, 
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    except Exception as e:
        print(f"Error checking link status: {e}")
        # If we can't connect to backend, show error
        await update.message.reply_text(
            "⚠️ *Cannot connect to server*\n\n"
            "The backend is currently unavailable. Please try again in a moment.",
            parse_mode='Markdown'
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    chat_id = update.effective_chat.id
    
    # Check if user is linked
    try:
        response = requests.get(
            f"{BACKEND_API_URL}/api/telegram/check/{chat_id}",
            timeout=5
        )
        is_linked = response.status_code == 200
    except:
        is_linked = False
    
    if is_linked:
        help_message = (
            "*Class Assistant Bot Help*\n\n"
            "*During Presentations:*\n"
            "• Ask questions naturally\n"
            "• Get AI-generated answers\n"
            "• Access presentation materials\n\n"
            "*Commands:*\n"
            "• `/start` - Show welcome message\n"
            "• `/help` - Show this help\n\n"
            "Need help? Contact your instructor!"
        )
    else:
        help_message = (
            "*Class Assistant Bot Help*\n\n"
            "*Linking Your Account:*\n"
            "1. Log in to the web app\n"
            "2. Generate a link code\n"
            "3. Click 'Link My Account' button or use `/link`\n\n"
            "*Commands:*\n"
            "• `/start` - Show welcome message\n"
            "• `/link` - Start linking process\n"
            "• `/help` - Show this help\n\n"
            "Need help? Contact your instructor!"
        )
        
        keyboard = [
            [InlineKeyboardButton("Link My Account", callback_data="start_link")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(help_message, parse_mode='Markdown', reply_markup=reply_markup)
        return
    
    await update.message.reply_text(help_message, parse_mode='Markdown')


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "start_link":
        await query.edit_message_text(
            "*Let's link your account!*\n\n"
            "*Step 1:* Go to the web app and log in\n"
            "*Step 2:* Click 'Generate Link Code'\n"
            "*Step 3:* Copy the 6-character code\n"
            "*Step 4:* Send me the code here\n\n"
            "*Just type your code and send it* (e.g., ABC123)\n\n"
            "The code expires in 15 minutes.",
            parse_mode='Markdown'
        )
        # Set conversation state to wait for code
        context.user_data['waiting_for_code'] = True


async def link_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /link command - start the linking process"""
    chat_id = update.effective_chat.id
    
    # Check if already linked
    try:
        response = requests.get(
            f"{BACKEND_API_URL}/api/telegram/check/{chat_id}",
            timeout=5
        )
        
        if response.status_code == 200:
            user_data = response.json()
            await update.message.reply_text(
                f"*Already Linked!*\n\n"
                f"Your account is already linked to: `{user_data.get('email', 'your account')}`\n\n"
                f"You're all set!",
                parse_mode='Markdown'
            )
            return
    except:
        pass
    
    # Not linked, start the process
    message = (
        "*Let's link your account!*\n\n"
        "*Step 1:* Go to the web app and log in\n"
        "*Step 2:* Click 'Generate Link Code'\n"
        "*Step 3:* Copy the 6-character code\n"
        "*Step 4:* Send me the code here\n\n"
        "*Just type your code and send it* (e.g., ABC123)\n\n"
        "The code expires in 15 minutes."
    )
    
    await update.message.reply_text(message, parse_mode='Markdown')
    context.user_data['waiting_for_code'] = True

def process_link_code(chat_id: int, link_code: str):
    """Process the link code and return result"""
    try:
        response = requests.post(
            f"{BACKEND_API_URL}/api/telegram/link",
            json={
                "code": link_code,
                "telegram_chat_id": chat_id
            },
            timeout=10
        )
        
        if response.status_code == 200:
            user_data = response.json()
            return {
                "success": True,
                "message": (
                    f"✅ *Account Linked Successfully!*\n\n"
                    f"Your Telegram is now linked to:\n`{user_data.get('email', 'your account')}`\n\n"
                    f"*You can now:*\n"
                    f"• Ask questions during presentations\n"
                    f"• Receive AI-generated answers\n"
                    f"• Access your class materials\n\n"
                    f"Start a presentation on the web app to get started!"
                )
            }
        elif response.status_code == 400:
            return {
                "success": False,
                "message": (
                    "❌ *Invalid or Expired Code*\n\n"
                    "The link code is either:\n"
                    "• Incorrect\n"
                    "• Expired (codes expire after 15 minutes)\n"
                    "• Already used\n\n"
                    "Please generate a new code from the web app and try again."
                )
            }
        else:
            return {
                "success": False,
                "message": "Failed to link account. Please try again later."
            }
            
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "message": (
                "⚠️ *Cannot connect to backend*\n\n"
                "The server is currently unavailable. Please try again later."
            )
        }
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "message": (
                "⚠️ *Request timed out*\n\n"
                "The server is taking too long to respond. Please try again."
            )
        }
    except Exception as e:
        print(f"Error linking account: {e}")
        return {
            "success": False,
            "message": "An error occurred. Please try again later."
        }

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular messages"""
    chat_id = update.effective_chat.id
    msg = update.message.text
    
    # Check if waiting for link code
    if context.user_data.get('waiting_for_code', False):
        # User is sending a link code
        link_code = msg.strip().upper()
        
        # Validate format (6 characters, alphanumeric)
        if len(link_code) != 6 or not link_code.isalnum():
            await update.message.reply_text(
                "*Invalid code format*\n\n"
                "The code should be 6 characters (letters and numbers).\n"
                "Example: `ABC123`\n\n"
                "Please try again or generate a new code from the web app.",
                parse_mode='Markdown'
            )
            return
        
        await update.message.reply_text("🔄 Linking your account...")
        
        result = process_link_code(chat_id, link_code)
        await update.message.reply_text(result["message"], parse_mode='Markdown')
        
        # Clear the waiting state
        if result["success"]:
            context.user_data['waiting_for_code'] = False
        
        return
    
    # Check if user is linked before processing questions
    try:
        response = requests.get(
            f"{BACKEND_API_URL}/api/telegram/check/{chat_id}",
            timeout=5
        )
        
        if response.status_code != 200:
            # User is not linked
            keyboard = [
                [InlineKeyboardButton("🔗 Link My Account", callback_data="start_link")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "⚠️ *Account Not Linked*\n\n"
                "Please link your account first to ask questions.\n\n"
                "Click the button below to get started!",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return
    except:
        await update.message.reply_text(
            "⚠️ Cannot connect to server. Please try again later."
        )
        return
    
    # User is linked, process the question
    await update.message.reply_text("Processing your question...")
    
    # Send question to backend and get response
    response = await send_question_to_backend(chat_id, msg)
    await update.message.reply_text(response, parse_mode='Markdown')


def main():
    """Start the bot"""
    if not TELEGRAM_TOKEN:
        print("ERROR: TELEGRAM_TOKEN not set in env")
        return
    
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("link", link_start))
    
    # Add callback query handler for buttons
    app.add_handler(CallbackQueryHandler(button_callback))

    # Add message handler (must be last)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Class Assistant Bot is starting...")
    print("✅ Bot is ready and listening for messages!")
    
    app.run_polling()

if __name__ == "__main__":
    main()
