import logging
import random
import json
import hmac
import hashlib
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from twilio.rest import Client

# Deploy token for webapp validation
deploy_token = "f396a67a498f2ac86deff58f4871452a3517115ee8bdafcb275aafccc597e2c5"

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
TWILIO_ACCOUNT_SID = "ACd92d35abb342c43469a7211c175e19c4"
TWILIO_AUTH_TOKEN = "d852ee26fd60230e17f8ca6f4b372612"
TWILIO_PHONE_NUMBER = "+18885752860"
WEBAPP_URL = "https://bfcd0268e6.tapps.global/latest"

# Initialize Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def generate_otp() -> str:
    """Generate a secure 6-digit OTP using cryptographic random"""
    try:
        # Use secrets for cryptographically strong random numbers
        import secrets
        return ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    except ImportError:
        # Fallback to random if secrets not available
        logger.warning("Using fallback random for OTP generation")
        return ''.join([str(random.randint(0, 9)) for _ in range(6)])

def is_valid_phone_number(phone: str) -> bool:
    """Validate phone number format"""
    import re
    # Basic phone number validation (international format)
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
    
    # Define limits
    limits = {
        'otp_request': {'count': 3, 'window': 300},  # 3 requests per 5 minutes
        'otp_verify': {'count': 5, 'window': 300},   # 5 attempts per 5 minutes
    }
    
    if action not in limits:
        return True
        
    # Clean up old entries
    user_limits = {
        k: v for k, v in user_limits.items()
        if (current_time - v['timestamp']).total_seconds() < limits[k]['window']
    }
    
    # Check limit
    action_data = user_limits.get(action, {'count': 0, 'timestamp': current_time})
    if action_data['count'] >= limits[action]['count']:
        return False
        
    # Update counter
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

def get_webapp_url(user_id: int) -> str:
    """Generate secure web app URL with user data"""
    try:
        # Create initialization data with additional security parameters
        init_data = {
            'user': str(user_id),
            'auth_date': str(int(datetime.now().timestamp())),
            'start_param': 'authentication',
            'session': hmac.new(
                deploy_token.encode(),
                str(user_id).encode(),
                hashlib.sha256
            ).hexdigest()[:16]  # Use first 16 chars as session ID
        }
        
        # Generate hash
        data_check_string = '\n'.join(f'{k}={v}' for k, v in sorted(init_data.items()))
        secret_key = hmac.new(
            "WebAppData".encode(),
            deploy_token.encode(),
            hashlib.sha256
        ).digest()
        
        init_data['hash'] = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Build URL with parameters
        params = '&'.join(f'{k}={v}' for k, v in init_data.items())
        webapp_url = f"{WEBAPP_URL}?{params}"
        
        logger.info(f"Generated webapp URL for user {user_id}")
        return webapp_url
        
    except Exception as e:
        logger.error(f"Error generating webapp URL: {str(e)}")
        return WEBAPP_URL  # Fallback to basic URL if generation fails

