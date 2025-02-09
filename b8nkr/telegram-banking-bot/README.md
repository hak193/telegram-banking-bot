# B8NKR Telegram Banking Bot

A secure Telegram bot for banking operations with OTP verification via Twilio SMS.

## Features

- 🔐 Secure phone number verification with OTP
- 💰 Check account balance
- 📤 Send and request money
- 📱 User profile management
- 🌐 Web app integration
- 📊 Transaction history
- ⚡ Rate limiting and security measures

## Setups

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your credentials:
```env
TELEGRAM_TOKEN=your_telegram_bot_token
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone_number
WEBAPP_URL=your_webapp_url
```

3. Run the bot:
```bash
python bot.py
```

## Security Features

- 🔒 Cryptographically secure OTP generation
- ⏱️ OTP expiry after 5 minutes
- 🛡️ Rate limiting for OTP requests and verification attempts
- 🔍 Phone number validation and formatting
- 🧹 Automatic cleanup of expired data
- 🔐 Secure web app data validation

## Commands

- `/start` - Begin verification process
- `/menu` - Show main menu
- `/profile` - View your profile
- `/balance` - Check your balance
- `/transfer` - Send or request money
- `/history` - View transaction history
- `/cancel` - Cancel current operation
- `/help` - Show help message

## Development

The bot is built with:
- python-telegram-bot for Telegram API integration
- Twilio for SMS OTP delivery
- Flask for web app integration
- Cryptography for secure OTP generation
- Python-dotenv for environment management

## Rate Limits

- OTP Requests: 3 requests per 5 minutes
- OTP Verification: 5 attempts per 5 minutes
- Maximum transfer amount: $1,000 per transaction

## Security Best Practices

1. Never share your OTP with anyone
2. Keep your phone number up to date
3. Use strong passwords for your account
4. Monitor your transaction history regularly
5. Contact support if you notice suspicious activity

## Error Handling

The bot includes comprehensive error handling:
- Invalid phone number format detection
- OTP validation and expiry checks
- Rate limit monitoring
- Transaction validation
- Secure session management

## Logging

All important events are logged with timestamps:
- OTP generation and verification attempts
- User verification status
- Money transfers and requests
- Rate limit triggers
- Error occurrences

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
