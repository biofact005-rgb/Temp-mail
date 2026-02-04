import telebot
import requests
import random
import string
import time
import logging
import json
import os
import re
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
  app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Tumhara purana code yahan se start hoga ---
# ... (Telebot wala saara code)
# ---------------- CONFIGURATION ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")         # <--- Apna Token daalo
MUST_JOIN = "@errorkid_05"   # <--- Channel Username
ADMIN_ID = os.getenv("ADMIN_ID")                 # <--- Apna Khud ka Telegram ID daalo (Broadcast ke liye)
COOLDOWN_SECONDS = 60

API_BASE = "https://api.mail.tm"
DB_FILE = "users_db.json"

# Logging Setup
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

bot = telebot.TeleBot(BOT_TOKEN)

# ---------------- DATABASE SYSTEM (JSON) ----------------
# Ye function data ko file me save karega taaki restart par data na ude

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Database load karo start hote hi
user_data = load_db()

# ---------------- HELPER FUNCTIONS ----------------

def clean_html(raw_html):
    """HTML tags hatakar saaf text banata hai"""
    if not raw_html: return "No Content"
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.strip()

def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(MUST_JOIN, user_id).status
        if status in ['member', 'administrator', 'creator']:
            return True
    except:
        return False # Agar admin nahi banaya bot ko
    return False

