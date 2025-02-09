import json
import os
import logging
from flask import Flask, render_template, jsonify, request, Response
from datetime import datetime
import subprocess
import psutil

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Bot process management
bot_process = None


def get_bot_status():
    global bot_process
    if bot_process is None:
        return False
    return bot_process.poll() is None


def start_bot():
    global bot_process
    try:
        bot_process = subprocess.Popen(["python", "bot.py"])
        logger.info("Bot started")
        return True
    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}")
        return False


def stop_bot():
    global bot_process
    if bot_process:
        try:
            process = psutil.Process(bot_process.pid)
            for proc in process.children(recursive=True):
                proc.terminate()
            process.terminate()
            bot_process = None
            logger.info("Bot stopped")
            return True
        except Exception as e:
            logger.error(f"Error stopping bot: {str(e)}")
            return False
    return True


# Routes
@app.route("/")
def index():
    # Mock data for demonstration
    data = {
        "bot_running": get_bot_status(),
        "total_users": 150,
        "commands_today": 75,
        "active_sessions": 12,
        "recent_activities": [
            {"time": "2 mins ago", "user": "User123", "action": "Checked balance"},
            {"time": "5 mins ago", "user": "User456", "action": "Made transfer"},
            {"time": "10 mins ago", "user": "User789", "action": "Requested help"},
        ],
    }
    return render_template("index.html", **data)


@app.route("/toggle_bot", methods=["POST"])
def toggle_bot():
    current_status = get_bot_status()
    success = stop_bot() if current_status else start_bot()
    new_status = get_bot_status()

    return jsonify(
        {"success": success, "status": "running" if new_status else "stopped"}
    )


@app.route("/command_stats")
def command_stats():
    # Mock data for demonstration
    return jsonify(
        {"labels": ["Balance", "Transfer", "Help", "Call"], "values": [45, 30, 20, 5]}
    )


@app.route("/logs")
def logs():
    return render_template("logs.html")


@app.route("/commands")
def commands():
    return render_template("commands.html")


@app.route("/config")
def config():
    try:
        with open("bot.py", "r") as f:
            config_data = {
                "telegram_token": "7225913890:AAHfvAAeqYbc-0wIsxBFAqgeFHJ5G6AH24w",
                "twilio_account_sid": "ACd92d35abb342c43469a7211c175e19c4",
                "twilio_auth_token": "d852ee26fd60230e17f8ca6f4b372612",
                "twilio_phone_number": "+18885752860",
            }
    except Exception as e:
        logger.error(f"Error reading config: {str(e)}")
        config_data = {}

    return render_template("config.html", config=config_data)


@app.route("/save_config", methods=["POST"])
def save_config():
    try:
        config_data = {
            "telegram_token": request.form.get("telegram_token"),
            "twilio_account_sid": request.form.get("twilio_account_sid"),
            "twilio_auth_token": request.form.get("twilio_auth_token"),
            "twilio_phone_number": request.form.get("twilio_phone_number"),
        }

        # Update bot.py with new configuration
        with open("bot.py", "r") as f:
            content = f.read()

        # Update tokens in content
        content = content.replace(
            "7225913890:AAHfvAAeqYbc-0wIsxBFAqgeFHJ5G6AH24w",
            config_data["telegram_token"],
        )
        content = content.replace(
            "ACd92d35abb342c43469a7211c175e19c4", config_data["twilio_account_sid"]
        )
        content = content.replace(
            "d852ee26fd60230e17f8ca6f4b372612", config_data["twilio_auth_token"]
        )
        content = content.replace("+18885752860", config_data["twilio_phone_number"])

        with open("bot.py", "w") as f:
            f.write(content)

        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error saving config: {str(e)}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/log_stream")
def log_stream():
    def generate():
        with open("bot.log", "r") as f:
            while True:
                line = f.readline()
                if not line:
                    continue
                yield f"data: {line}\n\n"

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
