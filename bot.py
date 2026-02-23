"""
bot.py
Telegram bot - Python port of the WhatsApp bot.

Requirements:
    pip install python-telegram-bot playwright
    playwright install chromium

Set your bot token in BOT_TOKEN below (or via environment variable).
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

#from pdf import register_pdf_handlers

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from attendance import (
    compare_attendance,
    format_attendance_full,
    format_attendance_short,
    format_low_attendance,
    get_emoji,
    to_short_name,
    total_percentage,
)
from browser import scrape_attendance
from verify import verify_login
from telegram import BotCommand
# ─── Config ──────────────────────────────────────────────────────────────────

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8563840316:AAGbQLOY7Lqg-FidoRc1vwuAQBr0ZMfC2KA")
USERS_FILE = Path(__file__).parent / "users.json"
POLL_INTERVAL_SECONDS = 30 * 60  # 30 minutes
COLLEGE_START_HOUR = 8
COLLEGE_END_HOUR = 18

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── User Store ──────────────────────────────────────────────────────────────

def load_users() -> dict:
    if not USERS_FILE.exists():
        return {}
    return json.loads(USERS_FILE.read_text())


def save_users(users: dict) -> None:
    USERS_FILE.write_text(json.dumps(users, indent=2))


# ─── Multi-step verify state ─────────────────────────────────────────────────

# chat_id (str) -> { "step": str, "username": str }
pending_verify: dict = {}

# ─── Helpers ─────────────────────────────────────────────────────────────────

def is_college_hours() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    #return True
    return COLLEGE_START_HOUR <= now.hour < COLLEGE_END_HOUR


def build_change_message(changes: list) -> str:
    lines = []
    for change in changes:
        subject = change['subject']
        c = change['current']
        short_name = to_short_name(subject)
        emoji = get_emoji(c['present'], c['total'])
        lines.append(f"{emoji} *{short_name}*")
    return "📢 *Absent marked!*\n\n" + '\n'.join(lines)


# ─── Command Handlers ─────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Welcome! Type /help to see available commands."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_markdown(
        "*📋 Available Commands:*\n\n"
        "/verify       → Register / re-register your ERP account\n"
        "/check        → Manually check attendance now\n"
        "/all          → Full attendance with complete subject names\n"
        "/low          → Show only subjects below 75%\n"
        "/pause        → Pause auto-notifications\n"
        "/resume       → Resume auto-notifications\n"
        "/unsubscribe  → Remove your account from the bot\n"
        "/help         → Show this message"
    )


async def cmd_verify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    pending_verify[chat_id] = {"step": "username"}
    await update.message.reply_markdown(
        "Let's get you set up! 👋\nPlease send your *ERP username* (email):"
    )


async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    users = load_users()
    if chat_id not in users:
        await update.message.reply_text("You're not registered yet. Use /verify to get started.")
        return

    user = users[chat_id]
    await update.message.reply_text("⏳ Checking for any attendance updates...")
    try:
        new_attendance = await scrape_attendance(user['username'], user['password'])
        changes = compare_attendance(user.get('lastAttendance', {}), new_attendance)

        if changes:
            change_msg = build_change_message(changes)
            await update.message.reply_markdown(change_msg)
            users[chat_id]['lastAttendance'] = new_attendance
            save_users(users)
        else:
            await update.message.reply_text("✅ No new attendance changes detected.")

    except Exception as e:
        logger.error(f"Error checking attendance for {chat_id}: {e}")
        await update.message.reply_text("❌ Could not fetch attendance. Try again later.")

async def cmd_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    users = load_users()
    if chat_id not in users:
        await update.message.reply_text("You're not registered yet. Use /verify to get started.")
        return

    user = users[chat_id]
    await update.message.reply_text("⏳ Fetching your attendance...")
    try:
        attendance = await scrape_attendance(user['username'], user['password'])
        users[chat_id]['lastAttendance'] = attendance
        save_users(users)
        await update.message.reply_markdown(format_attendance_short(attendance))
        await update.message.reply_text(f"📈 Overall: {total_percentage(attendance)}")
    except Exception as e:
        logger.error(f"Error fetching attendance for {chat_id}: {e}")
        await update.message.reply_text("❌ Could not fetch attendance. Try again later.")


async def cmd_low(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    users = load_users()
    if chat_id not in users:
        await update.message.reply_text("You're not registered yet. Use /verify to get started.")
        return

    user = users[chat_id]
    await update.message.reply_text("⏳ Fetching your attendance...")
    try:
        attendance = await scrape_attendance(user['username'], user['password'])
        users[chat_id]['lastAttendance'] = attendance
        save_users(users)
        low_msg = format_low_attendance(attendance)
        await update.message.reply_markdown(low_msg or "🎉 All subjects are above 75%!")
    except Exception as e:
        logger.error(f"Error fetching attendance for {chat_id}: {e}")
        await update.message.reply_text("❌ Could not fetch attendance. Try again later.")


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    users = load_users()
    if chat_id not in users:
        await update.message.reply_text("You're not registered yet. Use /verify to get started.")
        return
    users[chat_id]['notificationsEnabled'] = False
    save_users(users)
    await update.message.reply_text("🔕 Notifications paused. Use /resume to turn them back on.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    users = load_users()
    if chat_id not in users:
        await update.message.reply_text("You're not registered yet. Use /verify to get started.")
        return
    users[chat_id]['notificationsEnabled'] = True
    save_users(users)
    await update.message.reply_text("🔔 Notifications resumed!")


async def cmd_unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    users = load_users()
    if chat_id in users:
        del users[chat_id]
        save_users(users)
    await update.message.reply_text(
        "👋 You've been removed. Bye! Use /verify anytime to come back."
    )


# ─── Multi-step verify message handler ───────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    text = update.message.text.strip()

    if chat_id not in pending_verify:
        return  # Ignore unknown messages

    state = pending_verify[chat_id]

    if state['step'] == 'username':
        state['username'] = text
        state['step'] = 'password'
        await update.message.reply_markdown("Got it! Now send your *ERP password*:")
        return

    if state['step'] == 'password':
        password = text
        await update.message.reply_text("⏳ Verifying your credentials...")

        valid = await verify_login(state['username'], password)
        if not valid:
            await update.message.reply_text(
                "❌ Invalid username or password. Try /verify again."
            )
            del pending_verify[chat_id]
            return

        # Fetch initial attendance snapshot
        attendance = await scrape_attendance(state['username'], password)
        users = load_users()
        users[chat_id] = {
            'chat_id': chat_id,
            'username': state['username'],
            'password': password,  # Consider encrypting — see README
            'lastAttendance': attendance,
            'notificationsEnabled': True,
        }
        save_users(users)
        del pending_verify[chat_id]

        await update.message.reply_markdown(
            "✅ Verified and registered!\n\n"
            "Here's your current attendance:\n\n"
            + format_attendance_short(attendance)
            + "\n\nType /help to see available commands."
        )


# ─── Polling ─────────────────────────────────────────────────────────────────

async def poll_all_users(app: Application) -> None:
    if not is_college_hours():
        logger.info("[Poll] Outside college hours, skipping.")
        return

    users = load_users()
    for chat_id, user in users.items():
        if not user.get('notificationsEnabled', True):
            continue
        try:
            new_attendance = await scrape_attendance(user['username'], user['password'])
            changes = compare_attendance(user.get('lastAttendance', {}), new_attendance)

            if changes:
                change_msg = build_change_message(changes)
                await app.bot.send_message(
                    chat_id=int(chat_id),
                    text=change_msg,
                    parse_mode='Markdown',
                )
                users[chat_id]['lastAttendance'] = new_attendance
                save_users(users)
                logger.info(f"[Poll] Notified {chat_id} about {len(changes)} change(s).")
            else:
                logger.info(f"[Poll] No changes for {chat_id}.")
        except Exception as e:
            logger.error(f"[Poll] Error for {chat_id}: {e}")


async def poll_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await poll_all_users(context.application)


# ─── Main ─────────────────────────────────────────────────────────────────────
async def post_init(app: Application) -> None:
    await app.bot.set_my_commands([
        BotCommand("verify",      "Register / re-register your ERP account"),
        BotCommand("check",       "Check for new attendance updates"),
        BotCommand("all",         "Full attendance with complete subject names"),
        BotCommand("low",         "Show only subjects below 75%"),
        BotCommand("pause",       "Pause auto-notifications"),
        BotCommand("resume",      "Resume auto-notifications"),
        BotCommand("unsubscribe", "Remove your account from the bot"),
        BotCommand("help",        "Show available commands"),
        BotCommand("pdf",  "Start creating a PDF from images"),
        BotCommand("done", "Finish and generate the PDF"),
    ])


def main() -> None:
    
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("verify", cmd_verify))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("all", cmd_all))
    app.add_handler(CommandHandler("low", cmd_low))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("unsubscribe", cmd_unsubscribe))

    # Multi-step verify text handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    #register_pdf_handlers(app)
    # Polling job
    app.job_queue.run_repeating(poll_job, interval=POLL_INTERVAL_SECONDS, first=10)

    logger.info("Bot started!")
    app.run_polling()


if __name__ == "__main__":
    main()