def generate_random_string(length=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def create_account():
    password = generate_random_string(12)
    try:
        domain_resp = requests.get(f"{API_BASE}/domains")
        if domain_resp.status_code == 200:
            domain = domain_resp.json()['hydra:member'][0]['domain']
            username = generate_random_string(10) + "@" + domain
        else:
            return None

        payload = {"address": username, "password": password}
        resp = requests.post(f"{API_BASE}/accounts", json=payload)

        if resp.status_code == 201:
            token_resp = requests.post(f"{API_BASE}/token", json=payload)
            if token_resp.status_code == 200:
                token = token_resp.json()['token']
                return {'email': username, 'token': token, 'created_at': time.time()}
    except Exception as e:
        logging.error(f"Account Create Error: {e}")
    return None

def get_messages(token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(f"{API_BASE}/messages", headers=headers)
        return resp.json()['hydra:member']
    except:
        return []

def get_msg_content(token, msg_id):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(f"{API_BASE}/messages/{msg_id}", headers=headers)
        return resp.json()
    except:
        return None

#-------------- ADMIN COMMANDS ----------------

@bot.message_handler(commands=['broadcast'])
def send_broadcast(message):
    # Sirf Admin use kar sakta hai
    if message.from_user.id != ADMIN_ID:
        return

    msg_text = message.text.replace("/broadcast", "").strip()
    if not msg_text:
        bot.reply_to(message, "❌ Message to likho! Example: `/broadcast Hello Users`")
        return

    sent = 0
    failed = 0
    bot.reply_to(message, f"📢 Broadcasting to {len(user_data)} users...")

    for uid in list(user_data.keys()):
        try:
            bot.send_message(uid, f"📢 **Announcement:**\n\n{msg_text}", parse_mode="Markdown")
            sent += 1
            time.sleep(0.1) # Flood wait se bachne ke liye
        except:
            failed += 1
            # Optional: Remove user if blocked
            # del user_data[uid]

    bot.reply_to(message, f"✅ Broadcast Complete!\nSent: {sent}\nFailed: {failed}")

# ---------------- USER HANDLERS ----------------

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = str(message.chat.id) # JSON keys strings hoti hain

    # 1. Verification
    if not is_subscribed(int(user_id)):
        text = "🚫 **Access Locked!**\n\nJoin our channel to unlock this premium bot."
        markup = InlineKeyboardMarkup()
        btn_join = InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{MUST_JOIN.replace('@', '')}")
        btn_try = InlineKeyboardButton("🔄 Verify Join", callback_data="check_join")
        markup.add(btn_join)
        markup.add(btn_try)
        bot.send_message(user_id, text, parse_mode="Markdown", reply_markup=markup)
        return

    # 2. Main Menu
    show_main_menu(message)

def show_main_menu(message):
    user_id = str(message.chat.id)

    # Agar user ke paas pehle se email hai to wo dikhao
    if user_id in user_data:
        saved_email = user_data[user_id]['email']
        text = (
            f"👋 Welcome back!\n\n"
            f"📧 **Active Email:**\n`{saved_email}`\n\n"
            f"Niche button se inbox check karein."
        )
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("📩 Inbox", callback_data="check_inbox"),
                   InlineKeyboardButton("🔄 Refresh", callback_data="refresh_menu"))
        markup.row(InlineKeyboardButton("🗑️ Delete & New", callback_data="gen_email"))
    else:
        text = "👋 **Welcome!**\⚠️ Disclaimer: This bot is for educational purposes only. Do not use temporary emails for illegal activities. Developer is not responsible for misuse.."
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✨ Generate Email", callback_data="gen_email"))

    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = str(call.message.chat.id)
    chat_id = call.message.chat.id

    # --- JOIN CHECK ---
    if call.data == "check_join":
        if is_subscribed(chat_id):
            bot.delete_message(chat_id, call.message.message_id)
            bot.answer_callback_query(call.id, "✅ Verified!")
            show_main_menu(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ Not Joined Yet!", show_alert=True)
        return

    # --- GENERATE EMAIL ---
    if call.data == "gen_email":
        current_time = time.time()

        # Cooldown Check
        if user_id in user_data:
            last_gen = user_data[user_id].get('created_at', 0)
            if current_time - last_gen < COOLDOWN_SECONDS:
                wait = int(COOLDOWN_SECONDS - (current_time - last_gen))
                bot.answer_callback_query(call.id, f"⏳ Wait {wait}s more!", show_alert=True)
                return

        bot.answer_callback_query(call.id, "⚙️ Generating...")
        acc = create_account()

        if acc:
            user_data[user_id] = acc
            save_db(user_data) # <--- DATA SAVE TO FILE

            text = f"✅ **New Email Created:**\n\n`{acc['email']}`\n\n(Tap to copy)"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("📩 Check Inbox", callback_data="check_inbox"),
                       InlineKeyboardButton("🔄 Refresh", callback_data="refresh_menu"))
            markup.row(InlineKeyboardButton("🗑️ Delete & New", callback_data="gen_email"))

            try:
                bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
            except:
                bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
        else:
            bot.answer_callback_query(call.id, "Error connecting to server.", show_alert=True)

    # --- REFRESH MENU ---
    elif call.data == "refresh_menu":
        bot.delete_message(chat_id, call.message.message_id)
        show_main_menu(call.message)

    # --- CHECK INBOX ---
    elif call.data == "check_inbox":
        if user_id not in user_data:
            bot.answer_callback_query(call.id, "⚠️ No active email.", show_alert=True)
            return

        token = user_data[user_id]['token']
        msgs = get_messages(token)

        if not msgs:
            bot.answer_callback_query(call.id, "📭 Inbox Empty", show_alert=False)
        else:
            bot.answer_callback_query(call.id, f"📬 Found {len(msgs)} Emails!")

            for m in msgs:
                full = get_msg_content(token, m['id'])
                if full:
                    sender = full.get('from', {}).get('address', 'Unknown')
                    subject = full.get('subject', 'No Subject')

                    # HTML Cleaning Magic
                    raw_body = full.get('text') or full.get('intro') or "HTML Content"
                    clean_body = clean_html(raw_body)

                    final_msg = (
                        f"📨 **NEW EMAIL**\n"
                        f"👤 **From:** `{sender}`\n"
                        f"📌 **Subject:** {subject}\n"
                        f"----------------------------\n"
                        f"{clean_body[:900]}\n"
                        f"----------------------------"
                    )
                    bot.send_message(chat_id, final_msg, parse_mode="Markdown")



if __name__ == "__main__":
    keep_alive() # Flask start karega
    print("🔥 Bot is running...")
    bot.infinity_polling()
