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

# here I manage the question the user does, like asking to create a pres, all under the category of the AI in the control
user_states = {}  # format: {chat_id: {"action": "create_example", "presentation_id": 1, "slide": 2}}

# Here I add all of the messages and delete them when the user leaves the pptx (need to add the queries to the ai to the db tho)
active_presentation_messages = {}  # Format: {chat_id: message_id}

#global bot application reference (will be set in main(), but I needed to use it everywhere, ik its bad practice xd)
bot_app = None

sio = socketio.AsyncClient()

@sio.event
async def connect():
    print("Connected to backend socket.")

@sio.event
async def disconnect():
    print("Disconnected from backend socket.")

@sio.event
async def connect_error(data):
    print("Socket connection failed:", data)

#listen for all messages from the backend, its to debug
@sio.on("*")
async def catch_all(event, data=None):
    print(f"Received event: {event}")
    print("Payload:", data)

@sio.on("presentation:started")
async def handle_presentation_started(data):
    """Handle presentation started event from backend"""
    print("Presentation started event received:", data)
    
    telegram_chat_id = data.get("telegram_chat_id")
    presentation_id = data.get("presentation_id")
    slide_count = data.get("slide_count", 1)
    current_slide = data.get("current_slide", 1)
    
    if telegram_chat_id and presentation_id:
        # Schedule the notification in the event loop
        asyncio.create_task(send_presentation_active_notification(
            telegram_chat_id, 
            presentation_id, 
            slide_count,
            current_slide
        ))

@sio.on("presentation:ended")
async def handle_presentation_ended(data):
    """Handle presentation ended event from backend"""
    print("🛑 Presentation ended event received:", data)
    
    telegram_chat_id = data.get("telegram_chat_id")
    duration = data.get("duration_seconds", 0)
    
    if telegram_chat_id:
        # Schedule the notification in the event loop
        asyncio.create_task(send_presentation_ended_notification(telegram_chat_id, duration))

@sio.on("presentation:update")
async def handle_presentation_update(data):
    """Handle slide change updates"""
    print("Presentation updated:", data)
    # notify user of slide changes

