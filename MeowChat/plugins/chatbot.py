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
        return await message.reply_text("❌ This works only in groups")

    # Admin check
    if not await admin_check(message):
        return await message.reply_text("❌ You are not admin")

    current = await is_enabled(chat_id)
    new = not current

    await col.update_one(
        {"chat_id": chat_id},
        {"$set": {"enabled": new}},
        upsert=True,
    )

    status = "ON ✅" if new else "OFF ❌"
    await message.reply_text(f"🤖 Chatbot is now {status}")

# ================== MAIN CHATBOT ==================

@app.on_message(filters.text & ~filters.command(["chatbot"]))
async def chatbot_reply(client, message: Message):
    chat_id = message.chat.id
    chat_type = message.chat.type

    # Prevent replying to other bots or oneself to avoid infinite loops
    if message.from_user and (message.from_user.is_bot or message.from_user.is_self):
        return

    # Only reply if private chat OR if chatbot is enabled in group
    is_private = chat_type == enums.ChatType.PRIVATE
    if not is_private:
        if not await is_enabled(chat_id):
            return

    if not message.text:
        return

    # ================== API CALL ==================

    final_text = f"{PROMPT}\nUser: {message.text}"
    
    # We send both formats so it is compatible with both the custom panel endpoint and direct upstream endpoint
    payload = {
        "message": final_text,
        "messages": [{"role": "user", "content": final_text}]
    }

    try:
        headers = {
            "Content-Type": "application/json"
        }
        if API_KEY:
            headers["x-api-key"] = API_KEY

        async with httpx.AsyncClient(timeout=10) as clientx:
            res = await clientx.post(API_URL, json=payload, headers=headers)

            if res.status_code == 200:
                data = res.json()
                reply = (
                    data.get("reply")
                    or data.get("response")
                    or data.get("message")
                    or (isinstance(data, dict) and data.get("messages") and isinstance(data["messages"], list) and data["messages"][-1].get("content"))
                    or "🤖 No response"
                )
            else:
                try:
                    err_data = res.json()
                    err_msg = err_data.get("error") or err_data.get("message") or f"Status {res.status_code}"
                except Exception:
                    err_msg = res.text or f"Status {res.status_code}"
                reply = f"⚠️ API Error: {err_msg}"

        await message.reply_text(reply)

    except Exception as e:
        print("Chatbot Error:", e)
        await message.reply_text(f"⚠️ Something went wrong: {str(e)}")

