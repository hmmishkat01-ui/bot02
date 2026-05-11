from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
  app.run(host='0.0.0.0',port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

import os
import telebot
from telebot import types
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from dotenv import load_dotenv

# .env ফাইল লোড করা
load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
BIKASH_NO = os.getenv('BIKASH_NO')
GROUP_LINK = os.getenv('GROUP_LINK')
COURSE_FEE = int(os.getenv('COURSE_FEE', 2500))
COUPON_CODE = os.getenv('COUPON_CODE', 'FREE500')
DISCOUNT_AMOUNT = int(os.getenv('DISCOUNT_AMOUNT', 500))

bot = telebot.TeleBot(TOKEN)

# গুগল শিট কানেকশন
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open("Course_Admission").sheet1
    print("✅ Google Sheet Connected!")
except Exception as e:
    print(f"❌ Sheet Error: {e}")

user_state = {}

# --- ভর্তি সম্পন্ন করার ফাংশন ---
def finalize_admission(message, student_id):
    try:
        if ',' not in message.text:
            bot.send_message(ADMIN_ID, "⚠️ ভুল ফরম্যাট! দয়া করে Roll,Reg এভাবে দিন। (যেমন: 101,5005)")
            msg = bot.send_message(ADMIN_ID, "আবার লিখুন:")
            bot.register_next_step_handler(msg, finalize_admission, student_id)
            return

        roll, reg = message.text.split(',')
        data = user_state.get(student_id)
        approve_time = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        
        # গুগল শিটে ডেটা জমা
        sheet.append_row([
            data['admit_time'], student_id, data['name'], data['phone'], 
            data['coupon'], data['paid_amount'], data['sender_num'], 
            roll.strip(), reg.strip(), data['photo_id'], "Approved", approve_time
        ])
        
        # স্টুডেন্টের জন্য সাকসেস মেসেজ
        success_msg = (
            "🎊 *অভিনন্দন! আপনার ভর্তি সফল হয়েছে* 🎊\n\n"
            "আপনার পেমেন্ট ভেরিফাই করা হয়েছে। আপনার তথ্যসমূহ নিচে দেওয়া হলো:\n\n"
            f"🔢 *রোল নাম্বার:* `{roll.strip()}`\n"
            f"🆔 *রেজিস্ট্রেশন:* `{reg.strip()}`\n\n"
            "নিচের বাটনে ক্লিক করে দ্রুত আমাদের সিক্রেট গ্রুপে যুক্ত হয়ে যান। 👇"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔗 জয়েন করুন (Secret Group)", url=GROUP_LINK))
        
        bot.send_message(student_id, success_msg, reply_markup=markup, parse_mode='Markdown')
        bot.send_message(ADMIN_ID, f"✅ {data['name']} এর ভর্তি সম্পন্ন হয়েছে।")
        
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ সমস্যা হয়েছে: {e}")

# --- ইউজার ফ্লো (Text Changes) ---

@bot.message_handler(commands=['start'])
def start(message):
    # আপনার চাহিদা অনুযায়ী পরিবর্তন করা হয়েছে
    welcome_msg = (
        "🎓 *Sky IT Institute*-তে আপনাকে স্বাগতম!\n\n"
        "AI automation কোর্সে এডমিশন নিতে আপনার *পূর্ণ নাম* লিখে মেসেজ দিন:"
    )
    bot.send_message(message.chat.id, welcome_msg, parse_mode='Markdown')
    user_state[message.chat.id] = {'step': 'NAME'}

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get('step') == 'NAME')
def get_name(message):
    user_state[message.chat.id]['name'] = message.text
    user_state[message.chat.id]['step'] = 'COUPON'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("কুপন নেই")
    bot.send_message(message.chat.id, "🎟 আপনার কি কোনো *কুপন কোড* আছে? থাকলে লিখুন, না থাকলে নিচের বাটনে ক্লিক করুন:", reply_markup=markup)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get('step') == 'COUPON')
