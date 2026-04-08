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
# FSM (Finite State Machine) ইমপোর্ট
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

# --- ২. কনফিগারেশন ও এনভায়রনমেন্ট ---
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

# --- ৩. ফায়ারবেস হেল্পার ---
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
            "name": message.from_user.full_name, 
            "username": f"@{message.from_user.username}" if message.from_user.username else "নেই",
            "phone": "N/A", "status": "pending", "balance": 0.0, "coins": 0, "total_refer": 0, 
            "total_earned": 0.0, "total_withdrawn": 0.0, 
            "referred_by_id": message.get_args() if message.get_args().isdigit() else None,
            "date": datetime.datetime.now().strftime("%d-%m-%Y")
        }
        fb_put(f"users/{user_id}", user_data)
        user = user_data

    if user['status'] == 'pending':
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ পেমেন্ট করেছি", callback_data="submit_pay"))
        await message.answer(f"👋 স্বাগতম <b>{user['name']}</b>\nঅ্যাকাউন্ট একটিভ করতে <code>{PAYMENT_NUMBER}</code> নম্বরে ৫০ টাকা পাঠিয়ে নিচের বাটনে ক্লিক করুন।", reply_markup=kb)
    else:
        await message.answer(f"✅ মেইন মেনু ওপেন হয়েছে।", reply_markup=main_menu())

# --- ৭. অ্যাডমিন প্যানেল হ্যান্ডলার ---
@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID, commands=['admin'], state="*")
async def admin_cmd(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("🛠 অ্যাডমিন মোড অ্যাক্টিভ হয়েছে।", reply_markup=admin_keyboard())

# অ্যাডমিন বাটন ফিল্টার
@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID, state="*")
async def admin_buttons(message: types.Message, state: FSMContext):
    if "📢 আপডেট পাঠান" in message.text:
        await message.answer("কোন ধরনের আপডেট পাঠাতে চান?", reply_markup=update_menu())
    
    elif "📝 সাধারণ নোটিশ" in message.text:
        await Form.waiting_for_notice.set()
        await message.answer("📝 নোটিশ মেসেজটি লিখুন:")
        
    elif "🎯 নতুন টাস্ক" in message.text:
        await Form.waiting_for_task_msg.set()
        await message.answer("🎯 টাস্কের বিবরণ বা লিঙ্কটি দিন (ইউজার সম্পন্ন করলে ১০ কয়েন পাবে):")

    elif "🔙 পিছনে যান" in message.text:
        await message.answer("অ্যাডমিন কন্ট্রোল", reply_markup=admin_keyboard())

    elif "📊 সিস্টেম ড্যাশবোর্ড" in message.text:
        users = fb_get("users") or {}
        active = sum(1 for u in users.values() if u.get('status') == 'active')
        msg = f"📊 <b>লাইভ ড্যাশবোর্ড</b>\n━━━━━━━━━━━━━\n👥 মোট ইউজার: {bn_num(len(users))}\n✅ একটিভ ইউজার: {bn_num(active)}"
        await message.answer(msg)
    
    elif "🏠 মেইন মেনু" in message.text:
        await message.answer("🏠 ইউজার প্যানেল", reply_markup=main_menu())

    elif "👥 ইউজার লিস্ট" in message.text:
        users = fb_get("users") or {}
        user_list = "👥 <b>ইউজার লিস্ট:</b>\n"
        for uid, data in list(users.items())[-15:]:
            user_list += f"• {data['name']} (<code>{uid}</code>)\n"
        await message.answer(user_list)

    # যদি অ্যাডমিন ইউজার বাটন ব্যবহার করতে চায়
    else:
        await user_panel_logic(message)

# --- ৮. টাস্ক ও নোটিশ সেন্ডিং লজিক ---
@dp.message_handler(state=Form.waiting_for_notice)
async def process_notice(message: types.Message, state: FSMContext):
    await state.finish()
    users = fb_get("users") or {}
    await message.answer("⏳ নোটিশ পাঠানো হচ্ছে...")
    for uid in users:
        try: await bot.send_message(uid, f"📢 <b>নতুন আপডেট:</b>\n\n{message.text}")
        except: pass
    await message.answer("✅ নোটিশ পাঠানো সফল হয়েছে!", reply_markup=admin_keyboard())

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
        except: pass
    await message.answer(f"✅ সফলভাবে {bn_num(count)} জন ইউজারের কাছে টাস্ক গিয়েছে।", reply_markup=admin_keyboard())