def validate_webapp_data(init_data: str, user_id: int) -> bool:
    """Validate web app initialization data"""
    try:
        # Parse the init data
        init_data_dict = dict(param.split('=') for param in init_data.split('&'))
        
        # Verify required fields
        required_fields = ['user', 'auth_date', 'session', 'hash']
        if not all(field in init_data_dict for field in required_fields):
            logger.error("Missing required fields in webapp data")
            return False
            
        # Verify user ID matches
        if init_data_dict['user'] != str(user_id):
            logger.error("User ID mismatch in webapp data")
            return False
            
        # Verify session is valid
        expected_session = hmac.new(
            deploy_token.encode(),
            str(user_id).encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        if init_data_dict['session'] != expected_session:
            logger.error("Invalid session in webapp data")
            return False
            
        # Verify auth_date is recent (within last 5 minutes)
        auth_timestamp = int(init_data_dict['auth_date'])
        current_timestamp = int(datetime.now().timestamp())
        if current_timestamp - auth_timestamp > 300:  # 5 minutes
            logger.error("Expired auth_date in webapp data")
            return False
        
        # Verify the hash matches
        data_check_string = '\n'.join(
            f'{k}={v}' for k, v in sorted(init_data_dict.items()) 
            if k != 'hash'
        )
        secret_key = hmac.new(
            "WebAppData".encode(), 
            deploy_token.encode(),
            hashlib.sha256
        ).digest()
        
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if calculated_hash != init_data_dict['hash']:
            logger.error("Invalid hash in webapp data")
            return False
            
        logger.info(f"Successfully validated webapp data for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error validating webapp data: {str(e)}")
        return False

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the bot and show authentication options"""
    user_id = update.effective_user.id
    
    # Check if user is already verified
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

    # New user verification flow
    webapp_url = get_webapp_url(user_id)
    keyboard = [
        [InlineKeyboardButton("🌐 Open Web App", web_app=WebAppInfo(url=webapp_url))],
        [InlineKeyboardButton("📱 Verify Phone Number", callback_data="verify_phone")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎉 *Welcome to B8NKR!*\n\n"
        "To get started, please verify your identity using one of these methods:\n\n"
        "1️⃣ Open our secure web app\n"
        "2️⃣ Verify directly through this chat\n\n"
        "💡 Your security is our priority.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def verify_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle phone number verification"""
    try:
        user_id = update.effective_user.id
        
        # Check rate limit for OTP requests
        if not check_rate_limit(user_id, 'otp_request'):
            await update.message.reply_text(
                "⚠️ Too many OTP requests.\n"
                "Please wait a few minutes before trying again."
            )
            return

        phone_number = update.message.text.strip()
        
        # Validate phone number format
        if not is_valid_phone_number(phone_number):
            await update.message.reply_text(
                "❌ Invalid phone number format!\n"
                "Please provide your number in international format (e.g., +1234567890)"
            )
            return

        # Check if number is already verified by another user
        for stored_id, data in otp_store.items():
            if stored_id != user_id and data.get('phone') == phone_number:
                logger.warning(f"Phone number {format_phone_number(phone_number)} already in use")
                await update.message.reply_text(
                    "❌ This phone number is already in use.\n"
                    "Please use a different number or contact support."
                )
                return

        # Generate and store OTP
        otp = generate_otp()
        store_otp(user_id, phone_number, otp)
        
        # Send OTP via SMS
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
        
        # Check rate limit for OTP verification attempts
        if not check_rate_limit(user_id, 'otp_verify'):
            await update.message.reply_text(
                "⚠️ Too many verification attempts.\n"
                "Please wait a few minutes before trying again."
            )
            return

        user_otp = update.message.text.strip()
        
        # Validate OTP format
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

    # Mock balance data for demonstration
    balance = 1000.00  # Replace with actual balance retrieval logic

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
    
    # Mock data for demonstration
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
        "What would you like to do?"),
async def transfer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Initiate money transfer process""",
    context.user_data['transfer_state'] = 'awaiting_recipient'
    await update.message.reply_text(
        "📱 Please enter the recipient's phone number in international format (e.g., +1234567890):\n"
        "Type /cancel to cancel"
    )

async def handle_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        parse_mode='Markdown'
    

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel current operation"""
    # Clear any ongoing operations
    context.user_data.pop('transfer_state', None)
    context.user_data.pop('transfer_data', None)
    context.user_data.pop('awaiting_phone', None)
    context.user_data.pop('awaiting_otp', None)
    
    await update.message.reply_text(
        "🔄 Current operation cancelled.\n"
        "Type /menu to see available options."
    )