def get_coupon(message):
    fee = COURSE_FEE
    coupon = "None"
    if message.text == COUPON_CODE:
        fee = COURSE_FEE - DISCOUNT_AMOUNT
        coupon = COUPON_CODE
        bot.send_message(message.chat.id, f"✅ কুপন সফল! বর্তমান কোর্স ফি: `{fee}` টাকা।")
    
    user_state[message.chat.id].update({'final_fee': fee, 'coupon': coupon, 'step': 'PHONE'})
    bot.send_message(message.chat.id, "📱 আপনার সচল *মোবাইল নাম্বারটি* দিন:", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get('step') == 'PHONE')
def get_phone(message):
    user_state[message.chat.id]['phone'] = message.text
    user_state[message.chat.id]['step'] = 'PHOTO'
    fee = user_state[message.chat.id]['final_fee']
    msg = (
        f"💰 আপনার কোর্স ফি: `{fee}` টাকা।\n"
        f"বিকাশ (Personal): `{BIKASH_NO}`\n\n"
        "টাকা পাঠানোর পর পেমেন্টের একটি *স্ক্রিনশট* দিন।"
    )
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(content_types=['photo'], func=lambda m: user_state.get(m.chat.id, {}).get('step') == 'PHOTO')
def get_photo(message):
    user_state[message.chat.id]['photo_id'] = message.photo[-1].file_id
    user_state[message.chat.id]['step'] = 'PAY_INFO'
    bot.send_message(message.chat.id, "💵 আপনি কত টাকা পাঠিয়েছেন এবং কোন নাম্বার থেকে পাঠিয়েছেন তা লিখে দিন।\n\nউদাহরণ: *2500, 017XXXXXXXX*", parse_mode='Markdown')

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get('step') == 'PAY_INFO')
def get_pay_info(message):
    cid = message.chat.id
    try:
        amount, sender = message.text.split(',')
        user_state[cid].update({
            'paid_amount': amount.strip(),
            'sender_num': sender.strip(),
            'admit_time': datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        })
        bot.send_message(cid, "⏳ ধন্যবাদ! আপনার তথ্যগুলো জমা হয়েছে। এডমিন চেক করে এপ্রুভ করলে আপনি কনফার্মেশন পাবেন।")
        
        # এডমিন নোটিফিকেশন
        data = user_state[cid]
        admin_txt = (
            f"🔔 *নতুন ভর্তি রিকোয়েস্ট!*\n👤 নাম: {data['name']}\n📞 ফোন: {data['phone']}\n"
            f"💵 পেমেন্ট: {data['paid_amount']} টাকা\n🔢 প্রেরক: {data['sender_num']}\n⏰ সময়: {data['admit_time']}"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{cid}"))
        markup.add(types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{cid}"))
        bot.send_photo(ADMIN_ID, data['photo_id'], caption=admin_txt, reply_markup=markup, parse_mode='Markdown')
    except:
        bot.send_message(cid, "⚠️ দয়া করে সঠিক ফরম্যাটে লিখুন। উদাহরণ: 2500, 01700000000")

@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_') or call.data.startswith('reject_'))
def admin_action(call):
    sid = int(call.data.split('_')[1])
    bot.answer_callback_query(call.id)
    if call.data.startswith('approve'):
        m = bot.send_message(ADMIN_ID, f"ইউজার {sid}-এর রোল ও রেজি দিন (Roll,Reg):")
        bot.register_next_step_handler(m, finalize_admission, sid)
    else:
        bot.send_message(sid, "❌ আপনার পেমেন্ট তথ্যটি সঠিক নয়।")

if __name__ == "__main__":
    print("----------------------------------------")
    print("🚀 SkillVant IT Academy Bot is LIVE!")
    print("----------------------------------------")
    try: bot.send_message(ADMIN_ID, "✅ Bot Started Successfully!")
    except: pass
    bot.polling(none_stop=True)