# --- ৯. টাস্ক বোনাস রিসিভ (Callback) ---
@dp.callback_query_handler(lambda c: c.data.startswith('done_'))
async def receive_task_bonus(call: types.CallbackQuery):
    task_id = call.data.split('_')[1]
    uid = str(call.from_user.id)
    
    history = fb_get(f"task_history/{uid}") or []
    if task_id in history:
        return await call.answer("❌ আপনি এই টাস্কটি আগেই সম্পন্ন করেছেন!", show_alert=True)
    
    u = fb_get(f"users/{uid}")
    if u:
        fb_update(f"users/{uid}", {"coins": u.get('coins', 0) + 10})
        history.append(task_id)
        fb_put(f"task_history/{uid}", history)
        await call.message.edit_text(f"✅ <b>অভিনন্দন!</b> আপনি ১০ কয়েন বোনাস পেয়েছেন।")
    await call.answer()

# --- ১০. ইউজার প্যানেল লজিক ---
@dp.message_handler()
async def user_panel_logic(message: types.Message):
    uid = str(message.from_user.id)
    u = fb_get(f"users/{uid}")
    if not u or u.get('status') == 'pending': return

    if "📊 আমার প্রোফাইল" in message.text:
        bot_info = await bot.get_me()
        msg = f"📊 <b>আপনার প্রোফাইল</b>\n💰 ব্যালেন্স: {bn_num(u['balance'])} টাকা\n🎯 কয়েন: {bn_num(u['coins'])}\n👥 রেফার: {bn_num(u['total_refer'])}\n🔗 লিংক: https://t.me/{bot_info.username}?start={uid}"
        await message.answer(msg)

    elif "🎁 ডেইলি বোনাস" in message.text:
        today = datetime.datetime.now().strftime("%d-%m-%Y")
        if u.get('last_bonus') == today: await message.answer("❌ আপনি আজকে অলরেডি বোনাস নিয়েছেন!")
        else:
            fb_update(f"users/{uid}", {"coins": u['coins']+10, "last_bonus": today})
            await message.answer("✅ ১০ কয়েন বোনাস পেয়েছেন।")

    elif "🔄 কয়েন কনভার্ট" in message.text:
        if u['coins'] < 6000: await message.answer("❌ কয়েন কনভার্ট করতে কমপক্ষে ৬০০০ কয়েন প্রয়োজন।")
        else:
            amount_to_add = (u['coins'] // 1000) * 10
            coins_to_cut = (u['coins'] // 1000) * 1000
            fb_update(f"users/{uid}", {
                "balance": u['balance'] + amount_to_add, 
                "coins": u['coins'] - coins_to_cut,
                "total_earned": u.get('total_earned', 0) + amount_to_add
            })
            await message.answer(f"✅ {bn_num(coins_to_cut)} কয়েন কনভার্ট করে {bn_num(amount_to_add)} টাকা পেয়েছেন।")

    elif "💸 টাকা উত্তোলন" in message.text:
        if u['balance'] < MIN_WITHDRAW: await message.answer(f"❌ আপনার ব্যালেন্স {bn_num(MIN_WITHDRAW)} টাকার কম।")
        else:
            kb = InlineKeyboardMarkup().row(InlineKeyboardButton("🟠 বিকাশ", callback_data="w_Bikash"), InlineKeyboardButton("🔴 নগদ", callback_data="w_Nagad"))
            await message.answer(f"💰 ব্যালেন্স: {bn_num(u['balance'])} টাকা। মেথড সিলেক্ট করুন:", reply_markup=kb)

    elif "📞 কাস্টমার সাপোর্ট" in message.text:
        await message.answer(f"👨‍💻 সরাসরি সাহায্যের জন্য অ্যাডমিনকে মেসেজ দিন: {ADMIN_USERNAME}")

    elif "ℹ️ ইনকাম তথ্য" in message.text:
        await message.answer("ℹ️ <b>ইনকাম পলিসি:</b>\nপ্রতি রেফারে পাবেন ১৫০ কয়েন এবং ২০-৩০ টাকা। ১০ কয়েন = ১ টাকা (কনভার্ট রেট)।")

# --- ১১. পেমেন্ট ও উইথড্র কলব্যাকস ---
@dp.callback_query_handler(lambda c: c.data == 'submit_pay', state="*")
async def pay_click(call: types.CallbackQuery):
    await Form.waiting_for_pay_num.set()
    await call.message.answer("📱 যে নম্বর থেকে টাকা পাঠিয়েছেন তা লিখুন:")
    await call.answer()

@dp.message_handler(state=Form.waiting_for_pay_num)
async def get_pay_num(message: types.Message, state: FSMContext):
    await state.update_data(p=message.text)
    await Form.waiting_for_trx_id.set()
    await message.answer("🆔 পেমেন্টের ট্রানজেকশন আইডি (TrxID) লিখুন:")

@dp.message_handler(state=Form.waiting_for_trx_id)
async def get_trx(message: types.Message, state: FSMContext):
    data = await state.get_data(); uid = str(message.from_user.id)
    u = fb_get(f"users/{uid}")
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}"))
    await bot.send_message(ADMIN_ID, f"🔔 <b>নতুন পেমেন্ট!</b>\n👤 {u['name']}\n📱 {data['p']}\n🆔 {message.text}", reply_markup=kb)
    await message.answer("⌛ আপনার তথ্য জমা হয়েছে। অ্যাডমিন চেক করে আইডি একটিভ করে দিবে।")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith('approve_'))
