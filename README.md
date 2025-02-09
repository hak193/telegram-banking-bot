# B8NKR Telegram Banking Bot

A secure Telegram bot for banking operations with OTP verification via Twilio SMS.

## Features

- 🔐 Secure phone number verification with OTP
- 💰 Check account balance
- 📤 Send and request money
- 📱 User profile management
- 📊 Transaction history
- ⚡ Rate limiting and security measures

## Prerequisites

1. Python 3.8 or higher
2. A Telegram Bot Token (from [@BotFather](https://t.me/botfather))
3. Twilio Account (for SMS OTP)

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/telegram-banking-bot.git
cd telegram-banking-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and update with your credentials:
```bash
cp .env.example .env
```

4. Update the following variables in `.env`:
- `TELEGRAM_TOKEN`: Your Telegram bot token
- `TWILIO_ACCOUNT_SID`: Your Twilio Account SID
- `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token
- `TWILIO_PHONE_NUMBER`: Your Twilio phone number

## Running the Bot

```bash
python bot.py
```

## Security Features

- 🔒 Cryptographically secure OTP generation
- ⏱️ OTP expiry after 5 minutes
- 🛡️ Rate limiting for OTP requests (3 per 5 minutes)
- 🔍 Rate limiting for verification attempts (5 per 5 minutes)
- 🧹 Automatic cleanup of expired data
- 📱 Phone number validation and formatting

## Commands

- `/start` - Begin verification process
- `/menu` - Show main menu
- `/profile` - View your profile
- `/balance` - Check your balance
- `/transfer` - Send or request money
- `/history` - View transaction history
- `/cancel` - Cancel current operation
- `/help` - Show help message

## Rate Limits

- OTP Requests: 3 requests per 5 minutes
- OTP Verification: 5 attempts per 5 minutes
- Maximum Transfer: $1,000 per transaction

## Error Handling

The bot includes comprehensive error handling:
- Invalid phone number detection
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

## Security Best Practices

1. Never share your OTP with anyone
2. Keep your phone number up to date
3. Monitor your transaction history regularly
4. Contact support if you notice suspicious activity
5. Use strong passwords for your account

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
