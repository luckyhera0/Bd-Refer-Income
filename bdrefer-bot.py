# -*- coding: utf-8 -*-
import logging
import datetime
import asyncio
import os
import requests
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# --- ১. Render Server Keep-Alive ---
app = Flask('')

@app.route('/')
def home():
    return "LuckyHera Bot is Online!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.setDaemon(True)
    t.start()

# --- ২. কনফিগারেশন ও এনভায়রনমেন্ট ভেরিয়েবল ---
API_TOKEN = os.getenv('BOT_TOKEN') 
ADMIN_ID = int(os.getenv('ADMIN_ID', '0')) 
PAYMENT_NUMBER = os.getenv('PAYMENT_NUMBER', '01753850929') 
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', '@luckyhera0')
FIREBASE_URL = "https://bdrefer-bot-default-rtdb.asia-southeast1.firebasedatabase.app"
MIN_WITHDRAW = 150 

# বট অবজেক্ট সেটআপ
storage = MemoryStorage()
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=storage)
logging.basicConfig(level=logging.INFO)

# --- ৩. ফায়ারবেস হেল্পার ফাংশন ---
def fb_get(path):
    r = requests.get(f"{FIREBASE_URL}/{path}.json")
    return r.json()

def fb_put(path, data):
    requests.put(f"{FIREBASE_URL}/{path}.json", json=data)

def fb_update(path, data):
    requests.patch(f"{FIREBASE_URL}/{path}.json", json=data)

def bn_num(number):
    try:
        num_str = str(int(float(number)))
        en_to_bn = {'0':'০', '1':'১', '2':'২', '3':'৩', '4':'৪', '5':'৫', '6':'৬', '7':'৭', '8':'৮', '9':'৯'}
        return ''.join(en_to_bn.get(char, char) for char in num_str)
    except:
        return "০"

# --- ৪. স্টেট ম্যানেজমেন্ট (FSM) ---
class Form(StatesGroup):
    waiting_for_pay_num = State()   
    waiting_for_trx_id = State()
    waiting_for_withdraw_num = State()
    waiting_for_broadcast = State()

# --- ৫. কিবোর্ড মেনু ---
def main_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("📊 আমার প্রোফাইল"), KeyboardButton("💸 টাকা উত্তোলন"))
    keyboard.row(KeyboardButton("🎁 ডেইলি বোনাস"), KeyboardButton("🔄 কয়েন কনভার্ট"))
    keyboard.row(KeyboardButton("ℹ️ ইনকাম তথ্য"), KeyboardButton("📞 কাস্টমার সাপোর্ট"))
    return keyboard

def admin_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("📊 সিস্টেম ড্যাশবোর্ড"), KeyboardButton("👥 ইউজার লিস্ট"))
    keyboard.row(KeyboardButton("📢 আপডেট পাঠান"), KeyboardButton("✉️ একক মেসেজ"))
    keyboard.row(KeyboardButton("📜 পেমেন্ট রিপোর্ট"), KeyboardButton("🏠 মেইন মেনু"))
    return keyboard

# --- ৬. স্টার্ট কমান্ড ও ইউজার রেজিস্ট্রেশন ---
@dp.message_handler(commands=['start'], state="*")
async def start_command(message: types.Message, state: FSMContext):
    await state.finish()
    user_id = str(message.from_user.id)
    user = fb_get(f"users/{user_id}")

    if not user:
        full_name = message.from_user.full_name
        username = f"@{message.from_user.username}" if message.from_user.username else "নেই"
        args = message.get_args()
        ref_id = args if args and args.isdigit() and args != user_id else None
        
        user_data = {
            "name": full_name, "username": username, "phone": "N/A", "status": "pending",
            "balance": 0.0, "coins": 0, "total_refer": 0, "total_earned": 0.0,
            "total_withdrawn": 0.0, "referred_by_id": ref_id, "date": datetime.datetime.now().strftime("%d-%m-%Y")
        }
        fb_put(f"users/{user_id}", user_data)
        user = user_data

    if user['status'] == 'pending':
        welcome_text = (
            f"👋 আসসালামু আলাইকুম, <b>{user['name']}</b>\n\n"
            f"আমাদের বিশ্বস্ত ইনকাম প্ল্যাটফর্মে আপনাকে স্বাগতম। প্রতি সফল রেফারে আপনি পাবেন ১৫০ কোয়েন বোনাস।\n\n"
            f"💰 <b>রেফারেল ইনকাম লেভেল:</b>\n"
            f"১. প্রাথমিক লেভেল: ২০ টাকা\n"
            f"২. ৩০০০ কোয়েন হলে: ২৫ টাকা\n"
            f"৩. ৫০০০ কোয়েন হলে: ৩০ টাকা\n\n"
            f"💠 <b>অ্যাকাউন্ট ভেরিফিকেশন নিয়ম:</b>\n"
            f"১. নিচে দেওয়া নম্বরে ৫০ টাকা Send Money করুন।\n"
            f"📌 বিকাশ/নগদ: <code>{PAYMENT_NUMBER}</code>\n\n"
            f"টাকা পাঠানো শেষ হলে নিচের বাটনে ক্লিক করুন।"
        )
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ পেমেন্ট করেছি", callback_data="submit_pay"))
        await message.answer(welcome_text, reply_markup=kb)
    else:
        await message.answer(f"✅ স্বাগতম সম্মানিত সদস্য <b>{user['name']}</b>!", reply_markup=main_menu())

