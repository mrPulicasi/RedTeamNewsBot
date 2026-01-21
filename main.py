import os
import feedparser
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")  # set env variable
TIMEZONE = timezone("Asia/Kolkata")

RSS_FEEDS = [
    "https://feeds.feedburner.com/TheHackersNews",
    "https://www.bleepingcomputer.com/feed/",
    "https://krebsonsecurity.com/feed/"
]

# ================= DATABASE =================
conn = sqlite3.connect("news.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS posted (
    link TEXT PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS groups (
    chat_id INTEGER PRIMARY KEY
)
""")

conn.commit()

# ================= DATABASE FUNCTIONS =================
def is_duplicate(link):
    cursor.execute("SELECT 1 FROM posted WHERE link=?", (link,))
    return cursor.fetchone() is not None

def save_link(link):
    cursor.execute("INSERT OR IGNORE INTO posted VALUES (?)", (link,))
    conn.commit()

def save_group(chat_id):
    cursor.execute("INSERT OR IGNORE INTO groups VALUES (?)", (chat_id,))
    conn.commit()

def get_all_groups():
    cursor.execute("SELECT chat_id FROM groups")
    return [row[0] for row in cursor.fetchall()]

# ================= NEWS FETCH =================
def fetch_news():
    results = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]:
            if not is_duplicate(entry.link):
                results.append(entry)
                save_link(entry.link)
    return results

# ================= POST NEWS =================
async def post_news(context: ContextTypes.DEFAULT_TYPE):
    groups = get_all_groups()
    if not groups:
        print("No groups found")
        return

    news = fetch_news()

    if not news:
        msg = "🛡 No major cyber security updates right now.\nStay alert!"
    else:
        msg = "🚨 *Cyber Security Updates* 🚨\n\n"
        for n in news:
            msg += f"🔹 *{n.title}*\n👉 {n.link}\n\n"
        msg += "🛡 Stay Safe | #CyberSecurity"

    for gid in groups:
        try:
            await context.bot.send_message(
                chat_id=gid,
                text=msg,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        except Exception as e:
            print(f"Failed to send to {gid}: {e}")

    print("Posted:", datetime.now(TIMEZONE))

# ================= COMMAND =================
async def postnow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await post_news(context)
    await update.message.reply_text("✅ News posted to all groups.")

# ================= GROUP TRACKER =================
async def track_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat and chat.type in ["group", "supergroup"]:
        save_group(chat.id)

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("postnow", postnow))
    app.add_handler(MessageHandler(filters.ALL, track_groups))

    scheduler = BackgroundScheduler(timezone=TIMEZONE)

    scheduler.add_job(
        lambda: app.create_task(post_news(app.bot_data)),
        "cron", hour=9, minute=0
    )
    scheduler.add_job(
        lambda: app.create_task(post_news(app.bot_data)),
        "cron", hour=14, minute=0
    )
    scheduler.add_job(
        lambda: app.create_task(post_news(app.bot_data)),
        "cron", hour=21, minute=0
    )

    scheduler.start()

    print("🔥 Cyber Security Multi-Group Bot Started")
    app.run_polling()

if __name__ == "__main__":
    main()
