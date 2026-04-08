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

# --- ৬. অ্যাডমিন হ্যান্ডলার ---
@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID, commands=['admin'], state="*")
async def admin_panel(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("🛠 <b>অ্যাডমিন কন্ট্রোল প্যানেল।</b>", reply_markup=admin_keyboard())

@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID, state="*")
async def admin_logic(message: types.Message, state: FSMContext):
    if "📢 আপডেট পাঠান" in message.text:
        await Form.waiting_for_notice.set()
        await message.answer("📝 একটি নোটিশ লিখুন যা সবার কাছে পৌঁছাবে:")
    elif "📊 ড্যাশবোর্ড" in message.text:
        users = fb_get("users") or {}
        active = sum(1 for u in users.values() if u.get('status')=='active')
        msg = f"📊 <b>লাইভ ড্যাশবোর্ড</b>\n👥 মোট ইউজার: {bn_num(len(users))}\n✅ একটিভ ইউজার: {bn_num(active)}"
        await message.answer(msg)
    elif "🏠 মেইন মেনু" in message.text:
        await message.answer("🏠 মেইন মেনু", reply_markup=main_menu())
    else:
        await user_panel_logic(message, state)

@dp.message_handler(state=Form.waiting_for_notice)
async def process_notice(message: types.Message, state: FSMContext):
    notice_text = message.text
    await state.finish()
    users = fb_get("users") or {}
    await message.answer("⏳ নোটিশ পাঠানো হচ্ছে...")
    count = 0
    for uid in users:
        try:
            await bot.send_message(uid, f"📢 <b>নতুন আপডেট:</b>\n\n{notice_text}")
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ সফলভাবে {bn_num(count)} জনের কাছে নোটিশ পাঠানো হয়েছে।", reply_markup=admin_keyboard())

# --- ৭. ইউজার প্যানেল ও কনভার্ট অ্যালগরিদম ---
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
            await message.answer("❌ আপনার একাউন্টে ৫০০০ কয়েন জমা থাকা বাধ্যতামূলক। ৫০০০ এর উপরে প্রতি ১০০০ কয়েন হলে ১০ টাকা কনভার্ট করতে পারবেন।")
        else:
            convertible = (current_coins - 5000) // 1000 * 1000
            money = (convertible // 1000) * 10
            fb_update(f"users/{uid}", {
                "balance": u['balance'] + money, 
                "coins": current_coins - convertible
            })
            await message.answer(f"✅ {bn_num(convertible)} কয়েন কনভার্ট করে {bn_num(money)} টাকা ব্যালেন্সে যোগ করা হয়েছে।")

    elif "ℹ️ ইনকাম তথ্য" in message.text:
        info = (
            "ℹ️ <b>ইনকাম ও লেভেল সিস্টেম</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "💰 <b>রেফার ইনকাম:</b>\n"
            "• ০-২৯৯৯ কয়েন: ২০ টাকা + ১৫০ কয়েন\n"
            "• ৩০০০-৪৯৯৯ কয়েন: ২৫ টাকা + ১৫০ কয়েন\n"
            "• ৫০০০+ কয়েন: ৩০ টাকা + ১৫০ কয়েন\n\n"
            "🔄 <b>কয়েন কনভার্ট:</b>\n"
            "১০০০ কয়েন = ১০ টাকা (৫০০০ কয়েন একাউন্টে জমা থাকা বাধ্যতামূলক)\n\n"
            "💸 <b>উত্তোলন:</b> সর্বনিম্ন ১৫০ টাকা।"
        )
        await message.answer(info)

# --- ৮. অ্যাপ্রুভ ও রেফার বোনাস লজিক ---
@dp.callback_query_handler(lambda c: c.data.startswith('approve_'))
async def approve_pay(call: types.CallbackQuery):
    tid = call.data.split('_')[1]
    fb_update(f"users/{tid}", {"status": "active"})
    user = fb_get(f"users/{tid}")
    if user and user.get('referred_by_id'):
        rid = user['referred_by_id']
        rd = fb_get(f"users/{rid}")
        if rd:
            u_coins = rd.get('coins', 0)
            ref_money = 20.0
            if u_coins >= 5000: ref_money = 30.0
            elif u_coins >= 3000: ref_money = 25.0
            
            fb_update(f"users/{rid}", {
                "balance": rd.get('balance', 0.0) + ref_money, 
                "coins": u_coins + 150, # ১৫০ কয়েন রেফার বোনাস
                "total_refer": rd.get('total_refer', 0) + 1
            })
            try: await bot.send_message(rid, f"🎊 রেফার সফল! আপনি {bn_num(ref_money)} টাকা ও ১৫০ কয়েন বোনাস পেয়েছেন।")
            except: pass
    await bot.send_message(tid, "✅ অভিনন্দন! অ্যাকাউন্ট সক্রিয় হয়েছে।", reply_markup=main_menu())
    await call.message.edit_text(f"✅ আইডি {tid} এপ্রুভড।")

# --- ৯. পেমেন্ট ও স্টার্ট (সংক্ষিপ্ত) ---
@dp.callback_query_handler(lambda c: c.data == 'submit_pay', state="*")
async def pay_click(call: types.CallbackQuery):
    await Form.waiting_for_pay_num.set()
    await call.message.answer("📱 নম্বরটি লিখুন:")
    await call.answer()

@dp.message_handler(state=Form.waiting_for_pay_num)
async def get_pay_num(message: types.Message, state: FSMContext):
    await state.update_data(p=message.text)
    await Form.waiting_for_trx_id.set()
    await message.answer("🆔 TrxID লিখুন:")

@dp.message_handler(state=Form.waiting_for_trx_id)
async def get_trx(message: types.Message, state: FSMContext):
    data = await state.get_data(); uid = str(message.from_user.id)
    u = fb_get(f"users/{uid}")
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}"))
    await bot.send_message(ADMIN_ID, f"🔔 পেমেন্ট রিকোয়েস্ট\n👤 {u['name']}\n📱 {data['p']}\n🆔 {message.text}", reply_markup=kb)
    await message.answer("⌛ অ্যাডমিন চেক করে এপ্রুভ করবেন।")
    await state.finish()

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
    else: await message.answer("স্বাগতম!", reply_markup=main_menu())

if __name__ == '__main__':
    keep_alive()
    executor.start_polling(dp, skip_updates=True)