# Helper to connect at startup with retry logic
async def connect_socket():
    max_retries = 10
    retry_delay = 2  # Start with 2 seconds
    
    for attempt in range(max_retries):
        try:
            print(f"🔗 Attempting to connect to backend WebSocket (attempt {attempt + 1}/{max_retries})...")
            await sio.connect(BACKEND_WS_URL, transports=["websocket"])
            print(f"✅ Connected to backend socket at {BACKEND_WS_URL}")
            # Keep the connection alive
            await sio.wait()
            break  # Exit if successful
        except Exception as e:
            print(f"❌ Socket connection failed (attempt {attempt + 1}/{max_retries}): {e}")
            
            if attempt < max_retries - 1:
                print(f"⏳ Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, 30)  # Exponential backoff, max 30s
            else:
                print("❌ Failed to connect to backend after all retries. Bot will work without WebSocket notifications.")
                # Bot will still work for commands, just won't receive WebSocket events


async def send_presentation_active_notification(telegram_chat_id, presentation_id: int, slide_count, current_slide):
    """Send notification with navigation buttons when presentation starts"""
    if not bot_app:
        print("Bot app not initialized yet")
        return
    
    #gotta add the presentation name later, and also fix the current slide
    message = (
        "*---------------------------------------------------*\n*---------------------------------------------------*\n\n"
        "*Presentation Started!*\n\n"
        f"Total slides: {slide_count}\n"
        f"📍 Current slide: {current_slide}\n\n"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("⬅️ Previous", callback_data=f"nav:prev:{presentation_id}"),
            InlineKeyboardButton("➡️ Next", callback_data=f"nav:next:{presentation_id}")
        ],
        [
            InlineKeyboardButton("Go to Slide", callback_data=f"nav:goto:{presentation_id}")
        ],
        [
            InlineKeyboardButton("AI Assistant", callback_data=f"ai:menu:{presentation_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        sent_message = await bot_app.bot.send_message(
            chat_id=telegram_chat_id,
            text=message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        # storing message ID to edit/delete it when presentation ends
        active_presentation_messages[telegram_chat_id] = sent_message.message_id
        print(f"Sent presentation active notification to chat {telegram_chat_id}, message_id: {sent_message.message_id}")
    except Exception as e:
        print(f"X Error sending notification: {e}")


async def send_presentation_ended_notification(telegram_chat_id: int, duration_seconds: int):
    """Send notification when presentation ends"""
    if not bot_app:
        print("Bot app not initialized yet")
        return
    
    minutes = duration_seconds // 60
    seconds = duration_seconds % 60
    
    #Added the emojies for now, idk how to make it look better, if someone wants to try go on
    message = (
        "🛑 *Presentation Ended*\n\n"
        f"⏱️ Duration: {minutes}m {seconds}s\n\n"
    )
    
    try:
        # remove the buttons and all
        message_id = active_presentation_messages.get(telegram_chat_id)
        if message_id:
            try:
                await bot_app.bot.edit_message_text(
                    chat_id=telegram_chat_id,
                    message_id=message_id,
                    text=message,
                    parse_mode='Markdown'
                )
                print(f"Edited presentation message to show ended status for chat {telegram_chat_id}")
            except Exception as edit_error:
                print(f"Could not edit message (maybe too old): {edit_error}")
                # fail debug log
                await bot_app.bot.send_message(
                    chat_id=telegram_chat_id,
                    text=message,
                    parse_mode='Markdown'
                )
            finally:
                # remove the presentation chat log
                active_presentation_messages.pop(telegram_chat_id, None)
        else:
            #just send new message
            await bot_app.bot.send_message(
                chat_id=telegram_chat_id,
                text=message,
                parse_mode='Markdown'
            )
        
        # clear the user info for the AI bot when ending a presentation just in case
        user_states.pop(telegram_chat_id, None)
        
        print(f"Sent presentation ended notification to chat {telegram_chat_id}")
    except Exception as e:
        print(f"X Error sending notification: {e}")


async def send_question_to_backend(telegram_chat_id: int, question: str, presentation_id: int = None):
    """
    Send a question to the backend and get AI response
    For now, just returns a placeholder message
    TODO: Integrate with OpenAI/Gemini for real AI responses
    """
    try:
        # For now, we'll just acknowledge the question
        # fuenzalida must work here, adding the options and all to go to the next slide
        #I ended up doing it in the functions at the end of this file xd, so nvmnd
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
            # print(f"user_data={user_data}")
            # User is already linked
            welcome_message = (
                f"*Welcome back to TutorFlow Bot!* 🎓\n\n"
                f"Your are logged in as: `{user_data.get('email', 'your account')}`\n\n"
                "*Start a presentation from the website to begin*\n"
                "Ready to assist you during your classes!"
            )
            await update.message.reply_text(welcome_message, parse_mode='Markdown')
        else:
            # User is not linked yet - show button
            welcome_message = (
                "*Welcome to TutorFlow Bot!* 🎓\n\n"
                "I'm your AI-powered educational assistant (and also a simple controller xd).\n\n"
                "To get started, you need to link your Telegram account with the web app.\n\n"
                "*How to link:*\n"
                "1. Click the button below\n"
                "2. Get your code from the web app\n"
                "3. Send it here\n\n"
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
        # If we can't connect to backend, show error (this isnt from sockets, but from request, should not fail)
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
            "*TutorFlow Bot Help*\n\n"
            "*During Presentations:*\n"
            "• Ask questions naturally\n"
            "• Get AI-generated answers\n"
            "• Access presentation materials\n\n"
            "*Commands:*\n"
            "• `/start` - Show welcome message\n"
            "• `/help` - Show this help\n\n"
            "Need help? not my problem lol"
        )
    else:
        help_message = (
            "*TutorFlow Bot Help*\n\n"
            "*Linking Your Account:*\n"
            "1. Log in to the web app\n"
            "2. Generate a link code\n"
            "3. Click 'Link My Account' button or use `/link`\n\n"
            "*Commands:*\n"
            "• `/start` - Show welcome message\n"
            "• `/link` - Start linking process\n"
            "• `/help` - Show this help\n\n"
            "Need help? not my problem lol"
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
    
    callback_data = query.data
    
    # Handle link account button
    if callback_data == "start_link":
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
        # waiting for the code from the user
        context.user_data['waiting_for_code'] = True
        return
    
    # back to navigation button
    if callback_data.startswith("back_to_nav:"):
        presentation_id = int(callback_data.split(":")[1])
        await show_navigation_menu(query, presentation_id)
        return
    
    # navigation buttons: format is "nav:action:presentation_id"
    if callback_data.startswith("nav:"):
        parts = callback_data.split(":")
        if len(parts) >= 3:
            action = parts[1]  # next, prev, goto
            presentation_id = int(parts[2])
            
            if action == "next":
                await handle_nav_next(query, presentation_id)
            elif action == "prev":
                await handle_nav_prev(query, presentation_id)
            elif action == "goto":
                await handle_nav_goto(query, context, presentation_id)
        return
    
    #AI Assistant button: format "ai:action:presentation_id"
    if callback_data.startswith("ai:"):
        parts = callback_data.split(":")
        if len(parts) >= 3:
            action = parts[1]
            presentation_id = int(parts[2])
            
            #clear any user state when entering AI menu (handles cancel buttn)
            chat_id = query.message.chat_id
            if chat_id in user_states and action == "menu":
                user_states.pop(chat_id, None)
            
            if action == "menu":
                await handle_ai_menu(query, presentation_id)
            elif action == "create_example":
                await handle_ai_create_example(query, presentation_id)
            elif action == "create_quiz":
                await handle_ai_create_quiz(query, presentation_id)
            elif action == "create_quiz_alt":
                await handle_ai_create_quiz_alternatives(query, presentation_id)
        return
    
    #selection button: format "select:option_index:presentation_id"
    if callback_data.startswith("select:"):
        parts = callback_data.split(":")
        if len(parts) >= 3:
            option_index = int(parts[1])  # 0, 1, or 2, need to add edge cases here
            presentation_id = int(parts[2])
            
            await handle_option_selection(query, context, presentation_id, option_index)
        return
    
    # skip button: format "skip:action_type:presentation_id"
    if callback_data.startswith("skip:"):
        parts = callback_data.split(":")
        if len(parts) >= 3:
            action_type = parts[1]  # "example", "quiz", "quiz_alt"
            presentation_id = int(parts[2])
            
            await handle_skip_input(query, context, presentation_id, action_type)
        return







#FIXING HEREEEEEEEE






async def show_navigation_menu(query, presentation_id: int):
    """Show the main navigation menu"""
    try:
        # Get current presentation info
        resp = requests.get(
            f"{BACKEND_API_URL}/api/presentations/{presentation_id}",
            timeout=5
        )
        
        if resp.ok:
            data = resp.json()
            current_slide = data.get("current_slide", 1)
            slide_count = data.get("slide_count", 0)
        else:
            current_slide = 1
            slide_count = 0
        
        message = (
            "*---------------------------------------------------*\n*---------------------------------------------------*\n\n"
            "*Presentation Active*\n\n"
            f"Total slides: {slide_count}\n"
            f"📍 Current slide: {current_slide}\n\n"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("⬅️ Previous", callback_data=f"nav:prev:{presentation_id}"),
                InlineKeyboardButton("➡️ Next", callback_data=f"nav:next:{presentation_id}")
            ],
            [
                InlineKeyboardButton("Go to Slide", callback_data=f"nav:goto:{presentation_id}")
            ],
            [
                InlineKeyboardButton("AI Assistant", callback_data=f"ai:menu:{presentation_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"Error showing navigation menu: {e}")
        await query.edit_message_text("Error loading navigation menu.")


async def handle_nav_next(query, presentation_id: int):
    """Handle next slide button"""
    try:
        resp = requests.post(
            f"{BACKEND_API_URL}/api/presentations/{presentation_id}/control",
            json={
                "action": "next",
                "telegram_chat_id": query.message.chat_id
            },
            timeout=5  # gotta test this with diferent latencies for every timeout
        )
        
        if resp.ok:
            data = resp.json()
            current_slide = data.get("current_slide", 1)
            
            # Get presentation info to show total slides
            pres_resp = requests.get(
                f"{BACKEND_API_URL}/api/presentations/{presentation_id}",
                timeout=5
            )
            slide_count = pres_resp.json().get("slide_count", 0) if pres_resp.ok else 0
            
            # Update message with navigation buttons
            message = (
                "*---------------------------------------------------*\n*---------------------------------------------------*\n\n"
                f"📍 *Slide {current_slide}*" + (f" / {slide_count}" if slide_count else "") + "\n\n"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("⬅️ Previous", callback_data=f"nav:prev:{presentation_id}"),
                    InlineKeyboardButton("➡️ Next", callback_data=f"nav:next:{presentation_id}")
                ],
                [
                    InlineKeyboardButton("Go to Slide", callback_data=f"nav:goto:{presentation_id}")
                ],
                [
                    InlineKeyboardButton("AI Assistant", callback_data=f"ai:menu:{presentation_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await query.answer("Could not navigate to next slide.", show_alert=True)
    except Exception as e:
        print(f"Error navigating next: {e}")
        await query.answer("Oooops, Error connecting to backend.", show_alert=True)


async def handle_nav_prev(query, presentation_id: int):
    """Handle previous slide button"""
    try:
        resp = requests.post(
            f"{BACKEND_API_URL}/api/presentations/{presentation_id}/control",
            json={
                "action": "prev",
                "telegram_chat_id": query.message.chat_id
            },
            timeout=5
        )
        
        if resp.ok:
            data = resp.json()
            current_slide = data.get("current_slide", 1)
            
            # Get presentation info to show total slides
            pres_resp = requests.get(
                f"{BACKEND_API_URL}/api/presentations/{presentation_id}",
                timeout=5
            )
            slide_count = pres_resp.json().get("slide_count", 0) if pres_resp.ok else 0
            
            # Update message with navigation buttons
            message = (
                "*---------------------------------------------------*\n*---------------------------------------------------*\n\n"
                f"📍 *Slide {current_slide}*" + (f" / {slide_count}" if slide_count else "") + "\n\n"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("⬅️ Previous", callback_data=f"nav:prev:{presentation_id}"),
                    InlineKeyboardButton("➡️ Next", callback_data=f"nav:next:{presentation_id}")
                ],
                [
                    InlineKeyboardButton("Go to Slide", callback_data=f"nav:goto:{presentation_id}")
                ],
                [
                    InlineKeyboardButton("AI Assistant", callback_data=f"ai:menu:{presentation_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await query.answer("Could not navigate to previous slide.", show_alert=True)
    except Exception as e:
        print(f"Error navigating prev: {e}")
        await query.answer("Ooops, Error connecting to backend.", show_alert=True)


async def handle_nav_goto(query, context, presentation_id: int):
    """Handle go to specific slide button"""
    pres_resp = requests.get(
        f"{BACKEND_API_URL}/api/presentations/{presentation_id}",
        timeout=5
    )
    slide_count = pres_resp.json().get("slide_count", 0) if pres_resp.ok else 0

    await query.edit_message_text(
        "*Go to Slide*\n\n"
        f"Reply with the slide number you want to jump to (from 1 to {slide_count}).\n"
        "Example: `5`",
        parse_mode='Markdown'
    )
    # store presentation_id for when user sends the slide number
    context.user_data['goto_presentation_id'] = presentation_id
    context.user_data['waiting_for_slide_number'] = True


async def handle_ai_menu(query, presentation_id: int):
    """Handle AI Assistant menu button"""
    message = (
        "*AI Assistant*\n\n"
        "Choose an option below:"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("Create Example", callback_data=f"ai:create_example:{presentation_id}")
        ],
        [
            InlineKeyboardButton("❓ Create Quiz", callback_data=f"ai:create_quiz:{presentation_id}")
        ],
        [
            InlineKeyboardButton("❓ Create Quiz (Alternatives)", callback_data=f"ai:create_quiz_alt:{presentation_id}")
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data=f"back_to_nav:{presentation_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def handle_ai_create_example(query, presentation_id: int):
    """Handle AI create example request - prompt user for input"""
    chat_id = query.message.chat_id
    # get current slide
    try:
        resp = requests.get(
            f"{BACKEND_API_URL}/api/presentations/{presentation_id}",
            timeout=5
        )
        current_slide = 1
        if resp.ok:
            current_slide = resp.json().get("current_slide", 1)
    except:
        current_slide = 1
    
    # Set user state to wait for input
    user_states[chat_id] = {
        "action": "create_example",
        "presentation_id": presentation_id,
        "slide": current_slide
    }
    
    message = (
        f"*Create Example (Slide {current_slide})*\n\n"
        "Please provide context for the example you want:\n\n"
        "• Send a text message describing what you want\n"
        "  Example: \"make an example about ECG calculation\"\n\n"
        "• OR send a voice message with your request\n\n"
        "• OR type `/skip` for no specific context\n\n"
        "I'll generate 3 examples based on the presentation content."
    )
    
    keyboard = [
        [InlineKeyboardButton("⏭️ Skip (No Context)", callback_data=f"skip:example:{presentation_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"ai:menu:{presentation_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def handle_ai_create_quiz(query, presentation_id: int):
    """Handle AI create quiz request - prompt user for optional input"""
    chat_id = query.message.chat_id
    
    # Get current slide
    try:
        resp = requests.get(
            f"{BACKEND_API_URL}/api/presentations/{presentation_id}",
            timeout=5
        )
        current_slide = 1
        if resp.ok:
            current_slide = resp.json().get("current_slide", 1)
    except:
        current_slide = 1
    
    # Set user state to wait for input
    user_states[chat_id] = {
        "action": "create_quiz",
        "presentation_id": presentation_id,
        "slide": current_slide
    }
    
    message = (
        f"*Create Quiz (Slide {current_slide})*\n\n"
        "Would you like to provide specific context for the quiz?\n\n"
        "• Send a text message with your requirements\n"
        "  Example: _\"focus on the main concepts\"_\n\n"
        "• OR type `/skip` to generate based on slide content only\n\n"
        "I'll generate 3 open-ended quiz questions."
    )
    
    keyboard = [
        [InlineKeyboardButton("⏭️ Skip (No Context)", callback_data=f"skip:quiz:{presentation_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"ai:menu:{presentation_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def handle_ai_create_quiz_alternatives(query, presentation_id: int):
    """Handle AI create quiz with alternatives (multiple choice) request - prompt user for optional input"""
    chat_id = query.message.chat_id
    
    # Get current slide
    try:
        resp = requests.get(
            f"{BACKEND_API_URL}/api/presentations/{presentation_id}",
            timeout=5
        )
        current_slide = 1
        if resp.ok:
            current_slide = resp.json().get("current_slide", 1)
    except:
        current_slide = 1
    
    # Set user state to wait for input
    user_states[chat_id] = {
        "action": "create_quiz_alt",
        "presentation_id": presentation_id,
        "slide": current_slide
    }
    
    message = (
        f"*Create Multiple Choice Quiz (Slide {current_slide})*\n\n"
        "Would you like to provide specific context for the quiz?\n\n"
        "• Send a text message with your requirements\n"
        "  Example: _\"make it challenging\"_\n\n"
        "• OR type `/skip` to generate based on slide content only\n\n"
        "I'll generate 3 multiple-choice quiz questions."
    )
    
    keyboard = [
        [InlineKeyboardButton("⏭️ Skip (No Context)", callback_data=f"skip:quiz_alt:{presentation_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"ai:menu:{presentation_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def handle_skip_input(query, context, presentation_id: int, action_type: str):
    """
    Handle when user clicks 'Skip (No Context)' button
    Generates AI content without user input
    """
    chat_id = query.message.chat_id
    
    # get user state to find current slide
    state = user_states.get(chat_id, {})
    current_slide = state.get("slide", 1)
    
    # loading message
    await query.edit_message_text(
        "Generating options...\n\n_This may take a few seconds_",
        parse_mode='Markdown'
    )
    
    try:
        # determine which endpoint to call, like routing
        if action_type == "example":
            endpoint = "/api/ai/create-example"
            slide_type = "example"
            title_prefix = "Examples"
        elif action_type == "quiz":
            endpoint = "/api/ai/create-quiz"
            slide_type = "quiz"
            title_prefix = "Quiz Questions"
        elif action_type == "quiz_alt":
            endpoint = "/api/ai/create-quiz-alternatives"
            slide_type = "quiz-alternatives"
            title_prefix = "Multiple Choice Quiz"
        else:
            await query.edit_message_text("❌ Invalid action type.")
            return
        
        # call backend AI endpoint with empty user_input
        ai_resp = requests.post(
            f"{BACKEND_API_URL}{endpoint}",
            json={
                "presentation_id": presentation_id,
                "slide_number": current_slide,
                "telegram_chat_id": chat_id,
                "user_input": ""  #no context
            },
            timeout=60
        )
        
        if ai_resp.ok:
            result = ai_resp.json()
            options = result.get("options", [])
            
            if len(options) < 3:
                await query.edit_message_text(
                    "❌ AI returned fewer than 3 options. Please try again.",
                    parse_mode='Markdown'
                )
                return
            
            # show the 3 options as buttons
            message = (
                f"*{title_prefix} for Slide {current_slide}*\n\n"
                "*Generated 3 options. Choose one to add to your presentation:*\n\n"
                f"*Option 1:*\n{options[0][:300]}{'...' if len(options[0]) > 300 else ''}\n\n"
                f"*Option 2:*\n{options[1][:300]}{'...' if len(options[1]) > 300 else ''}\n\n"
                f"*Option 3:*\n{options[2][:300]}{'...' if len(options[2]) > 300 else ''}\n\n"
            )
            
            # update user state with options
            user_states[chat_id] = {
                "action": f"select_{action_type}",
                "presentation_id": presentation_id,
                "slide": current_slide,
                "options": options,
                "slide_type": slide_type,
                "user_input": ""
            }
            
            keyboard = [
                [InlineKeyboardButton("✅ Choose Option 1",callback_data=f"select:0:{presentation_id}")],
                [InlineKeyboardButton("✅ Choose Option 2",callback_data=f"select:1:{presentation_id}")],
                [InlineKeyboardButton("✅ Choose Option 3",callback_data=f"select:2:{presentation_id}")],
                [InlineKeyboardButton("🔄 Generate New Options",callback_data=f"skip:{action_type}:{presentation_id}")],
                [InlineKeyboardButton("❌ Cancel", callback_data=f"ai:menu:{presentation_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(
                "❌ Failed to generate options. Please try again.",
                parse_mode='Markdown'
            )
    except Exception as e:
        print(f"Error in handle_skip_input: {e}")
        import traceback
        traceback.print_exc()
        await query.edit_message_text(
            "❌ Error connecting to backend.",
            parse_mode='Markdown'
        )


async def handle_option_selection(query, context, presentation_id: int, option_index: int):
    """
    Handle when user selects one of the 3 AI-generated options
    Calls the insert-slide endpoint to add the slide to the presentation
    """
    chat_id = query.message.chat_id
    
    #get user state
    if chat_id not in user_states:
        await query.edit_message_text("❌ Session expired. Please try again.")
        return
    
    state = user_states[chat_id]
    options = state.get("options", [])
    slide_type = state.get("slide_type", "example")
    user_input = state.get("user_input", "")
    insert_after = state.get("slide", 1)
    
    if option_index >= len(options):
        await query.edit_message_text("❌ Invalid option selected.")
        return
    
    selected_content = options[option_index]
    
    #loading message
    await query.edit_message_text(
        f"✅ *Option {option_index + 1} selected!*\n\n"
        "🔄 Inserting slide into presentation...\n\n"
        "_This may take a few seconds_",
        parse_mode='Markdown'
    )
    
    try:
        # put the slide title
        if slide_type == "example":
            slide_title = "AI Example"
        elif slide_type == "quiz":
            slide_title = "AI Quiz ❓"
        elif slide_type == "quiz-alternatives":
            slide_title = "AI Quiz ❓"
        else:
            slide_title = "AI Generated Slide"
        
        # Call backend to insert the slide
        insert_resp = requests.post(
            f"{BACKEND_API_URL}/api/ai/insert-slide",
            json={
                "presentation_id": presentation_id,
                "slide_content": selected_content,
                "slide_title": slide_title,
                "slide_type": slide_type,
                "insert_after": insert_after,
                "user_input": user_input,
                "telegram_chat_id": chat_id
            },
            timeout=90  # need to test this, to see if its slower than the timeout
        )
        
        if insert_resp.ok:
            result = insert_resp.json()
            new_slide_count = result.get("new_slide_count", 0)
            inserted_at = result.get("inserted_at", insert_after + 1)
            
            message = (
                "✅ *Slide Added Successfully!*\n\n"
                f"📍 Inserted at position: *{inserted_at}*\n"
                f"Total slides: *{new_slide_count}*\n\n"
                "_The presentation has been updated. "
                "If you're viewing it in fullscreen, the new slide is now available!_"
            )
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to Navigation", callback_data=f"back_to_nav:{presentation_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
            #clear user state
            user_states.pop(chat_id, None)
        else:
            error_data = insert_resp.json() if insert_resp.content else {}
            error_msg = error_data.get("error", "Unknown error")
            
            await query.edit_message_text(
                f"❌ *Failed to insert slide*\n\n"
                f"Error: {error_msg}\n\n"
                "Please try again or contact support.",
                parse_mode='Markdown'
            )
    except Exception as e:
        print(f"Error inserting slide: {e}")
        import traceback
        traceback.print_exc()
        
        await query.edit_message_text(
            "❌ *Error connecting to backend*\n\n"
            "Could not insert the slide. Please try again.",
            parse_mode='Markdown'
        )


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
                "*Cannot connect to backend*\n\n"
                "The server is currently unavailable. Please try again later."
            )
        }
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "message": (
                "*Request timed out*\n\n"
                "The server is taking too long to respond. Please try again."
            )
        }
    except Exception as e:
        print(f"Error linking account: {e}")
        return {
            "success": False,
            "message": "An error occurred. Please try again later."
        }


#got tired of copy pasting the controls xd
async def show_controls(chat_id, presentation_id, current_slide=1, slide_count=0, context=None):
    message = (
        "*---------------------------------------------------*\n*---------------------------------------------------*\n\n"
        f"📍 *Slide {current_slide}*" + (f" / {slide_count}" if slide_count else "") + "\n\n"
    )

    keyboard = [
        [
            InlineKeyboardButton("⬅️ Previous", callback_data=f"nav:prev:{presentation_id}"),
            InlineKeyboardButton("➡️ Next", callback_data=f"nav:next:{presentation_id}")
        ],
        [
            InlineKeyboardButton("Go to Slide", callback_data=f"nav:goto:{presentation_id}")
        ],
        [
            InlineKeyboardButton("AI Assistant", callback_data=f"ai:menu:{presentation_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text=message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular messages"""
    chat_id = update.effective_chat.id
    msg = update.message.text if update.message.text else None
    
    # check user is in AI state (waiting for example input)
    if chat_id in user_states:
        state = user_states[chat_id]
        action = state.get("action")
        presentation_id = state.get("presentation_id")
        slide = state.get("slide")
        
        if action == "create_example":
            # handle text or voice input for example creation
            user_input = None
            input_type = "text"
            
            if update.message.text:
                user_input = update.message.text
                input_type = "text"
            elif update.message.voice:
                # Handle voice message (still havent implemented it tho, should convert the audio to text here and pass it to the backend as text)
                input_type = "audio"
                # get file_id to pass to backend
                user_input = update.message.voice.file_id
            
            if user_input:
                await update.message.reply_text("Generating examples...\n\n_This may take a few seconds_")
                try:
                    # call backend AI endpoint (returns 3 options for everything, left it in the query)
                    payload = {
                        "presentation_id": presentation_id,
                        "slide_number": slide,
                        "telegram_chat_id": chat_id,
                        "user_input": user_input,
                        "input_type": input_type
                    }
                    
                    # If audio, include voice file_id
                    if input_type == "audio":
                        payload["voice_file_id"] = user_input
                    
                    ai_resp = requests.post(
                        f"{BACKEND_API_URL}/api/ai/create-example",
                        json=payload,
                        timeout=60
                    )
                    
                    if ai_resp.ok:
                        result = ai_resp.json()
                        options = result.get("options", [])
                        
                        if len(options) < 3:
                            await update.message.reply_text(
                                "❌ AI returned fewer than 3 options. Please try again."
                            )
                            user_states.pop(chat_id, None)
                            return
                        
                        # Show the 3 options as buttons
                        message = (
                            f"*Examples for Slide {slide}*\n\n"
                            "*Generated 3 options. Choose one to add to your presentation:*\n\n"
                            f"*Option 1:*\n{options[0][:300]}{'...' if len(options[0]) > 300 else ''}\n\n"
                            f"*Option 2:*\n{options[1][:300]}{'...' if len(options[1]) > 300 else ''}\n\n"
                            f"*Option 3:*\n{options[2][:300]}{'...' if len(options[2]) > 300 else ''}\n\n"
                        )
                        
                        # Update user state with options
                        user_states[chat_id] = {
                            "action": "select_example",
                            "presentation_id": presentation_id,
                            "slide": slide,
                            "options": options,
                            "slide_type": "example",
                            "user_input": user_input if input_type == "text" else "voice message"
                        }
                        
                        keyboard = [
                            [InlineKeyboardButton("✅ Choose Option 1", callback_data=f"select:0:{presentation_id}")],
                            [InlineKeyboardButton("✅ Choose Option 2", callback_data=f"select:1:{presentation_id}")],
                            [InlineKeyboardButton("✅ Choose Option 3", callback_data=f"select:2:{presentation_id}")],
                            [InlineKeyboardButton("🔄 Generate New Options", callback_data=f"ai:create_example:{presentation_id}")],
                            [InlineKeyboardButton("❌ Cancel", callback_data=f"ai:menu:{presentation_id}")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await update.message.reply_text(
                            message,
                            parse_mode='Markdown',
                            reply_markup=reply_markup
                        )
                    else:
                        await update.message.reply_text("❌ Failed to generate examples. Please try again.")
                        user_states.pop(chat_id, None)
                        pres_resp = requests.get(f"{BACKEND_API_URL}/api/presentations/{presentation_id}", timeout=5)
                        if pres_resp.ok:
                            pres_data = pres_resp.json()
                            await show_controls(chat_id, presentation_id, pres_data.get("current_slide", 1), pres_data.get("slide_count", 0), context)
                except Exception as e:
                    print(f"Error creating example: {e}")
                    import traceback
                    traceback.print_exc()
                    await update.message.reply_text("❌ Error connecting to backend.")
                    user_states.pop(chat_id, None)
                    try:
                        pres_resp = requests.get(f"{BACKEND_API_URL}/api/presentations/{presentation_id}", timeout=5)
                        if pres_resp.ok:
                            pres_data = pres_resp.json()
                            await show_controls(chat_id, presentation_id, pres_data.get("current_slide", 1), pres_data.get("slide_count", 0), context)
                    except:
                        pass
                
                # Don't clear user state yet - they need to select an option
                return
            else:
                await update.message.reply_text("Please send a text or voice message.")
                return
        
        elif action in ["create_quiz", "create_quiz_alt"]:
            # Handle text input for quiz creation
            user_input = update.message.text if update.message.text else None
            
            if user_input:
                await update.message.reply_text("Generating quiz questions...\n\n_This may take a few seconds_")
                
                try:
                    # Determine endpoint and slide type
                    if action == "create_quiz":
                        endpoint = "/api/ai/create-quiz"
                        slide_type = "quiz"
                        title_prefix = "Quiz Questions"
                    else:  # create_quiz_alt
                        endpoint = "/api/ai/create-quiz-alternatives"
                        slide_type = "quiz-alternatives"
                        title_prefix = "Multiple Choice Quiz"
                    
                    # Call backend AI endpoint
                    ai_resp = requests.post(
                        f"{BACKEND_API_URL}{endpoint}",
                        json={
                            "presentation_id": presentation_id,
                            "slide_number": slide,
                            "telegram_chat_id": chat_id,
                            "user_input": user_input
                        },
                        timeout=60
                    )
                    
                    if ai_resp.ok:
                        result = ai_resp.json()
                        options = result.get("options", [])
                        
                        if len(options) < 3:
                            await update.message.reply_text(
                                "❌ AI returned fewer than 3 options. Please try again."
                            )
                            user_states.pop(chat_id, None)
                            return
                        
                        # Show the 3 options as buttons
                        message = (
                            f"*{title_prefix} for Slide {slide}*\n\n"
                            "*Generated 3 options. Choose one to add to your presentation:*\n\n"
                            f"*Option 1:*\n{options[0][:300]}{'...' if len(options[0]) > 300 else ''}\n\n"
                            f"*Option 2:*\n{options[1][:300]}{'...' if len(options[1]) > 300 else ''}\n\n"
                            f"*Option 3:*\n{options[2][:300]}{'...' if len(options[2]) > 300 else ''}\n\n"
                        )
                        
                        # Update user state with options
                        user_states[chat_id] = {
                            "action": f"select_{action.split('_')[1]}{'_alt' if action == 'create_quiz_alt' else ''}",
                            "presentation_id": presentation_id,
                            "slide": slide,
                            "options": options,
                            "slide_type": slide_type,
                            "user_input": user_input
                        }
                        
                        keyboard = [
                            [InlineKeyboardButton("✅ Choose Option 1",callback_data=f"select:0:{presentation_id}")],
                            [InlineKeyboardButton("✅ Choose Option 2",callback_data=f"select:1:{presentation_id}")],
                            [InlineKeyboardButton("✅ Choose Option 3",callback_data=f"select:2:{presentation_id}")],
                            [InlineKeyboardButton("🔄 Generate New Options",callback_data=f"skip:{'quiz_alt' if action == 'create_quiz_alt' else 'quiz'}:{presentation_id}")],
                            [InlineKeyboardButton("❌ Cancel",callback_data=f"ai:menu:{presentation_id}")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await update.message.reply_text(
                            message,
                            parse_mode='Markdown',
                            reply_markup=reply_markup
                        )
                    else:
                        await update.message.reply_text("❌ Failed to generate quiz questions. Please try again.")
                        user_states.pop(chat_id, None)
                except Exception as e:
                    print(f"Error creating quiz: {e}")
                    import traceback
                    traceback.print_exc()
                    await update.message.reply_text("❌ Error connecting to backend.")
                    user_states.pop(chat_id, None)
                
                # Don't clear user state yet - they need to select an option
                return
            else:
                await update.message.reply_text("Please send a text message with your requirements, or use the Skip button.")
                return
    
    # check if waiting for slide number (goto functionality)
    if context.user_data.get('waiting_for_slide_number', False):
        try:
            slide_number = int(msg.strip())
            presentation_id = context.user_data.get('goto_presentation_id')
            
            if not presentation_id:
                await update.message.reply_text("Session expired. Please try again.")
                context.user_data['waiting_for_slide_number'] = False
                return
            
            # send goto command to backend
            resp = requests.post(
                f"{BACKEND_API_URL}/api/presentations/{presentation_id}/control",
                json={
                    "action": "goto",
                    "target_slide": slide_number,
                    "telegram_chat_id": chat_id
                },
                timeout=5
            )
            
            if resp.ok:
                data = resp.json()
                current_slide = data.get("current_slide", slide_number)
                
                pres_resp = requests.get(
                    f"{BACKEND_API_URL}/api/presentations/{presentation_id}",
                    timeout=5
                )
                slide_count = pres_resp.json().get("slide_count", 0) if pres_resp.ok else 0
                
                await show_controls(chat_id, presentation_id, current_slide, slide_count, context)
            else:
                await update.message.reply_text("❌ Could not jump to that slide.")
                pres_resp = requests.get(f"{BACKEND_API_URL}/api/presentations/{presentation_id}", timeout=5)
                if pres_resp.ok:
                    pres_data = pres_resp.json()
                    await show_controls(chat_id, presentation_id, pres_data.get("current_slide", 1), pres_data.get("slide_count", 0), context)
            
            context.user_data['waiting_for_slide_number'] = False
            context.user_data.pop('goto_presentation_id', None)
            return
            
        except ValueError:
            await update.message.reply_text(
                "Please send a valid slide number (e.g., `5`).",
                parse_mode='Markdown'
            )
            # show controls when the input is bad
            presentation_id = context.user_data.get('goto_presentation_id')
            if presentation_id:
                try:
                    pres_resp = requests.get(f"{BACKEND_API_URL}/api/presentations/{presentation_id}", timeout=5)
                    if pres_resp.ok:
                        pres_data = pres_resp.json()
                        await show_controls(chat_id, presentation_id, pres_data.get("current_slide", 1), pres_data.get("slide_count", 0), context)
                except:
                    pass
            return
        except Exception as e:
            print(f"Error in goto: {e}")
            await update.message.reply_text("Ooops, Error connecting to backend.")
            # the user can still use the control even if it fails, to keep the illusion xd
            presentation_id = context.user_data.get('goto_presentation_id')
            if presentation_id:
                try:
                    pres_resp = requests.get(f"{BACKEND_API_URL}/api/presentations/{presentation_id}", timeout=5)
                    if pres_resp.ok:
                        pres_data = pres_resp.json()
                        await show_controls(chat_id, presentation_id, pres_data.get("current_slide", 1), pres_data.get("slide_count", 0), context)
                except:
                    pass
            context.user_data['waiting_for_slide_number'] = False
            return
    
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
                "*Account Not Linked*\n\n"
                "Please link your account first to ask questions.\n\n"
                "Click the button below to get started!",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return
    except:
        await update.message.reply_text(
            "Cannot connect to server. Please try again later."
        )
        return
    
    # User is linked, process the question
    # await update.message.reply_text("Processing your question...")
    
    # Send question to backend and get response
    # response = await send_question_to_backend(chat_id, msg)
    # await update.message.reply_text(response, parse_mode='Markdown')


async def require_linked_user(update, context):
    chat_id = update.effective_chat.id
    resp = requests.get(f"{BACKEND_API_URL}/api/telegram/check/{chat_id}", timeout=5)
    if resp.status_code != 200:
        await update.message.reply_text("Please link your account first with /link.")
        return None
    return resp.json()

async def start_presentation_cmd(update, context):
    user = await require_linked_user(update, context)
    if not user:
        return
    presentation_id = await resolve_presentation_id(update, context, user)
    if not presentation_id:
        return

    try:
        requests.post(
            f"{BACKEND_API_URL}/api/presentations/{presentation_id}/start",
            json={"telegram_chat_id": update.effective_chat.id},
            timeout=5,
        )
        context.user_data["presentation_id"] = presentation_id  # keep active ID
        await update.message.reply_text("Presentation started.")
    except requests.RequestException:
        await update.message.reply_text("Error connecting to the backend.")


async def next_slide_cmd(update, context):
    await _send_control_command(update, context, "next")

async def prev_slide_cmd(update, context):
    await _send_control_command(update, context, "prev")

async def goto_slide_cmd(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /goto 5")
        return
    await _send_control_command(
        update, context, "goto", target_slide=int(context.args[0])
    )

async def download_cmd(update, context):
    user = await require_linked_user(update, context)
    if not user:
        return
    presentation_id = await resolve_presentation_id(update, context, user)
    if not presentation_id:
        return
    resp = requests.post(f"{BACKEND_API_URL}/api/presentations/{presentation_id}/convert")
    pdf_url = resp.json()["pdf_url"]
    await update.message.reply_document(
        document=pdf_url.replace("/api", f"{BACKEND_API_URL}/api"),
        filename="presentation.pdf"
    )

async def preview_next_cmd(update, context):
    await _request_slide_image(update, context, offset=1)

async def _send_control_command(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, target_slide: int | None = None):
    user = await require_linked_user(update, context)
    user = await require_linked_user(update, context)
    if not user:
        return

    presentation_id = await resolve_presentation_id(update, context, user)
    if not presentation_id:
        return
    payload = {
        "action": action,
        "telegram_chat_id": update.effective_chat.id
    }
    if target_slide:
        payload["target_slide"] = target_slide
    resp = requests.post(
        f"{BACKEND_API_URL}/api/presentations/{presentation_id}/control",
        json=payload, timeout=5
    )
    if resp.ok:
        slide = resp.json()["current_slide"]
        await update.message.reply_text(f"Now on slide {slide}.")
    else:
        await update.message.reply_text("Could not update the presentation.")

async def end_presentation_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await require_linked_user(update, context)
    if not user:
        return

    presentation_id = await resolve_presentation_id(update, context, user)
    if not presentation_id:
        return

    try:
        resp = requests.post(
            f"{BACKEND_API_URL}/api/presentations/{presentation_id}/end",
            json={"telegram_chat_id": update.effective_chat.id},
            timeout=5,
        )
        if resp.status_code == 200:
            await update.message.reply_text("✅ Presentation ended.")
        else:
            await update.message.reply_text("Could not finish the presentation.")
    except requests.RequestException:
        await update.message.reply_text("Error connecting to the backend.")

async def _request_slide_image(update: Update, context: ContextTypes.DEFAULT_TYPE, offset: int):
    user = await require_linked_user(update, context)
    if not user:
        return

    presentation_id = await resolve_presentation_id(update, context, user)
    try:
        resp = requests.get(
            f"{BACKEND_API_URL}/api/presentations/{presentation_id}/slides/next-image",
            params={"offset": offset},
            timeout=10,
        )
        if resp.status_code != 200:
            await update.message.reply_text("Could not retrieve the next slide.")
            return

        image_bytes = resp.content
        await update.message.reply_photo(image=image_bytes)
    except requests.RequestException:
        await update.message.reply_text("Error connecting to the backend.")


async def resolve_presentation_id(update, context, user):
    """
    Return the ID of the presentation that will be controlled.
    First looks at the backend JSON response, then falls back to the value stored in context.user_data.
    """
    presentation_id = user.get("active_presentation_id")
    if presentation_id:
        context.user_data["presentation_id"] = presentation_id
        return presentation_id

    # Fallback: use the last id we stored
    cached = context.user_data.get("presentation_id")
    if cached:
        return cached

    await update.message.reply_text(
        "There is no active presentation associated. Start one from the web app or with /start_presentation."
    )
    return None


def main():
    """starting the bot execution"""
    global bot_app
    
    if not TELEGRAM_TOKEN:
        print("ERROR: TELEGRAM_TOKEN not set in env")
        return
    
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    bot_app = app  # globally for WebSocket handlers

    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("link", link_start))
    app.add_handler(CommandHandler("start_presentation", start_presentation_cmd))
    app.add_handler(CommandHandler("end_presentation", end_presentation_cmd))
    app.add_handler(CommandHandler("next", next_slide_cmd))
    app.add_handler(CommandHandler("prev", prev_slide_cmd))
    app.add_handler(CommandHandler("goto", goto_slide_cmd))
    app.add_handler(CommandHandler("download", download_cmd))
    app.add_handler(CommandHandler("preview", preview_next_cmd))
    
    # callback query handler for buttons
    app.add_handler(CallbackQueryHandler(button_callback))

    # message handler (must be last, do not movee)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("TutorFlow Bot is starting...")
    
    # Initialize the application
    async def post_init(application):
        """Initialize WebSocket connection after bot starts"""
        print("🔗 Connecting to backend WebSocket...")
        asyncio.create_task(connect_socket())
    
    app.post_init = post_init
    
    print("Bot is ready and listening for messages!!!!!!!!!!!!!!!!")
    
    app.run_polling()

#dont actually need this, I can just call main, but its good practice supposedly xd
if __name__ == "__main__":
    main()
