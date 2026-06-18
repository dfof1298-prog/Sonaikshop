# database.py - SONIK BOT - COMPLETE VERSION
import os
import datetime
import random
import string
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = "mongodb://mongo:PLYxmxgNgAaBGpZsNtSfDdyOitMaQSfE@thomas.proxy.rlwy.net:42086"
DB_NAME = "sonik_bot"

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# Collections
users_col = db["users"]
proxies_col = db["proxies"]
cards_col = db["cards"]
star_orders_col = db["star_orders"]
sites_col = db["sites"]
stats_col = db["stats"]

# File for sites
SITES_FILE = "sites.txt"


async def init_db():
    try:
        await users_col.create_index("user_id", unique=True)
        await proxies_col.create_index([("user_id", 1), ("proxy_url", 1)])
        await cards_col.create_index("created_at")
        await star_orders_col.create_index("order_id", unique=True)
        await sites_col.create_index("user_id", unique=True)
        
        if await stats_col.count_documents({"_id": "stars_earned"}) == 0:
            await stats_col.insert_one({"_id": "stars_earned", "total": 0})
        
        print("✅ Database connected!")
    except Exception as e:
        print(f"⚠️ DB warning: {e}")


# ============ SITES FROM FILE ============
async def load_sites_from_file():
    sites = []
    if os.path.exists(SITES_FILE):
        try:
            with open(SITES_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        sites.append(line)
        except:
            pass
    return list(dict.fromkeys(sites))


async def save_sites_to_file(sites):
    try:
        with open(SITES_FILE, "w", encoding="utf-8") as f:
            for site in sites:
                f.write(f"{site}\n")
        return True
    except:
        return False


async def get_global_sites():
    return await load_sites_from_file()


async def add_global_site(site: str) -> bool:
    sites = await load_sites_from_file()
    if site in sites:
        return False
    sites.append(site)
    return await save_sites_to_file(sites)


async def add_global_sites_batch(sites: list) -> int:
    existing = await load_sites_from_file()
    new_sites = []
    for site in sites:
        if site not in existing and site not in new_sites:
            new_sites.append(site)
    if new_sites:
        existing.extend(new_sites)
        await save_sites_to_file(existing)
    return len(new_sites)


async def remove_global_site(site: str) -> bool:
    sites = await load_sites_from_file()
    if site not in sites:
        return False
    sites.remove(site)
    return await save_sites_to_file(sites)


async def clear_all_global_sites() -> int:
    sites = await load_sites_from_file()
    count = len(sites)
    await save_sites_to_file([])
    return count


async def get_all_global_sites_with_price():
    sites = await load_sites_from_file()
    return [{"site": s, "price_range": "No filter"} for s in sites]


async def get_total_sites_count() -> int:
    sites = await load_sites_from_file()
    return len(sites)


# ============ USER ============
async def ensure_user(user_id: int):
    existing = await users_col.find_one({"user_id": user_id})
    if not existing:
        await users_col.insert_one({
            "user_id": user_id,
            "subscription_plan": None,
            "subscription_end": None,
            "subscription_hours": 0,
            "banned": False,
            "banned_by": None,
            "banned_at": None,
            "last_seen": datetime.datetime.utcnow(),
            "created_at": datetime.datetime.utcnow(),
            "plan": "Bronze"
        })
    else:
        await users_col.update_one(
            {"user_id": user_id},
            {"$set": {"last_seen": datetime.datetime.utcnow()}}
        )


async def get_user_subscription(user_id: int) -> dict:
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        await ensure_user(user_id)
        user = await users_col.find_one({"user_id": user_id})
    end = user.get("subscription_end")
    if end and datetime.datetime.utcnow() < end:
        remaining = (end - datetime.datetime.utcnow()).total_seconds() / 3600
        return {
            "plan": user.get("subscription_plan"),
            "end": end,
            "is_active": True,
            "remaining_hours": round(remaining, 2)
        }
    return {"plan": None, "end": None, "is_active": False, "remaining_hours": 0}


async def set_user_subscription(user_id: int, plan: str, hours: int):
    expiry = datetime.datetime.utcnow() + datetime.timedelta(hours=hours)
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"subscription_plan": plan, "subscription_end": expiry, "subscription_hours": hours, "plan": plan}},
        upsert=True
    )


async def is_user_subscribed(user_id: int) -> bool:
    sub = await get_user_subscription(user_id)
    return sub["is_active"]


async def is_banned_user(user_id: int) -> bool:
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        return False
    return user.get("banned", False)


async def ban_user(user_id: int, banned_by: int = None):
    await users_col.update_one(
        {"user_id": user_id}, 
        {"$set": {"banned": True, "banned_by": banned_by, "banned_at": datetime.datetime.utcnow()}}
    )


async def unban_user(user_id: int) -> bool:
    """Unban a user - returns True if user was unbanned, False if not found or already unbanned"""
    try:
        # First check if user exists
        user = await users_col.find_one({"user_id": user_id})
        if not user:
            print(f"⚠️ User {user_id} not found in database")
            return False
        
        # Check if user is actually banned
        if not user.get("banned", False):
            print(f"⚠️ User {user_id} is not banned")
            return True  # Return True because they're already not banned
        
        # Update user to unban
        result = await users_col.update_one(
            {"user_id": user_id},
            {"$set": {"banned": False, "banned_by": None, "banned_at": None}}
        )
        
        print(f"✅ User {user_id} unbanned successfully, modified: {result.modified_count}")
        return result.modified_count > 0
    except Exception as e:
        print(f"❌ Error unbanning user {user_id}: {e}")
        return False


