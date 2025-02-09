import logging
import random
import json
import hmac
import hashlib
import os
from datetime import datetime, timedelta
from telegram import WebAppInfo, Chat, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from twilio.rest import Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Deploy token for webapp validation
deploy_token = os.getenv("TELEGRAM_TOKEN", "f396a67a498f2ac86deff58f4871452a3517115ee8bdafcb275aafccc597e2c5")

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO,
    filename='bot.log'
)
logger = logging.getLogger(__name__)

# Store OTPs and rate limiting data
otp_store = {}
rate_limit_store = {}

# Load configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://bfcd0268e6.tapps.global/latest")

# Initialize Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def generate_otp() -> str:
    """Generate a secure 6-digit OTP using cryptographic random"""
    try:
        import secrets
        return ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    except ImportError:
        logger.warning("Using fallback random for OTP generation")
        return ''.join([str(random.randint(0, 9)) for _ in range(6)])

def is_valid_phone_number(phone: str) -> bool:
    """Validate phone number format"""
    import re
    pattern = r'^\+[1-9]\d{6,14}$'
    return bool(re.match(pattern, phone))

def format_phone_number(phone: str) -> str:
    """Format phone number for display (hide middle digits)"""
    if len(phone) <= 6:
        return phone
    return f"{phone[:3]}{'*' * (len(phone) - 6)}{phone[-3:]}"

def check_rate_limit(user_id: int, action: str) -> bool:
    """Check if user has exceeded rate limit"""
    current_time = datetime.now()
    user_limits = rate_limit_store.get(user_id, {})
    
    limits = {
        'otp_request': {'count': 3, 'window': 300},  # 3 requests per 5 minutes
        'otp_verify': {'count': 5, 'window': 300},   # 5 attempts per 5 minutes
    }
    
    if action not in limits:
        return True
        
    user_limits = {
        k: v for k, v in user_limits.items()
        if (current_time - v['timestamp']).total_seconds() < limits[k]['window']
    }
    
    action_data = user_limits.get(action, {'count': 0, 'timestamp': current_time})
    if action_data['count'] >= limits[action]['count']:
        return False
        
    action_data['count'] += 1
    action_data['timestamp'] = current_time
    user_limits[action] = action_data
    rate_limit_store[user_id] = user_limits
    
    return True

def store_otp(user_id: int, phone_number: str, otp: str):
    """Store OTP with 5-minute expiry"""
    expiry_time = datetime.now() + timedelta(minutes=5)
    otp_store[user_id] = {
        'otp': otp,
        'phone': phone_number,
        'expiry': expiry_time
    }

def verify_otp(user_id: int, otp: str) -> bool:
    """Verify OTP and check if it's still valid"""
    if user_id not in otp_store:
        return False
    
    stored_data = otp_store[user_id]
    if datetime.now() > stored_data['expiry']:
        del otp_store[user_id]
        return False
    
    if otp == stored_data['otp']:
        del otp_store[user_id]
        return True
    return False

