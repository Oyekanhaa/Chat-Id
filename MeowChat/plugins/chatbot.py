import os
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import enums, filters
from pyrogram.types import Message

# Import variables from config
from config import API_URL, MONGO_URL, API_KEY

from MeowChat import app
from MeowChat.utils.admins import admin_check

# ================== DATABASE ==================

mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["chatbot"]
col = db["status"]

# ================== SETTINGS ==================

TRIGGER_WORDS = ["hello", "hi", "bot"]  # apne hisab se add kar

# ================== PROMPT ==================

def load_prompt():
    try:
        path = os.path.join(os.path.dirname(__file__), "prompt.txt")
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""

PROMPT = load_prompt()

# ================== STATUS ==================

async def is_enabled(chat_id: int) -> bool:
    data = await col.find_one({"chat_id": chat_id})
    return data.get("enabled", False) if data else False

# ================== TOGGLE COMMAND ==================

@app.on_message(filters.command("chatbot"))
async def toggle_chatbot(client, message: Message):
    chat_id = message.chat.id

    # Only group
    if message.chat.type not in [
        enums.ChatType.GROUP,
        enums.ChatType.SUPERGROUP,
    ]:
        return await message.reply_text("âŒ This works only in groups")

    # Admin check
    if not await admin_check(message):
        return await message.reply_text("âŒ You are not admin")

    current = await is_enabled(chat_id)
    new = not current

    await col.update_one(
        {"chat_id": chat_id},
        {"$set": {"enabled": new}},
        upsert=True,
    )

    status = "ON âœ…" if new else "OFF âŒ"
    await message.reply_text(f"ðŸ¤– Chatbot is now {status}")

# ================== MAIN CHATBOT ==================

@app.on_message(filters.text & ~filters.command(["chatbot"]))
async def chatbot_reply(client, message: Message):
    chat_id = message.chat.id

    # Only reply if enabled in group
    if message.chat.type in [
        enums.ChatType.GROUP,
        enums.ChatType.SUPERGROUP,
    ]:
        if not await is_enabled(chat_id):
            return

    if not message.text:
        return

    text = message.text.lower()

    # ================== CONDITIONS ==================

    should_reply = False

    # 1. Reply to bot message
    if message.reply_to_message:
        if (
            message.reply_to_message.from_user
            and message.reply_to_message.from_user.is_bot
        ):
            should_reply = True

    # 2. Trigger word
    if any(word in text for word in TRIGGER_WORDS):
        should_reply = True

    if not should_reply:
        return

    # ================== API CALL ==================

    final_text = f"{PROMPT}\nUser: {message.text}"
    payload = {"message": final_text}

    try:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": API_KEY
        }

        async with httpx.AsyncClient(timeout=10) as clientx:
            res = await clientx.post(API_URL, json=payload, headers=headers)

            if res.status_code == 200:
                data = res.json()
                reply = (
                    data.get("reply")
                    or data.get("response")
                    or data.get("message")
                    or "ðŸ¤– No response"
                )
            else:
                reply = "âš ï¸ API Error"

        await message.reply_text(reply)

    except Exception as e:
        print("Chatbot Error:", e)
        await message.reply_text("âš ï¸ Something went wrong")    payload = {"message": final_text}

    try:
        async with httpx.AsyncClient(timeout=10) as clientx:
            res = await clientx.post(API_URL, json=payload)

            if res.status_code == 200:
                data = res.json()
                reply = (
                    data.get("reply")
                    or data.get("response")
                    or data.get("message")
                    or "🤖 No response"
                )
            else:
                reply = "⚠️ API Error"

        await message.reply_text(reply)

    except Exception as e:
        print("Chatbot Error:", e)
        await message.reply_text("⚠️ Something went wrong")
