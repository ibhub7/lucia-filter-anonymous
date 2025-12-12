import time
import asyncio
from pyrogram import enums
from logging_helper import LOGGER 
from database.users_chats_db import db
from pyrogram.errors import UserNotParticipant, ChatAdminRequired

CHANNEL_CACHE = {}
CACHE_TTL = 3600


async def is_req_subscribed(bot, query, chnl):
    if await db.find_join_req(query.from_user.id, chnl):
        return True
    try:
        user = await bot.get_chat_member(chnl, query.from_user.id)
        if user.status != enums.ChatMemberStatus.BANNED:
            return True
    except UserNotParticipant:
        pass
    except Exception as e:
        LOGGER.error(e)
    return False

async def is_subscribed(bot, user_id, channel_id):
    try:
        user = await bot.get_chat_member(channel_id, user_id)
    except UserNotParticipant:
        pass
    except Exception as e:
        pass
    else:
        if user.status != enums.ChatMemberStatus.BANNED:
            return True
    return False
    
async def get_channel_details(client, chat_id, is_req_channel=False):
    current_time = time.time()
    if chat_id in CHANNEL_CACHE:
        cached_data = CHANNEL_CACHE[chat_id]
        if current_time - cached_data['timestamp'] < CACHE_TTL:
            return cached_data
    try:
        chat = await client.get_chat(chat_id)
        title = chat.title or "Update Channel"
    except Exception as e:
        LOGGER.error(f"Error fetching chat {chat_id}: {e}")
        title = "Update Channel"
    try:
        if is_req_channel:
             invite_link_obj = await client.create_chat_invite_link(chat_id, creates_join_request=True)
        else:
             invite_link_obj = await client.create_chat_invite_link(chat_id)

        invite_link = invite_link_obj.invite_link
    except ChatAdminRequired:
        LOGGER.error(f"Bot Needs Admin Rights In Channel {chat_id}")
        invite_link = None
    except Exception as e:
        LOGGER.error(f"Error Creating Invite Link For {chat_id}: {e}")
        invite_link = None
    data = {'title': title, 'invite_link': invite_link, 'timestamp': current_time}
    if invite_link:
        CHANNEL_CACHE[chat_id] = data
    return data

async def check_force_subscription(client, user_id, chnl, is_req_channel, is_subscribed, is_req_subscribed, message):
    try:
        if is_req_channel:
            if await is_req_subscribed(client, message, chnl):
                return None
        else:
            if await is_subscribed(client, user_id, chnl):
                return None
        details = await get_channel_details(client, chnl, is_req_channel)
        if details['invite_link']:
             return {
                 'title': details['title'],
                 'url': details['invite_link'],
                 'chat_id': chnl
             }
        else:
            return None
    except Exception as e:
        LOGGER.error(f"Error In Subscription Check For {chnl}: {e}")
        return None
