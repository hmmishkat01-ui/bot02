import os
import telebot
from telebot import types
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# সার্ভারকে সজাগ রাখার জন্য Flask
app = Flask('')
@app.route('/')
def home(): return "Sky IT Academy Bot is Running!"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive(): Thread(target=run).start()

load_dotenv()
bot = telebot.TeleBot(os.getenv('BOT_TOKEN'))
ADMIN_ID = int(os.getenv('ADMIN_ID'))

# গুগল শিট কানেকশন
global sheet
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open("Course_Admission").sheet1
    print("✅ Google Sheet Connected!")
except Exception as e:
    print(f"❌ Sheet Error: {e}")
    sheet = None

user_state = {}

# --- মেইন ফাংশনসমূহ ---

@bot.message_handler(commands=['start'])
def start(message):
    welcome_msg = (
        "🎓 *Sky IT Institute*-তে আপনাকে স্বাগতম!\n\n"
        "AI Automation মাস্টারক্লাসে ভর্তি হতে আপনার *পূর্ণ নাম* লিখে মেসেজ দিন:"
    )
    bot.send_message(message.chat.id, welcome_msg, parse_mode='Markdown')
    user_state[message.chat.id] = {'step': 'NAME'}

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get('step') == 'NAME')
def get_name(message):
    user_state[message.chat.id]['name'] = message.text
    user_state[message.chat.id]['step'] = 'EMAIL' # এই ধাপে এখন ইমেল চাইবে
    bot.send_message(message.chat.id, "📧 আপনার সচল *ইমেল এড্রেসটি* লিখুন:")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get('step') == 'EMAIL')
def get_email(message):
    if "@" not in message.text or "." not in message.text:
        bot.send_message(message.chat.id, "⚠️ দয়া করে একটি সঠিক ইমেল এড্রেস দিন:")
        return
    
    user_state[message.chat.id]['email'] = message.text
    user_state[message.chat.id]['step'] = 'PHONE'
    bot.send_message(message.chat.id, "📱 আপনার *মোবাইল নাম্বারটি* দিন:")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get('step') == 'PHONE')
def get_phone(message):
    user_state[message.chat.id]['phone'] = message.text
    user_state[message.chat.id]['step'] = 'PHOTO'
    msg = (
        f"💰 কোর্স ফি: `{os.getenv('COURSE_FEE')}` টাকা।\n"
        f"বিকাশ (Personal): `{os.getenv('BIKASH_NO')}`\n\n"
        "টাকা পাঠানোর পর পেমেন্টের একটি *স্ক্রিনশট* এখানে দিন।"
    )
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(content_types=['photo'], func=lambda m: user_state.get(m.chat.id, {}).get('step') == 'PHOTO')
def get_photo(message):
    user_state[message.chat.id]['photo_id'] = message.photo[-1].file_id
    user_state[message.chat.id]['step'] = 'PAY_INFO'
    bot.send_message(message.chat.id, "💵 কত টাকা এবং কোন নাম্বার থেকে পাঠিয়েছেন তা লিখে দিন (উদা: 2500, 017XXXXXXXX):")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get('step') == 'PAY_INFO')
def final_submit(message):
    cid = message.chat.id
    user_state[cid].update({
        'pay_info': message.text,
        'admit_time': datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    })
    bot.send_message(cid, "⏳ ধন্যবাদ! আপনার তথ্য জমা হয়েছে। এডমিন চেক করে এপ্রুভ করলে কনফার্মেশন পাবেন।")
    
    data = user_state[cid]
    admin_txt = (
        f"🔔 *নতুন ভর্তি রিকোয়েস্ট!*\n👤 নাম: {data['name']}\n📧 ইমেল: {data['email']}\n"
        f"📞 ফোন: {data['phone']}\n💵 পেমেন্ট: {message.text}\n⏰ সময়: {data['admit_time']}"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{cid}"))
    markup.add(types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{cid}"))
    bot.send_photo(ADMIN_ID, data['photo_id'], caption=admin_txt, reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_') or call.data.startswith('reject_'))
def handle_admin(call):
    sid = int(call.data.split('_')[1])
    bot.answer_callback_query(call.id)
    if call.data.startswith('approve'):
        msg = bot.send_message(ADMIN_ID, f"ইউজার {sid}-এর রোল ও রেজি দিন (Roll,Reg):")
        bot.register_next_step_handler(msg, finalize_approval, sid)
    else:
        bot.send_message(sid, "❌ আপনার পেমেন্ট তথ্য সঠিক নয়।")

def finalize_approval(message, sid):
    global sheet
    try:
        roll, reg = message.text.split(',')
        data = user_state[sid]
        app_time = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        
        if sheet:
            sheet.append_row([data['admit_time'], sid, data['name'], data['email'], data['phone'], data['pay_info'], roll.strip(), reg.strip(), app_time])
        
        bot.send_message(sid, f"🎊 ভর্তি সফল!\n🔢 রোল: `{roll.strip()}`\n🆔 রেজি: `{reg.strip()}`\n🔗 গ্রুপ: {os.getenv('GROUP_LINK')}", parse_mode='Markdown')
        bot.send_message(ADMIN_ID, "✅ এপ্রুভ সম্পন্ন!")
    except:
        bot.send_message(ADMIN_ID, "⚠️ ভুল ফরম্যাট! Roll,Reg দিন।")

if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)
