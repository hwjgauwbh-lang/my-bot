import logging
import sqlite3
from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = "PUT_YOUR_TOKEN_HERE"

logging.basicConfig(level=logging.INFO)

# ======================
# قاعدة البيانات
# ======================
db = sqlite3.connect("bot.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
user_id INTEGER,
chat_id INTEGER,
warns INTEGER DEFAULT 0,
role TEXT DEFAULT 'member'
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS banned_words (
chat_id INTEGER,
word TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS settings (
chat_id INTEGER,
welcome TEXT
)
""")

db.commit()

# ======================
# صلاحيات (رتب)
# ======================
def get_role(user_id, chat_id):
    cur.execute("SELECT role FROM users WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    data = cur.fetchone()
    return data[0] if data else "member"

def set_role(user_id, chat_id, role):
    cur.execute("INSERT OR REPLACE INTO users VALUES (?, ?, 0, ?)", (user_id, chat_id, role))
    db.commit()

# ======================
# الحظر
# ======================
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return

    await context.bot.ban_chat_member(
        update.effective_chat.id,
        update.message.reply_to_message.from_user.id
    )

# ======================
# الطرد
# ======================
async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return

    user = update.message.reply_to_message.from_user.id
    await context.bot.ban_chat_member(update.effective_chat.id, user)
    await context.bot.unban_chat_member(update.effective_chat.id, user)

# ======================
# القيد
# ======================
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return

    user = update.message.reply_to_message.from_user.id

    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user,
        ChatPermissions(can_send_messages=False)
    )

# ======================
# الإنذارات
# ======================
def add_warn(user_id, chat_id):
    cur.execute("SELECT warns FROM users WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    data = cur.fetchone()

    if data:
        warns = data[0] + 1
        cur.execute("UPDATE users SET warns=? WHERE user_id=? AND chat_id=?", (warns, user_id, chat_id))
    else:
        warns = 1
        cur.execute("INSERT INTO users VALUES (?, ?, ?, 'member')", (user_id, chat_id, warns))

    db.commit()
    return warns

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return

    user = update.message.reply_to_message.from_user.id
    chat = update.effective_chat.id

    warns = add_warn(user, chat)

    if warns >= 3:
        await context.bot.restrict_chat_member(
            chat,
            user,
            ChatPermissions(can_send_messages=False)
        )

# ======================
# منع كلمات
# ======================
async def block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    word = " ".join(context.args)
    cur.execute("INSERT INTO banned_words VALUES (?, ?)", (update.effective_chat.id, word))
    db.commit()

async def filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        return

    cur.execute("SELECT word FROM banned_words WHERE chat_id=?", (update.effective_chat.id,))
    words = cur.fetchall()

    for w in words:
        if w[0] in update.message.text:
            await update.message.delete()

# ======================
# ترحيب
# ======================
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        cur.execute("SELECT welcome FROM settings WHERE chat_id=?", (update.effective_chat.id,))
        data = cur.fetchone()

        if data:
            msg = data[0].replace("{الاسم}", user.first_name)
            await update.message.reply_text(msg)

async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    cur.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (update.effective_chat.id, text))
    db.commit()

# ======================
# رتب (مميز/مشرف/مدير)
# ======================
async def set_role_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return

    role = " ".join(context.args)
    user = update.message.reply_to_message.from_user.id

    set_role(user, update.effective_chat.id, role)

# ======================
# تشغيل
# ======================
app = ApplicationBuilder().token(TOKEN).build()

# أوامر عربية
app.add_handler(CommandHandler("حظر", ban))
app.add_handler(CommandHandler("طرد", kick))
app.add_handler(CommandHandler("قيد", mute))
app.add_handler(CommandHandler("انذار", warn))
app.add_handler(CommandHandler("منع", block))
app.add_handler(CommandHandler("اضف_ترحيب", set_welcome))
app.add_handler(CommandHandler("جعله", set_role_cmd))

app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, filter))

print("Bot Shield Pro Running 🔥")
app.run_polling()