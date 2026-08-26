"""MongoDB async helper for the Discord bot."""
import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "discord_bot")

_client = AsyncIOMotorClient(MONGO_URL)
db = _client[DB_NAME]

users = db["users"]
warns = db["warns"]
tickets = db["tickets"]
panels = db["panels"]
giveaways = db["giveaways"]
playlists = db["playlists"]
invites = db["invites"]
guild_config = db["guild_config"]

shop_items_default = [
    {"id": "sword", "name": "Spada", "price": 500, "desc": "Una spada affilata"},
    {"id": "shield", "name": "Scudo", "price": 800, "desc": "Uno scudo resistente"},
    {"id": "pickaxe", "name": "Piccone", "price": 300, "desc": "Aumenta i coin dal !mine"},
    {"id": "box", "name": "Cassa Misteriosa", "price": 1000, "desc": "Aprila con !openbox"},
    {"id": "crown", "name": "Corona", "price": 5000, "desc": "Simbolo di prestigio"},
]


async def get_user(guild_id: int, user_id: int) -> dict:
    doc = await users.find_one({"guild_id": guild_id, "user_id": user_id})
    if not doc:
        doc = {
            "guild_id": guild_id, "user_id": user_id,
            "balance": 0, "bank": 0, "xp": 0, "level": 0, "messages": 0,
            "inventory": [], "last_daily": 0, "last_work": 0, "last_mine": 0,
        }
        await users.insert_one(doc)
    return doc


async def update_user(guild_id: int, user_id: int, update: dict):
    await users.update_one({"guild_id": guild_id, "user_id": user_id}, {"$set": update}, upsert=True)


async def inc_user(guild_id: int, user_id: int, inc: dict):
    await users.update_one({"guild_id": guild_id, "user_id": user_id}, {"$inc": inc}, upsert=True)


async def get_guild_config(guild_id: int) -> dict:
    doc = await guild_config.find_one({"guild_id": guild_id})
    if not doc:
        doc = {"guild_id": guild_id}
        await guild_config.insert_one(doc)
    return doc
