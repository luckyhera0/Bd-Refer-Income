# -*- coding: utf-8 -*-
import logging
import datetime
import os
import asyncio
import requests
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# --- ১. সার্ভার কিপ-অ্যালাইভ ---
app = Flask('')
@app.route('/')
def home(): return "LuckyHera Bot is Online!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- ২. কনফিগারেশন ---
API_TOKEN = os.getenv('BOT_TOKEN') 
ADMIN_ID = int(os.getenv('ADMIN_ID', '0')) 
PAYMENT_NUMBER = os.getenv('PAYMENT_NUMBER', '01753850929') 
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', '@luckyhera0')
FIREBASE_URL = "https://bdrefer-bot-default-rtdb.asia-southeast1.firebasedatabase.app"
MIN_WITHDRAW = 150 

storage = MemoryStorage()
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=storage)
logging.basicConfig(level=logging.INFO)

# --- ৩. ডাটাবেজ হেল্পার ---
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
    except: return "০"

# --- ৪. স্টেট ম্যানেজমেন্ট ---
class Form(StatesGroup):
    waiting_for_pay_num = State()   
    waiting_for_trx_id = State()
    waiting_for_withdraw_num = State()
    waiting_for_notice = State()      
    waiting_for_task_msg = State()    

# --- ৫. কিবোর্ড মেনু ---
def main_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("📊 আমার প্রোফাইল"), KeyboardButton("💸 টাকা উত্তোলন"))
    keyboard.row(KeyboardButton("🎁 ডেইলি বোনাস"), KeyboardButton("🔄 কয়েন কনভার্ট"))
    keyboard.row(KeyboardButton("ℹ️ ইনকাম তথ্য"), KeyboardButton("📞 কাস্টমার সাপোর্ট"))
    return keyboard

def admin_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("📊 ড্যাশবোর্ড"), KeyboardButton("📢 আপডেট পাঠান"))
    keyboard.row(KeyboardButton("🏠 মেইন মেনু"))
    return keyboard

def update_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("📝 সাধারণ নোটিশ"), KeyboardButton("🎯 নতুন টাস্ক"))
    keyboard.row(KeyboardButton("🔙 পিছনে যান"))
    return keyboard

# --- ৬. অ্যাডমিন কমান্ড ও অ্যাকশন ---
@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID, commands=['admin'], state="*")
async def admin_panel(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("🛠 <b>অ্যাডমিন কন্ট্রোল মোড অ্যাক্টিভ।</b>", reply_markup=admin_keyboard())

@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID, state="*")
async def admin_logic(message: types.Message, state: FSMContext):
    if "📢 আপডেট পাঠান" in message.text:
        await message.answer("কোন ধরনের আপডেট পাঠাতে চান?", reply_markup=update_menu())
    
    elif "📝 সাধারণ নোটিশ" in message.text:
        await Form.waiting_for_notice.set()
        await message.answer("📝 নোটিশের লেখাটি পাঠান (এটি সরাসরি সবার ইনবক্সে যাবে):")

    elif "🎯 নতুন টাস্ক" in message.text:
        await Form.waiting_for_task_msg.set()
        await message.answer("🎯 টাস্কের বিস্তারিত (লিঙ্কসহ) লিখুন:\n(ইউজার বাটন ক্লিক করলে ১০ কয়েন পাবে)")

    elif "📊 ড্যাশবোর্ড" in message.text:
        users = fb_get("users") or {}
        msg = f"📊 মোট ইউজার: {bn_num(len(users))}\n✅ একটিভ: {bn_num(sum(1 for u in users.values() if u.get('status')=='active'))}"
        await message.answer(msg)

    elif "🏠 মেইন মেনু" in message.text or "🔙 পিছনে যান" in message.text:
        await message.answer("🏠 মেইন মেনু", reply_markup=main_menu())
    
    else:
        # অ্যাডমিন যাতে ইউজার প্যানেলও ব্যবহার করতে পারে
        await user_panel_logic(message, state)

# --- ৭. নোটিশ ও টাস্ক ব্রডকাস্ট প্রসেসর ---
@dp.message_handler(state=Form.waiting_for_notice)
async def process_notice(message: types.Message, state: FSMContext):
    notice_text = message.text
    await state.finish()
    users = fb_get("users") or {}
    await message.answer("⏳ সবার কাছে নোটিশ পাঠানো হচ্ছে...")
    count = 0
    for uid in users:
        try:
            await bot.send_message(uid, f"📢 <b>নতুন আপডেট:</b>\n\n{notice_text}")
            count += 1
            await asyncio.sleep(0.05) # সার্ভার লোড কমাতে
        except: pass
    await message.answer(f"✅ সফলভাবে {bn_num(count)} জনের কাছে নোটিশ পাঠানো হয়েছে।", reply_markup=admin_keyboard())