async def get_all_users():
    cursor = users_col.find({}).sort("last_seen", -1)
    return await cursor.to_list(length=1000)


async def update_last_seen(user_id: int):
    await users_col.update_one({"user_id": user_id}, {"$set": {"last_seen": datetime.datetime.utcnow()}})


async def get_user_plan(user_id: int) -> str:
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        await ensure_user(user_id)
        user = await users_col.find_one({"user_id": user_id})
    end = user.get("subscription_end")
    if end and datetime.datetime.utcnow() < end:
        return user.get("subscription_plan", "Bronze")
    return "Bronze"


async def is_premium_user(user_id: int) -> bool:
    return await is_user_subscribed(user_id)


async def get_all_premium_users():
    now = datetime.datetime.utcnow()
    cursor = users_col.find({"subscription_end": {"$gt": now}})
    return await cursor.to_list(length=1000)


async def get_total_users() -> int:
    return await users_col.count_documents({})


async def get_premium_count() -> int:
    now = datetime.datetime.utcnow()
    return await users_col.count_documents({"subscription_end": {"$gt": now}})


async def cleanup_expired_subscriptions():
    now = datetime.datetime.utcnow()
    result = await users_col.update_many(
        {"subscription_end": {"$lt": now}},
        {"$set": {"subscription_plan": None, "subscription_end": None, "subscription_hours": 0, "plan": "Bronze"}}
    )
    return result.modified_count


# ============ PROXY ============
async def add_proxy_db(user_id: int, proxy_data: dict):
    await proxies_col.insert_one({
        "user_id": user_id,
        "ip": proxy_data.get("ip"),
        "port": proxy_data.get("port"),
        "username": proxy_data.get("username"),
        "password": proxy_data.get("password"),
        "proxy_url": proxy_data.get("proxy_url"),
        "proxy_type": proxy_data.get("type", "http"),
        "added_at": datetime.datetime.utcnow()
    })


async def get_all_user_proxies(user_id: int):
    cursor = proxies_col.find({"user_id": user_id}).sort("added_at", 1)
    return await cursor.to_list(length=1000)


async def get_proxy_count(user_id: int) -> int:
    return await proxies_col.count_documents({"user_id": user_id})


async def get_random_proxy(user_id: int):
    proxies = await get_all_user_proxies(user_id)
    return random.choice(proxies) if proxies else None


async def remove_proxy_by_index(user_id: int, index: int):
    proxies = await get_all_user_proxies(user_id)
    if 0 <= index < len(proxies):
        proxy = proxies[index]
        await proxies_col.delete_one({"_id": proxy["_id"]})
        return proxy
    return None


async def remove_proxy_by_url(user_id: int, proxy_url: str):
    result = await proxies_col.delete_one({"user_id": user_id, "proxy_url": proxy_url})
    return result.deleted_count > 0


async def clear_all_proxies(user_id: int) -> int:
    result = await proxies_col.delete_many({"user_id": user_id})
    return result.deleted_count


# ============ CARDS ============
async def save_card_to_db(card: str, status: str, response: str, gateway: str, price: str):
    await cards_col.insert_one({
        "card": card, "status": status, "response": response[:200],
        "gateway": gateway, "price": price, "created_at": datetime.datetime.utcnow()
    })


async def get_total_cards_count() -> int:
    return await cards_col.count_documents({})


async def get_charged_count() -> int:
    return await cards_col.count_documents({"status": "CHARGED"})


async def get_approved_count() -> int:
    return await cards_col.count_documents({"status": "APPROVED"})


# ============ STAR ORDERS ============
def generate_order_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))


async def create_star_order(user_id: int, plan: str, hours: int, price_stars: int):
    order_id = generate_order_id()
    await star_orders_col.insert_one({
        "order_id": order_id,
        "user_id": user_id,
        "plan": plan,
        "hours": hours,
        "price_stars": price_stars,
        "status": "pending",
        "created_at": datetime.datetime.utcnow()
    })
    return order_id


async def get_star_order(order_id: str):
    return await star_orders_col.find_one({"order_id": order_id})


async def get_user_pending_order(user_id: int):
    return await star_orders_col.find_one({"user_id": user_id, "status": "pending"})


async def confirm_star_payment(order_id: str, telegram_payment_id: str, provider_payment_charge_id: str):
    order = await get_star_order(order_id)
    if not order:
        return False
    await star_orders_col.update_one(
        {"order_id": order_id},
        {"$set": {"status": "paid", "telegram_payment_id": telegram_payment_id, "paid_at": datetime.datetime.utcnow()}}
    )
    await set_user_subscription(order["user_id"], order["plan"], order["hours"])
    
    await stats_col.update_one(
        {"_id": "stars_earned"},
        {"$inc": {"total": order["price_stars"]}},
        upsert=True
    )
    return True


async def get_total_stars_earned():
    stats = await stats_col.find_one({"_id": "stars_earned"})
    return stats["total"] if stats else 0


# ============ FORCE JOIN ============
async def mark_user_joined(user_id: int):
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"joined_verified": True}},
        upsert=True
    )


async def is_user_marked_joined(user_id: int) -> bool:
    user = await users_col.find_one({"user_id": user_id})
    return user.get("joined_verified", False) if user else False


async def remove_joined_mark(user_id: int):
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"joined_verified": False}},
        upsert=True
    )