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
CREATE TABLE IF NOT EXISTS warns (
user_id INTEGER,
chat_id INTEGER,
count INTEGER
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
chat_id INTEGER PRIMARY KEY,
lock_links INTEGER DEFAULT 1,
welcome TEXT DEFAULT ''
)
""")

db.commit()

# ======================
# إعدادات افتراضية
# ======================
def init_chat(chat_id):
    cur.execute("SELECT chat_id FROM settings WHERE chat_id=?", (chat_id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO settings VALUES (?, 1, '')", (chat_id,))
        db.commit()

# ======================
# الحظر
# ======================
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user.id
        await context.bot.ban_chat_member(update.effective_chat.id, user)

# ======================
# الطرد
# ======================
async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user.id
        await context.bot.ban_chat_member(update.effective_chat.id, user)
        await context.bot.unban_chat_member(update.effective_chat.id, user)

# ======================
# القيد
# ======================
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
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
    cur.execute("SELECT count FROM warns WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    data = cur.fetchone()

    if data:
        count = data[0] + 1
        cur.execute("UPDATE warns SET count=? WHERE user_id=? AND chat_id=?", (count, user_id, chat_id))
    else:
        count = 1
        cur.execute("INSERT INTO warns VALUES (?, ?, ?)", (user_id, chat_id, count))

    db.commit()
    return count

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user.id
        chat = update.effective_chat.id

        count = add_warn(user, chat)

        if count >= 3:
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

# ======================
# فلترة
# ======================
async def filter_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        return

    chat = update.effective_chat.id
    text = update.message.text

    cur.execute("SELECT word FROM banned_words WHERE chat_id=?", (chat,))
    words = cur.fetchall()

    for w in words:
        if w[0] in text:
            await update.message.delete()

# ======================
# إعدادات
# ======================
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat.id
    init_chat(chat)

    cur.execute("SELECT lock_links, welcome FROM settings WHERE chat_id=?", (chat,))
    data = cur.fetchone()

    msg = f"""
⚙️ الإعدادات:

🔗 الروابط: {'مقفولة' if data[0] else 'مفتوحة'}
👋 الترحيب: {data[1] if data[1] else 'غير موجود'}
"""
    await update.message.reply_text(msg)

# ======================
# قفل الروابط
# ======================
async def link_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        return

    chat = update.effective_chat.id
    init_chat(chat)

    cur.execute("SELECT lock_links FROM settings WHERE chat_id=?", (chat,))
    data = cur.fetchone()

    if data and data[0] == 1:
        if "http" in update.message.text or "t.me" in update.message.text:
            await update.message.delete()

# ======================
# الترحيب
# ======================
async def welcome_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    chat = update.effective_chat.id

    cur.execute("UPDATE settings SET welcome=? WHERE chat_id=?", (text, chat))
    db.commit()

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        cur.execute("SELECT welcome FROM settings WHERE chat_id=?", (update.effective_chat.id,))
        data = cur.fetchone()

        if data and data[0]:
            msg = data[0].replace("{الاسم}", user.first_name)
            await update.message.reply_text(msg)

# ======================
# تشغيل
# ======================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("حظر", ban))
app.add_handler(CommandHandler("طرد", kick))
app.add_handler(CommandHandler("قيد", mute))

app.add_handler(CommandHandler("انذار", warn))
app.add_handler(CommandHandler("منع", block))

app.add_handler(CommandHandler("الإعدادات", settings))
app.add_handler(CommandHandler("اضف_ترحيب", welcome_set))

app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, filter_words))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, link_filter))

print("Bot Running 🔥")
app.run_polling()