def send_otp_sms(phone_number: str, otp: str):
    """Send OTP via Twilio SMS"""
    try:
        message = twilio_client.messages.create(
            to=phone_number,
            from_=TWILIO_PHONE_NUMBER,
            body=f"Your B8NKR verification code is: {otp}"
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send SMS: {str(e)}")
        return False

async def verify_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle phone number verification"""
    try:
        user_id = update.effective_user.id
        
        if not check_rate_limit(user_id, 'otp_request'):
            await update.message.reply_text(
                "⚠️ Too many OTP requests.\n"
                "Please wait a few minutes before trying again."
            )
            return

        phone_number = update.message.text.strip()
        
        if not is_valid_phone_number(phone_number):
            await update.message.reply_text(
                "❌ Invalid phone number format!\n"
                "Please provide your number in international format (e.g., +1234567890)"
            )
            return

        for stored_id, data in otp_store.items():
            if stored_id != user_id and data.get('phone') == phone_number:
                logger.warning(f"Phone number {format_phone_number(phone_number)} already in use")
                await update.message.reply_text(
                    "❌ This phone number is already in use.\n"
                    "Please use a different number or contact support."
                )
                return

        otp = generate_otp()
        store_otp(user_id, phone_number, otp)
        
        if send_otp_sms(phone_number, otp):
            logger.info(f"OTP sent to {format_phone_number(phone_number)} for user {user_id}")
            await update.message.reply_text(
                f"✅ Verification code sent to {format_phone_number(phone_number)}!\n"
                "Please enter the 6-digit code.\n"
                "⏱️ You have 5 minutes to enter the code."
            )
            context.user_data['awaiting_otp'] = True
            context.user_data['phone_number'] = phone_number
        else:
            logger.error(f"Failed to send OTP to {format_phone_number(phone_number)}")
            await update.message.reply_text(
                "❌ Failed to send verification code.\n"
                "Please check the number and try again later."
            )
    except Exception as e:
        logger.error(f"Error in verify_phone for user {user_id}: {str(e)}")
        await update.message.reply_text(
            "❌ An error occurred.\n"
            "Please try again or contact support if the problem persists."
        )

async def verify_otp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle OTP verification"""
    try:
        user_id = update.effective_user.id
        phone_number = context.user_data.get('phone_number')
        
        if not phone_number:
            logger.error(f"No phone number found for user {user_id}")
            await update.message.reply_text(
                "❌ Session expired.\n"
                "Please start over with /start"
            )
            context.user_data['awaiting_otp'] = False
            return
        
        if not check_rate_limit(user_id, 'otp_verify'):
            await update.message.reply_text(
                "⚠️ Too many verification attempts.\n"
                "Please wait a few minutes before trying again."
            )
            return

        user_otp = update.message.text.strip()
        
        if not user_otp.isdigit() or len(user_otp) != 6:
            await update.message.reply_text(
                "❌ Invalid code format!\n"
                "Please enter the 6-digit code sent to your phone."
            )
            return
        
        if verify_otp(user_id, user_otp):
            logger.info(f"OTP verified successfully for {format_phone_number(phone_number)}")
            context.user_data['verified'] = True
            context.user_data['awaiting_otp'] = False
            context.user_data['verified_phone'] = phone_number
            
            keyboard = [
                [InlineKeyboardButton("👤 My Profile", callback_data="profile")],
                [InlineKeyboardButton("💰 Check Balance", callback_data="balance")],
                [InlineKeyboardButton("📤 Transfer Money", callback_data="transfer")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ Success! Phone number {format_phone_number(phone_number)} verified.\n\n"
                "🎉 Welcome to B8NKR! You now have full access to all features.\n"
                "What would you like to do?",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            remaining_attempts = 5 - len([
                action for action, data in rate_limit_store.get(user_id, {}).items()
                if action == 'otp_verify'
            ])
            
            logger.warning(f"Invalid OTP attempt from user {user_id} ({remaining_attempts} attempts remaining)")
            await update.message.reply_text(
                "❌ Invalid or expired verification code.\n"
                f"You have {remaining_attempts} attempts remaining.\n\n"
                "Please try again or use /start to request a new code."
            )
    except Exception as e:
        logger.error(f"Error in verify_otp_handler for user {user_id}: {str(e)}")
        await update.message.reply_text(
            "❌ An error occurred.\n"
            "Please try again or contact support if the problem persists."
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the bot and show authentication options"""
    user_id = update.effective_user.id
    
    if context.user_data.get('verified', False):
        keyboard = [
            [InlineKeyboardButton("👤 My Profile", callback_data="profile")],
            [InlineKeyboardButton("💰 Check Balance", callback_data="balance")],
            [InlineKeyboardButton("📤 Transfer Money", callback_data="transfer")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"👋 Welcome back!\n\n"
            "🏦 *B8NKR Main Menu*\n"
            "What would you like to do?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return

    keyboard = [
        [InlineKeyboardButton("📱 Verify Phone Number", callback_data="verify_phone")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎉 *Welcome to B8NKR!*\n\n"
        "To get started, please verify your identity:\n\n"
        "1️⃣ Click the button below to verify your phone number\n\n"
        "💡 Your security is our priority.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help information"""
    await update.message.reply_text(
        "🔍 *Available Commands*\n\n"
        "/start - Begin verification process\n"
        "/menu - Show main menu\n"
        "/profile - View your profile\n"
        "/balance - Check your balance\n"
        "/transfer - Send or request money\n"
        "/history - View transaction history\n"
        "/cancel - Cancel current operation\n"
        "/help - Show this help message\n\n"
        "💡 *Tips*:\n"
        "• Keep your phone number up to date\n"
        "• Never share your OTP with anyone\n"
        "• Contact support if you notice suspicious activity",
        parse_mode='Markdown'
    )

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user balance"""
    if not context.user_data.get('verified', False):
        await update.message.reply_text(
            "⚠️ Please verify your phone number first!\n"
            "Use /start to begin verification."
        )
        return

    balance = 1000.00  # Mock balance

    await update.message.reply_text(
        f"💰 Your current balance is: `${balance:,.2f}`",
        parse_mode='Markdown'
    )

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user profile and transaction summary"""
    if not context.user_data.get('verified', False):
        await update.message.reply_text(
            "⚠️ Please verify your phone number first!\n"
            "Use /start to begin verification."
        )
        return

    phone = context.user_data.get('verified_phone', 'Unknown')
    
    profile_data = {
        'balance': 1000.00,
        'total_sent': 250.00,
        'total_received': 150.00,
        'pending_requests': 1,
        'join_date': '2024-01-01',
        'last_transfer': '2024-01-15'
    }
    
    keyboard = [
        [
            InlineKeyboardButton("📊 Transaction History", callback_data="transfer_history"),
            InlineKeyboardButton("✏️ Edit Profile", callback_data="edit_profile")
        ],
        [InlineKeyboardButton("« Back to Menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👤 *Your Profile*\n\n"
        f"📱 Phone: `{format_phone_number(phone)}`\n"
        f"💰 Balance: `${profile_data['balance']:,.2f}`\n"
        f"📅 Member since: {profile_data['join_date']}\n\n"
        "*Transaction Summary*\n"
        f"📤 Total Sent: `${profile_data['total_sent']:,.2f}`\n"
        f"📥 Total Received: `${profile_data['total_received']:,.2f}`\n"
        f"⏳ Pending Requests: {profile_data['pending_requests']}\n"
        f"🕒 Last Transfer: {profile_data['last_transfer']}\n\n"
        "Select an option below:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show main menu"""
    if not context.user_data.get('verified', False):
        await update.message.reply_text(
            "⚠️ Please verify your phone number first!\n"
            "Use /start to begin verification."
        )
        return

    keyboard = [
        [InlineKeyboardButton("👤 My Profile", callback_data="profile")],
        [InlineKeyboardButton("💰 Check Balance", callback_data="balance")],
        [InlineKeyboardButton("📤 Transfer Money", callback_data="transfer")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🏦 *Welcome to B8NKR*\n"
        "What would you like to do?",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def transfer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Initiate money transfer process"""
    if not context.user_data.get('verified', False):
        await update.message.reply_text(
            "⚠️ Please verify your phone number first!\n"
            "Use /start to begin verification."
        )
        return

    keyboard = [
        [InlineKeyboardButton("💸 Send Money", callback_data="send_money")],
        [InlineKeyboardButton("📥 Request Money", callback_data="request_money")],
        [InlineKeyboardButton("« Back to Menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "💸 *Transfer Money*\n\n"
        "Choose an option:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel current operation"""
    context.user_data.pop('transfer_state', None)
    context.user_data.pop('transfer_data', None)
    context.user_data.pop('awaiting_phone', None)
    context.user_data.pop('awaiting_otp', None)
    
    await update.message.reply_text(
        "🔄 Current operation cancelled.\n"
        "Type /menu to see available options."
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()

    if query.data == "verify_phone":
        await query.message.reply_text(
            "📱 Please send your phone number in international format\n"
            "Example: +1234567890\n\n"
            "ℹ️ Your number will only be used for verification."
        )
        context.user_data['awaiting_phone'] = True
    elif query.data == "profile":
        await profile_command(update, context)
    elif query.data == "balance":
        await balance_command(update, context)
    elif query.data == "transfer":
        await transfer_command(update, context)
    elif query.data == "back_to_main":
        await menu_command(update, context)
    elif query.data == "send_money":
        context.user_data['transfer_state'] = 'awaiting_recipient'
        await query.message.edit_text(
            "📱 Enter recipient's phone number:\n"
            "Example: +1234567890\n\n"
            "Type /cancel to cancel"
        )
    elif query.data == "request_money":
        context.user_data['transfer_state'] = 'awaiting_sender'
        await query.message.edit_text(
            "📱 Enter sender's phone number:\n"
            "Example: +1234567890\n\n"
            "Type /cancel to cancel"
        )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages"""
    try:
        if context.user_data.get('awaiting_phone', False):
            context.user_data['awaiting_phone'] = False
            await verify_phone(update, context)
        elif context.user_data.get('awaiting_otp', False):
            await verify_otp_handler(update, context)
        elif context.user_data.get('transfer_state'):
            await handle_transfer(update, context)
        else:
            await update.message.reply_text(
                "❓ I don't understand that command.\n"
                "Use /menu to see available options."
            )
    except Exception as e:
        logger.error(f"Error in message_handler: {str(e)}")
        await update.message.reply_text(
            "❌ An error occurred processing your request.\n"
            "Please try again or use /menu to start over."
        )

async def cleanup_expired_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cleanup expired OTPs and rate limit data"""
    try:
        current_time = datetime.now()
        
        expired_otps = [
            user_id for user_id, data in otp_store.items()
            if current_time > data['expiry']
        ]
        for user_id in expired_otps:
            del otp_store[user_id]
            
        expired_limits = []
        for user_id, limits in rate_limit_store.items():
            expired_actions = [
                action for action, data in limits.items()
                if (current_time - data['timestamp']).total_seconds() > 3600
            ]
            for action in expired_actions:
                del limits[action]
            if not limits:
                expired_limits.append(user_id)
                
        for user_id in expired_limits:
            del rate_limit_store[user_id]
            
        logger.info(f"Cleanup: Removed {len(expired_otps)} expired OTPs and {len(expired_limits)} expired rate limits")
        
    except Exception as e:
        logger.error(f"Error in cleanup task: {str(e)}")

def main() -> None:
    """Start the bot"""
    try:
        application = (
            ApplicationBuilder()
            .token(deploy_token)
            .build()
        )
        logger.info("Bot initialized successfully")

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("menu", menu_command))
        application.add_handler(CommandHandler("profile", profile_command))
        application.add_handler(CommandHandler("cancel", cancel_command))
        application.add_handler(CommandHandler("balance", balance_command))
        application.add_handler(CommandHandler("transfer", transfer_command))
        application.add_handler(CommandHandler("help", help_command))
        
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

        job_queue = application.job_queue
        job_queue.run_repeating(cleanup_expired_data, interval=900, first=10)
        logger.info("Scheduled cleanup job")

        logger.info("Starting bot polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Error running bot: {str(e)}")
        raise

if __name__ == "__main__":
    main()