@dp.message_handler(state=Form.waiting_for_task_msg)
async def process_task(message: types.Message, state: FSMContext):
    task_text = message.text
    await state.finish()
    users = fb_get("users") or {}
    task_id = datetime.datetime.now().strftime("%H%M%S")
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ সম্পন্ন করেছি (১০ কয়েন)", callback_data=f"done_{task_id}"))
    
    await message.answer("⏳ সবার কাছে টাস্ক পাঠানো হচ্ছে...")
    count = 0
    for uid in users:
        try:
            await bot.send_message(uid, f"🎯 <b>নতুন টাস্ক!</b>\n\n{task_text}\n\n💰 রিওয়ার্ড: ১০ কয়েন", reply_markup=kb)
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ সফলভাবে {bn_num(count)} জনের কাছে টাস্ক পাঠানো হয়েছে।", reply_markup=admin_keyboard())

# --- ৮. ইউজার প্যানেল লজিক ---
async def user_panel_logic(message: types.Message, state: FSMContext):
    uid = str(message.from_user.id)
    u = fb_get(f"users/{uid}")
    if not u or u.get('status') == 'pending': return

    if "📊 আমার প্রোফাইল" in message.text:
        bot_info = await bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={uid}"
        msg = (f"📊 <b>আপনার প্রোফাইল</b>\n━━━━━━━━━━━━━━\n👤 নাম: {u['name']}\n🆔 আইডি: <code>{uid}</code>\n"
               f"💰 ব্যালেন্স: {bn_num(u['balance'])} টাকা\n🎯 কয়েন: {bn_num(u['coins'])}\n"
               f"👥 মোট রেফার: {bn_num(u['total_refer'])} জন\n━━━━━━━━━━━━━━\n"
               f"🔗 <b>রেফার লিংক:</b>\n{ref_link}")
        await message.answer(msg)

    elif "🔄 কয়েন কনভার্ট" in message.text:
        current_coins = u.get('coins', 0)
        if current_coins < 6000:
            await message.answer("❌ লেভেল আপগ্রেডের জন্য ৫০০০ কয়েন জমা থাকা বাধ্যতামূলক। ৫০০০ এর উপরে প্রতি ১০০০ কয়েন হলে ১০ টাকা কনভার্ট করতে পারবেন।")
        else:
            convertible = (current_coins - 5000) // 1000 * 1000
            money = (convertible // 1000) * 10
            fb_update(f"users/{uid}", {"balance": u['balance'] + money, "coins": current_coins - convertible})
            await message.answer(f"✅ {bn_num(convertible)} কয়েন কনভার্ট করে {bn_num(money)} টাকা পেয়েছেন।")

    elif "ℹ️ ইনকাম তথ্য" in message.text:
        info = "ℹ️ <b>ইনকাম পলিসি</b>\n• ৫০০০ কয়েন লেভেল বোনাস লক থাকবে।\n• এরপর প্রতি ১০০০ কয়েন = ১০ টাকা।\n• প্রতি টাস্ক = ১০ কয়েন।"
        await message.answer(info)

    elif "🎁 ডেইলি বোনাস" in message.text:
        today = datetime.datetime.now().strftime("%d-%m-%Y")
        if u.get('last_bonus') == today: await message.answer("❌ অলরেডি নিয়েছেন!")
        else:
            fb_update(f"users/{uid}", {"coins": u.get('coins', 0)+10, "last_bonus": today})
            await message.answer("✅ ১০ কয়েন বোনাস পেয়েছেন।")

# --- ৯. পেমেন্ট ও টাস্ক কলব্যাক ---
@dp.callback_query_handler(lambda c: c.data.startswith('done_'))
async def task_done(call: types.CallbackQuery):
    task_id = call.data.split('_')[1]
    uid = str(call.from_user.id)
    history = fb_get(f"task_history/{uid}") or []
    if task_id in history:
        return await call.answer("❌ আপনি এটি আগেই করেছেন!", show_alert=True)
    
    u = fb_get(f"users/{uid}")
    if u:
        fb_update(f"users/{uid}", {"coins": u.get('coins', 0) + 10})
        history.append(task_id)
        fb_put(f"task_history/{uid}", history)
        await call.message.edit_text(f"✅ <b>টাস্ক সফল!</b> ১০ কয়েন জমা হয়েছে।")
    await call.answer()

@dp.message_handler(commands=['start'], state="*")
async def start(message: types.Message, state: FSMContext):
    await state.finish()
    uid = str(message.from_user.id)
    user = fb_get(f"users/{uid}")
    if not user:
        user_data = {"name": message.from_user.full_name, "status": "pending", "balance": 0.0, "coins": 0, "total_refer": 0, "referred_by_id": message.get_args() if message.get_args().isdigit() else None}
        fb_put(f"users/{uid}", user_data)
        user = user_data
    
    if user['status'] == 'pending':
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ পেমেন্ট করেছি", callback_data="submit_pay"))
        await message.answer(f"পেমেন্ট নম্বর: {PAYMENT_NUMBER}", reply_markup=kb)
    else:
        await message.answer("স্বাগতম!", reply_markup=main_menu())

if __name__ == '__main__':
    keep_alive()
    executor.start_polling(dp, skip_updates=True)