# --- ৭. অ্যাডমিন প্যানেল ও বাটন লজিক ---
@dp.message_handler(commands=['admin'])
async def admin_panel_cmd(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🛠 <b>অ্যাডমিন কন্ট্রোল প্যানেল ওপেন হয়েছে।</b>", reply_markup=admin_keyboard())

@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID)
async def admin_logic(message: types.Message):
    if "📊 সিস্টেম ড্যাশবোর্ড" in message.text:
        users = fb_get("users") or {}
        total = len(users)
        active = sum(1 for u in users.values() if u.get('status') == 'active')
        withdrawn = sum(u.get('total_withdrawn', 0.0) for u in users.values())
        
        msg = (f"🛠 <b>সিস্টেম স্ট্যাটাস</b>\n━━━━━━━━━━━━━━━━━━\n"
               f"👥 মোট ইউজার: {bn_num(total)} জন\n"
               f"✅ একটিভ ইউজার: {bn_num(active)} জন\n"
               f"💸 মোট উত্তোলন: {bn_num(withdrawn)} টাকা\n━━━━━━━━━━━━━━━━━━")
        await message.answer(msg)

    elif "👥 ইউজার লিস্ট" in message.text:
        users = fb_get("users") or {}
        user_list = "👥 <b>ইউজার লিস্ট:</b>\n\n"
        for uid, data in list(users.items())[-20:]: # শেষ ২০ জন দেখাচ্ছে
            user_list += f"• {data['name']} (<code>{uid}</code>)\n"
        await message.answer(user_list)

    elif "📢 আপডেট পাঠান" in message.text:
        await Form.waiting_for_broadcast.set()
        await message.answer("📝 আপনার মেসেজটি লিখুন যা সবাইকে পাঠাতে চান:")

    elif "🏠 মেইন মেনু" in message.text:
        await message.answer("🏠 মেইন মেনু", reply_markup=main_menu())

# ব্রডকাস্ট হ্যান্ডলার
@dp.message_handler(state=Form.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    users = fb_get("users") or {}
    await state.finish()
    count = 0
    await message.answer("⏳ মেসেজ পাঠানো শুরু হচ্ছে...")
    for uid in users:
        try:
            await bot.send_message(uid, f"📢 <b>নতুন আপডেট:</b>\n\n{message.text}")
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ সফলভাবে {bn_num(count)} জনের কাছে মেসেজ পাঠানো হয়েছে।", reply_markup=admin_keyboard())

# --- ৮. পেমেন্ট ভেরিফিকেশন ---
@dp.callback_query_handler(lambda c: c.data == 'submit_pay', state="*")
async def pay_click(call: types.CallbackQuery):
    await Form.waiting_for_pay_num.set()
    await call.message.answer("📱 <b>ধাপ-১:</b> যে নম্বর থেকে টাকা পাঠিয়েছেন তা লিখুন:")
    await call.answer()

@dp.message_handler(state=Form.waiting_for_pay_num)
async def get_pay_num(message: types.Message, state: FSMContext):
    await state.update_data(p=message.text)
    await Form.waiting_for_trx_id.set()
    await message.answer("🆔 <b>ধাপ-২:</b> পেমেন্টের ট্রানজেকশন আইডি (TrxID) লিখুন:")

@dp.message_handler(state=Form.waiting_for_trx_id)
async def get_trx(message: types.Message, state: FSMContext):
    data = await state.get_data(); uid = str(message.from_user.id)
    u = fb_get(f"users/{uid}")
    fb_update(f"users/{uid}", {"phone": data['p']})
    
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}"))
    admin_msg = (f"🔔 <b>নতুন পেমেন্ট!</b>\n👤 নাম: {u['name']}\n🔗 ইউজারনেম: {u['username']}\n"
                 f"🆔 আইডি: {uid}\n📱 ফোন: {data['p']}\n🆔 TrxID: {message.text}")
    await bot.send_message(ADMIN_ID, admin_msg, reply_markup=kb)
    await message.answer("⌛ তথ্য জমা হয়েছে। অ্যাডমিন চেক করে এপ্রুভ করবেন।")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith('approve_'), state="*")
async def admin_approve(call: types.CallbackQuery):
    tid = call.data.split('_')[1]
    fb_update(f"users/{tid}", {"status": "active"})
    user = fb_get(f"users/{tid}")
    if user and user['referred_by_id']:
        rid = user['referred_by_id']
        rd = fb_get(f"users/{rid}")
        if rd:
            ref_bonus = 20.0
            if rd['coins'] >= 5000: ref_bonus = 30.0
            elif rd['coins'] >= 3000: ref_bonus = 25.0
            fb_update(f"users/{rid}", {"balance": rd['balance']+ref_bonus, "coins": rd['coins']+150, "total_refer": rd['total_refer']+1, "total_earned": rd['total_earned']+ref_bonus})
            try: await bot.send_message(rid, f"🎊 রেফারে আইডি একটিভ হয়েছে। আপনি {bn_num(ref_bonus)} টাকা বোনাস পেয়েছেন।")
            except: pass
    await bot.send_message(tid, "✅ অভিনন্দন! অ্যাকাউন্ট সক্রিয় হয়েছে।", reply_markup=main_menu())
    await call.message.edit_text(f"✅ আইডি {tid} এপ্রুভড।")
    await call.answer()