async def handle_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle money transfer flow"""
    user_id = update.effective_user.id
    message = update.message.text.strip()
    state = context.user_data.get('transfer_state')
    
    if message.lower() == '/cancel':
        context.user_data.pop('transfer_state', None)
        context.user_data.pop('transfer_data', None)
        await update.message.reply_text(
            "💫 Transfer cancelled.\n"
            "Type /menu to return to main menu."
        )
        return

    if state == 'awaiting_recipient' or state == 'awaiting_sender':
        # Validate phone number
        if not is_valid_phone_number(message):
            await update.message.reply_text(
                "❌ Invalid phone number format!\n"
                "Please use international format (e.g., +1234567890)\n"
                "Type /cancel to cancel"
            )
            return
            
        # Store the phone number and move to amount state
        context.user_data['transfer_data'] = {'phone': message}
        context.user_data['transfer_state'] = 'awaiting_amount'
        
        action = "send to" if state == 'awaiting_recipient' else "request from"
        await update.message.reply_text(
            f"✅ Phone number: {format_phone_number(message)}\n\n"
            f"💰 Enter the amount to {action} this user (in USD):\n"
            "Example: 50.00\n\n"
            "Type /cancel to cancel"
        )
        
    elif state == 'awaiting_amount':
        try:
            amount = float(message)
            if amount <= 0:
                raise ValueError("Amount must be positive")
            if amount > 1000:  # Example limit
                raise ValueError("Amount exceeds limit")
                
            transfer_data = context.user_data.get('transfer_data', {})
            transfer_data['amount'] = amount
            
            # Create confirmation message
            action = "send" if 'awaiting_recipient' in context.user_data.get('transfer_state', '') else "request"
            preposition = "to" if action == "send" else "from"
            phone = transfer_data.get('phone', 'Unknown')
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_{action}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel_transfer")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🔍 *Review {action.title()} Money*\n\n"
                f"Amount: ${amount:,.2f} USD\n"
                f"Phone: {format_phone_number(phone)}\n\n"
                "Please confirm this transaction:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            context.user_data['transfer_state'] = 'awaiting_confirmation'
            
        except ValueError as e:
            await update.message.reply_text(
                "❌ Invalid amount!\n"
                "Please enter a valid number (e.g., 50.00)\n"
                "Maximum transfer amount: $1,000\n\n"
                "Type /cancel to cancel"
            )
            return

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages"""
    try:
        # Handle web app data
        if update.effective_message.web_app_data:
            await webapp_handler(update, context)
            return
            
        # Handle regular messages
        if context.user_data.get('awaiting_phone', False):
            context.user_data['awaiting_phone'] = False
            await verify_phone(update, context)
        elif context.user_data.get('awaiting_otp', False):
            await verify_otp_handler(update, context)
        elif context.user_data.get('transfer_state'):
            await handle_transfer(update, context)
        else:
            # Handle unknown messages
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
        
        # Cleanup expired OTPs
        expired_otps = [
            user_id for user_id, data in otp_store.items()
            if current_time > data['expiry']
        ]
        for user_id in expired_otps:
            del otp_store[user_id]
            
        # Cleanup expired rate limits (older than 1 hour)
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

        application.add_handler(CommandHandler("transfer", transfer_command))

        # Initialize job queue
        job_queue = application.job_queue

    """Start the bot"""
    try:
        # Initialize bot with deploy token
        application = (
            ApplicationBuilder()
            .token(deploy_token)
            .build()
        )
        logger.info("Bot initialized successfully")

        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))
        
        async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            """Handle button clicks"""
            query = update.callback_query
            await query.answer()
            # Add your button handling logic here
            await query.edit_message_text(text=f"Selected option: {query.data}")
        application.add_handler(CommandHandler("profile", profile_command))
        application.add_handler(CommandHandler("cancel", cancel_command))
        application.add_handler(CommandHandler("balance", balance_command))
        application.add_handler(CommandHandler("transfer", transfer))
        application.add_handler(CommandHandler("help", help_command))
        
        # Add callback and message handlers
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

        # Add periodic cleanup job (run every 15 minutes)
        job_queue = application.job_queue
        job_queue.run_repeating(cleanup_expired_data, interval=900, first=10)
        application.run_polling(allowed_updates=[
            "message", "edited_message", "channel_post", "edited_channel_post",
            "inline_query", "chosen_inline_result", "callback_query", "shipping_query",
            "pre_checkout_query", "poll", "poll_answer", "my_chat_member",
            "chat_member", "chat_join_request"
        ])

        # Start the bot
        logger.info("Starting bot polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Error running bot: {str(e)}")
        raise

if __name__ == "__main__":
    main()
