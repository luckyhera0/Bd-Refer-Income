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
def home(): return "LuckyHera Bot is Online!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.setDaemon(True)
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

# --- ৩. ফায়ারবেস Helper ---
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

# --- ৫. কিবোর্ড মেনুসমূহ ---
def main_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("📊 আমার প্রোফাইল"), KeyboardButton("💸 টাকা উত্তোলন"))
    keyboard.row(KeyboardButton("🎁 ডেইলি বোনাস"), KeyboardButton("🔄 কয়েন কনভার্ট"))
    keyboard.row(KeyboardButton("ℹ️ ইনকাম তথ্য"), KeyboardButton("📞 কাস্টমার সাপোর্ট"))
    return keyboard

def admin_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("📊 সিস্টেম ড্যাশবোর্ড"), KeyboardButton("👥 ইউজার লিস্ট"))
    keyboard.row(KeyboardButton("📢 আপডেট পাঠান"), KeyboardButton("🏠 মেইন মেনু"))
    return keyboard

def update_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("📝 সাধারণ নোটিশ"), KeyboardButton("🎯 নতুন টাস্ক"))
    keyboard.row(KeyboardButton("🔙 পিছনে যান"))
    return keyboard

# --- ৬. স্টার্ট ও রেজিস্ট্রেশন ---
@dp.message_handler(commands=['start'], state="*")
async def start_command(message: types.Message, state: FSMContext):
    await state.finish()
    user_id = str(message.from_user.id)
    user = fb_get(f"users/{user_id}")

    if not user:
        user_data = {
            "name": message.from_user.full_name, "username": f"@{message.from_user.username}" if message.from_user.username else "নেই",
            "phone": "N/A", "status": "pending", "balance": 0.0, "coins": 0, "total_refer": 0, 
            "total_earned": 0.0, "total_withdrawn": 0.0, "referred_by_id": message.get_args() if message.get_args().isdigit() else None,
            "date": datetime.datetime.now().strftime("%d-%m-%Y")
        }
        fb_put(f"users/{user_id}", user_data)
        user = user_data

    if user['status'] == 'pending':
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ পেমেন্ট করেছি", callback_data="submit_pay"))
        await message.answer(f"👋 স্বাগতম <b>{user['name']}</b>\nপেমেন্ট নম্বর: <code>{PAYMENT_NUMBER}</code>", reply_markup=kb)
    else:
        await message.answer(f"✅ স্বাগতম!", reply_markup=main_menu())

# --- ৭. অ্যাডমিন লজিক (আপডেট ও টাস্ক) ---
@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID, state="*")
async def admin_actions(message: types.Message, state: FSMContext):
    if message.text == "/admin":
        await message.answer("🛠 অ্যাডমিন মোড অ্যাক্টিভ", reply_markup=admin_keyboard())
    
    elif "📢 আপডেট পাঠান" in message.text:
        await message.answer("কোন ধরনের আপডেট পাঠাতে চান?", reply_markup=update_menu())
    
    elif "📝 সাধারণ নোটিশ" in message.text:
        await Form.waiting_for_notice.set()
        await message.answer("📝 নোটিশ মেসেজটি লিখুন (এটি সবাই শুধু দেখতে পাবে):")
        
    elif "🎯 নতুন টাস্ক" in message.text:
        await Form.waiting_for_task_msg.set()
        await message.answer("🎯 টাস্কের বিস্তারিত লিখুন:\n(ইউজার এটি সম্পন্ন করলে ১০ কয়েন পাবে)")

    elif "🔙 পিছনে যান" in message.text:
        await message.answer("অ্যাডমিন মেনু", reply_markup=admin_keyboard())

    elif "📊 সিস্টেম ড্যাশবোর্ড" in message.text:
        users = fb_get("users") or {}
        msg = f"👥 মোট ইউজার: {bn_num(len(users))}\n💸 মোট উত্তোলন: {bn_num(sum(u.get('total_withdrawn', 0) for u in users.values()))} টাকা"
        await message.answer(msg)

# --- ৮. নোটিশ ও টাস্ক সেন্ডিং লজিক ---
@dp.message_handler(state=Form.waiting_for_notice)
async def send_notice(message: types.Message, state: FSMContext):
    await state.finish()
    users = fb_get("users") or {}
    for uid in users:
        try: await bot.send_message(uid, f"📢 <b>নতুন নোটিশ:</b>\n\n{message.text}")
        except: pass
    await message.answer("✅ নোটিশ পাঠানো হয়েছে।", reply_markup=admin_keyboard())

@dp.message_handler(state=Form.waiting_for_task_msg)
async def send_task(message: types.Message, state: FSMContext):
    task_text = message.text
    await state.finish()
    
    users = fb_get("users") or {}
    task_id = datetime.datetime.now().strftime("%H%M%S") # ইউনিক টাস্ক আইডি
    
    # ইনলাইন বাটন - এখানে ১০ কয়েন ফিক্সড করা হয়েছে
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ সম্পন্ন করেছি (১০ কয়েন)", callback_data=f"done_{task_id}"))
    
    for uid in users:
        try: await bot.send_message(uid, f"🎯 <b>নতুন টাস্ক!</b>\n\n{task_text}\n\n💰 রিওয়ার্ড: ১০ কয়েন", reply_markup=kb)
        except: pass
    await message.answer(f"✅ টাস্ক পাঠানো হয়েছে!", reply_markup=admin_keyboard())