async def approve_id(call: types.CallbackQuery):
    tid = call.data.split('_')[1]
    fb_update(f"users/{tid}", {"status": "active"})
    user = fb_get(f"users/{tid}")
    if user and user.get('referred_by_id'):
        rid = user['referred_by_id']
        rd = fb_get(f"users/{rid}")
        if rd:
            bonus = 20.0 # ডিফল্ট রেফার বোনাস
            fb_update(f"users/{rid}", {"balance": rd.get('balance', 0)+bonus, "coins": rd.get('coins', 0)+150, "total_refer": rd.get('total_refer', 0)+1})
            try: await bot.send_message(rid, f"🎊 আপনার রেফারে একজন জয়েন করেছে! আপনি বোনাস পেয়েছেন।")
            except: pass
    await bot.send_message(tid, "✅ অভিনন্দন! আপনার অ্যাকাউন্ট এখন সক্রিয়।", reply_markup=main_menu())
    await call.message.edit_text(f"✅ আইডি {tid} সফলভাবে একটিভ করা হয়েছে।")
    await call.answer()

# উত্তোলন প্রসেস
@dp.callback_query_handler(lambda c: c.data.startswith('w_'), state="*")
async def withdraw_method(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(m=call.data.split('_')[1])
    await Form.waiting_for_withdraw_num.set()
    await call.message.edit_text("✅ আপনার পার্সোনাল নম্বরটি লিখুন:")
    await call.answer()

@dp.message_handler(state=Form.waiting_for_withdraw_num)
async def withdraw_final(message: types.Message, state: FSMContext):
    data = await state.get_data(); uid = str(message.from_user.id)
    u = fb_get(f"users/{uid}"); amount = u['balance']
    fb_update(f"users/{uid}", {"balance": 0.0, "total_withdrawn": u.get('total_withdrawn', 0) + amount})
    await bot.send_message(ADMIN_ID, f"💸 <b>উইথড্র রিকোয়েস্ট!</b>\nআইডি: {uid}\nপরিমাণ: {amount} টাকা\nমেথড: {data['m']}\nনম্বর: {message.text}")
    await message.answer(f"✅ আবেদন জমা হয়েছে। ২৪ ঘণ্টার মধ্যে পেমেন্ট পাবেন।", reply_markup=main_menu())
    await state.finish()

if __name__ == '__main__':
    keep_alive()
    executor.start_polling(dp, skip_updates=True)