# --- ৯. ইউজার প্যানেল লজিক ---
@dp.message_handler()
async def user_logic(message: types.Message):
    uid = str(message.from_user.id)
    u = fb_get(f"users/{uid}")
    if not u: return

    if "📊 আমার প্রোফাইল" in message.text:
        bot_info = await bot.get_me()
        msg = (f"📊 <b>আপনার প্রোফাইল কার্ড</b>\n━━━━━━━━━━━━━━━━━━\n👤 <b>নাম:</b> {u['name']}\n🆔 <b>আইডি:</b> <code>{uid}</code>\n"
               f"💰 <b>ব্যালেন্স:</b> {bn_num(u['balance'])} টাকা\n🎯 <b>কোয়েন:</b> {bn_num(u['coins'])}\n"
               f"👥 <b>মোট রেফার:</b> {bn_num(u['total_refer'])} জন\n💸 <b>মোট ইনকাম:</b> {bn_num(u['total_earned'])} টাকা\n"
               f"🔗 <b>রেফার লিংক:</b>\nhttps://t.me/{bot_info.username}?start={uid}")
        await message.answer(msg)

    elif "🎁 ডেইলি বোনাস" in message.text:
        today = datetime.datetime.now().strftime("%d-%m-%Y")
        if u.get('last_bonus') == today: await message.answer("❌ আপনি আজকে অলরেডি বোনাস নিয়েছেন!")
        else:
            fb_update(f"users/{uid}", {"coins": u['coins']+10, "last_bonus": today})
            await message.answer("✅ <b>অভিনন্দন!</b> আপনি ১০ কোয়েন ডেইলি বোনাস পেয়েছেন।")

    elif "🔄 কয়েন কনভার্ট" in message.text:
        if u['coins'] < 6000: await message.answer("❌ কমপক্ষে ৬০০০ কোয়েন প্রয়োজন।")
        else:
            extra = (u['coins'] - 5000) // 1000
            if extra > 0:
                m = extra * 10; c = extra * 1000
                fb_update(f"users/{uid}", {"balance": u['balance']+m, "coins": u['coins']-c, "total_earned": u['total_earned']+m})
                await message.answer(f"✅ {bn_num(c)} কোয়েন কনভার্ট করে {bn_num(m)} টাকা পেয়েছেন।")

    elif "💸 টাকা উত্তোলন" in message.text:
        if u['balance'] < MIN_WITHDRAW: await message.answer(f"❌ সর্বনিম্ন উত্তোলন {bn_num(MIN_WITHDRAW)} টাকা।")
        else:
            kb = InlineKeyboardMarkup().row(InlineKeyboardButton("🟠 বিকাশ", callback_data="w_Bikash"), InlineKeyboardButton("🔴 নগদ", callback_data="w_Nagad"))
            await message.answer(f"💰 ব্যালেন্স: {bn_num(u['balance'])} টাকা। মেথড সিলেক্ট করুন:", reply_markup=kb)

    elif "📞 কাস্টমার সাপোর্ট" in message.text:
        await message.answer(f"👨‍💻 অ্যাডমিন: {ADMIN_USERNAME}")

# --- ১০. উইথড্র প্রসেস ---
@dp.callback_query_handler(lambda c: c.data.startswith('w_'), state="*")
async def w_method(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(m=call.data.split('_')[1])
    await Form.waiting_for_withdraw_num.set()
    await call.message.edit_text("✅ আপনার পার্সোনাল নম্বরটি লিখুন:")

@dp.message_handler(state=Form.waiting_for_withdraw_num)
async def w_process(message: types.Message, state: FSMContext):
    data = await state.get_data(); uid = str(message.from_user.id)
    u = fb_get(f"users/{uid}"); amount = u['balance']
    fb_update(f"users/{uid}", {"balance": 0.0, "total_withdrawn": u.get('total_withdrawn', 0) + amount})
    admin_msg = (f"💸 <b>উইথড্র রিকোয়েস্ট!</b>\n👤 নাম: {u['name']}\n🔗 ইউজারনেম: {u['username']}\n"
                 f"🆔 আইডি: {uid}\nপরিমাণ: {amount} টাকা\nমেথড: {data['m']}\nনম্বর: {message.text}")
    await bot.send_message(ADMIN_ID, admin_msg)
    await message.answer(f"✅ সফল! {bn_num(amount)} টাকা উত্তোলনের আবেদন জমা হয়েছে।", reply_markup=main_menu())
    await state.finish()

def start_bot():
    keep_alive()
    executor.start_polling(dp, skip_updates=True)

if __name__ == '__main__':
    start_bot()
