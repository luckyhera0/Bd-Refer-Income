# -*- coding: utf-8 -*-
import logging
import datetime
import os
import asyncio
import requests
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# --- সার্ভার সেটআপ ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- কনফিগারেশন ---
API_TOKEN = os.getenv('BOT_TOKEN') 
ADMIN_ID = int(os.getenv('ADMIN_ID', '0')) 
PAYMENT_NUMBER = os.getenv('PAYMENT_NUMBER', '01753850929') 
FIREBASE_URL = "https://bdrefer-bot-default-rtdb.asia-southeast1.firebasedatabase.app"

bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

class Form(StatesGroup):
    waiting_for_notice = State()
    waiting_for_task = State()

def fb_get(path): return requests.get(f"{FIREBASE_URL}/{path}.json").json()
def fb_update(path, data): requests.patch(f"{FIREBASE_URL}/{path}.json", json=data)

def main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📊 আমার প্রোফাইল", "💸 টাকা উত্তোলন")
    kb.row("🎁 ডেইলি বোনাস", "🔄 কয়েন কনভার্ট")
    kb.row("ℹ️ ইনকাম তথ্য", "📞 কাস্টমার সাপোর্ট")
    return kb

def admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📊 ড্যাশবোর্ড", "📢 আপডেট পাঠান", "🏠 মেইন মেনু")
    return kb

# --- অ্যাডমিন নোটিশ ও টাস্ক হ্যান্ডলার ---
@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID, commands=['admin'], state="*")
async def adm(m: types.Message, state: FSMContext):
    await state.finish()
    await m.answer("🛠 অ্যাডমিন মোড", reply_markup=admin_kb())

@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID, state="*")
async def adm_logic(m: types.Message, state: FSMContext):
    if m.text == "📢 আপডেট পাঠান":
        sub = ReplyKeyboardMarkup(resize_keyboard=True).row("📝 সাধারণ নোটিশ", "🎯 নতুন টাস্ক").add("🔙 পিছনে যান")
        await m.answer("কি পাঠাতে চান?", reply_markup=sub)
    elif m.text == "📝 সাধারণ নোটিশ":
        await Form.waiting_for_notice.set()
        await m.answer("📝 নোটিশটি লিখুন:")
    elif m.text == "🎯 নতুন টাস্ক":
        await Form.waiting_for_task.set()
        await m.answer("🎯 টাস্কের বিবরণ দিন (১০ কয়েন রিওয়ার্ড):")
    elif m.text == "🏠 মেইন মেনু":
        await m.answer("🏠 ইউজার মেনু", reply_markup=main_kb())
    # ... বাকি লজিক ...

@dp.message_handler(state=Form.waiting_for_notice)
async def send_n(m: types.Message, state: FSMContext):
    await state.finish()
    users = fb_get("users") or {}
    await m.answer("⏳ পাঠানো হচ্ছে...")
    for u in users:
        try: await bot.send_message(u, f"📢 <b>নোটিশ:</b>\n\n{m.text}")
        except: pass
    await m.answer("✅ সফল!", reply_markup=admin_kb())

@dp.message_handler(state=Form.waiting_for_task)
async def send_t(m: types.Message, state: FSMContext):
    await state.finish()
    users = fb_get("users") or {}
    tid = datetime.datetime.now().strftime("%H%M")
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ সম্পন্ন (১০ কয়েন)", callback_data=f"done_{tid}"))
    for u in users:
        try: await bot.send_message(u, f"🎯 <b>টাস্ক:</b>\n\n{m.text}", reply_markup=kb)
        except: pass
    await m.answer("✅ টাস্ক পাঠানো হয়েছে।", reply_markup=admin_kb())

# --- প্রোফাইল ও ইনকাম লজিক ---
@dp.message_handler()
async def user_m(m: types.Message):
    uid = str(m.from_user.id)
    u = fb_get(f"users/{uid}")
    if not u or u.get('status') == 'pending': return

    if m.text == "📊 আমার প্রোফাইল":
        me = await bot.get_me()
        msg = f"📊 <b>প্রোফাইল</b>\n💰 ব্যালেন্স: {u['balance']} টাকা\n🎯 কয়েন: {u['coins']}\n🔗 https://t.me/{me.username}?start={uid}"
        await m.answer(msg)
    
    elif m.text == "🔄 কয়েন কনভার্ট":
        c = u.get('coins', 0)
        if c < 6000: await m.answer("❌ ৫০০০ কয়েন লেভেলের জন্য রেখে বাকিটুকু কনভার্ট করতে পারবেন (কমপক্ষে ৬০০০ লাগবে)।")
        else:
            conv = (c - 5000) // 1000 * 1000
            money = (conv // 1000) * 10
            fb_update(f"users/{uid}", {"balance": u['balance']+money, "coins": c-conv})
            await m.answer(f"✅ {conv} কয়েন = {money} টাকা জমা হয়েছে।")

if __name__ == '__main__':
    keep_alive()
    executor.start_polling(dp, skip_updates=True)