# --- ৯. টাস্ক কমপ্লিট ও ১০ কয়েন জমা করা ---
@dp.callback_query_handler(lambda c: c.data.startswith('done_'))
async def task_done_callback(call: types.CallbackQuery):
    task_id = call.data.split('_')[1]
    uid = str(call.from_user.id)
    reward = 10  # প্রতি টাস্কে ১০ কয়েন
    
    # চেক করা ইউজার আগে করেছে কি না
    history = fb_get(f"task_history/{uid}") or []
    if task_id in history:
        return await call.answer("❌ আপনি এই টাস্কটি আগেই করেছেন!", show_alert=True)
    
    # কয়েন আপডেট
    u = fb_get(f"users/{uid}")
    if u:
        fb_update(f"users/{uid}", {"coins": u.get('coins', 0) + reward})
        history.append(task_id)
        fb_put(f"task_history/{uid}", history)
        
        await call.message.edit_text(f"✅ <b>টাস্ক সফল!</b>\nআপনি {bn_num(reward)} কয়েন বোনাস পেয়েছেন।")
    await call.answer()

# --- ১০. বাকি ফাংশনগুলো (আগের মতোই রাখা হয়েছে) ---
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
    admin_msg = f"🔔 পেমেন্ট রিকোয়েস্ট\n👤 {u['name']}\n📱 {data['p']}\n🆔 {message.text}"
    await bot.send_message(ADMIN_ID, admin_msg, reply_markup=kb)
    await message.answer("⌛ অ্যাডমিন চেক করে এপ্রুভ করবেন।")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith('approve_'))
async def admin_approve(call: types.CallbackQuery):
    tid = call.data.split('_')[1]
    fb_update(f"users/{tid}", {"status": "active"})
    user = fb_get(f"users/{tid}")
    if user and user.get('referred_by_id'):
        rid = user['referred_by_id']
        rd = fb_get(f"users/{rid}")
        if rd:
            bonus = 20.0
            if rd.get('coins', 0) >= 5000: bonus = 30.0
            elif rd.get('coins', 0) >= 3000: bonus = 25.0
            fb_update(f"users/{rid}", {"balance": rd.get('balance', 0)+bonus, "coins": rd.get('coins', 0)+150, "total_refer": rd.get('total_refer', 0)+1, "total_earned": rd.get('total_earned', 0)+bonus})
            try: await bot.send_message(rid, f"🎊 রেফার সফল! {bn_num(bonus)} টাকা বোনাস পেয়েছেন।")
            except: pass
    await bot.send_message(tid, "✅ আইডি একটিভ হয়েছে।", reply_markup=main_menu())
    await call.message.edit_text(f"✅ এপ্রুভড {tid}")
    await call.answer()

@dp.message_handler()
async def user_panel(message: types.Message):
    uid = str(message.from_user.id)
    u = fb_get(f"users/{uid}")
    if not u: return

    if "📊 আমার প্রোফাইল" in message.text:
        bot_info = await bot.get_me()
        msg = f"📊 <b>প্রোফাইল</b>\n💰 ব্যালেন্স: {bn_num(u['balance'])} টাকা\n🎯 কয়েন: {bn_num(u['coins'])}\n👥 রেফার: {bn_num(u['total_refer'])}\n🔗 লিংক: https://t.me/{bot_info.username}?start={uid}"
        await message.answer(msg)
    elif "🎁 ডেইলি বোনাস" in message.text:
        today = datetime.datetime.now().strftime("%d-%m-%Y")
        if u.get('last_bonus') == today: await message.answer("❌ অলরেডি নিয়েছেন!")
        else:
            fb_update(f"users/{uid}", {"coins": u['coins']+10, "last_bonus": today})
            await message.answer("✅ ১০ কয়েন পেয়েছেন।")
    elif "💸 টাকা উত্তোলন" in message.text:
        if u['balance'] < MIN_WITHDRAW: await message.answer(f"❌ সর্বনিম্ন {bn_num(MIN_WITHDRAW)} টাকা উত্তোলন।")
        else:
            kb = InlineKeyboardMarkup().row(InlineKeyboardButton("🟠 বিকাশ", callback_data="w_Bikash"), InlineKeyboardButton("🔴 নগদ", callback_data="w_Nagad"))
            await message.answer(f"💰 ব্যালেন্স: {bn_num(u['balance'])}। মেথড সিলেক্ট করুন:", reply_markup=kb)

# উইথড্র প্রসেস
@dp.callback_query_handler(lambda c: c.data.startswith('w_'), state="*")
async def w_method(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(m=call.data.split('_')[1])
    await Form.waiting_for_withdraw_num.set()
    await call.message.edit_text("✅ আপনার নম্বরটি লিখুন:")

@dp.message_handler(state=Form.waiting_for_withdraw_num)
async def w_process(message: types.Message, state: FSMContext):
    data = await state.get_data(); uid = str(message.from_user.id)
    u = fb_get(f"users/{uid}"); amount = u['balance']
    fb_update(f"users/{uid}", {"balance": 0.0, "total_withdrawn": u.get('total_withdrawn', 0) + amount})
    await bot.send_message(ADMIN_ID, f"💸 উইথড্র আবেদন!\nআইডি: {uid}\nপরিমাণ: {amount} টাকা\nনম্বর: {message.text}")
    await message.answer(f"✅ আবেদন জমা হয়েছে।", reply_markup=main_menu())
    await state.finish()

if __name__ == '__main__':
    keep_alive()
    executor.start_polling(dp, skip_updates=True)
