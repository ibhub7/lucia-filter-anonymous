import re
import io
import math
import random
import string
import aiohttp
import asyncio
import hashlib
import requests
from info import *
from utils import *
from logging_helper import LOGGER
from typing import Optional
from datetime import datetime
from pyrogram import Client, filters
from database.ia_filterdb import save_file
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery


CAPTION_LANGUAGES = ["Bhojpuri", "Hindi", "Bengali", "Tamil", "English", "Bangla", "Telugu", "Malayalam", "Kannada", "Marathi", "Punjabi", "Bengoli", "Gujrati", "Korean", "Gujarati", "Spanish", "French", "German", "Chinese", "Arabic", "Portuguese", "Russian", "Japanese", "Odia", "Assamese", "Urdu"]

SILENTX_UPDATE_CAPTION = """𝖭𝖤𝖶 𝖥𝖨𝖫𝖤 𝖠𝖣𝖣𝖤𝖣 ✅

{} #{}
📺 𝖥𝗈𝗋𝗆𝖺𝗍 - {}
🔰 𝖰𝗎𝖺𝗅𝗂𝗍𝗒 - {}
🔈 𝖠𝗎𝖽𝗂𝗈 - {}
🖇️ <a href="{}">𝖨𝖬𝖣𝖡 𝖨𝗇𝖿𝗈</a>
"""

notified_movies = set()
user_reactions = {}
reaction_counts = {}

media_filter = filters.document | filters.video | filters.audio

@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    """Media Handler"""
    for file_type in ("document", "video", "audio"):
        media = getattr(message, file_type, None)
        if media is not None:
            break
    else:
        return
    media.file_type = file_type
    media.caption = message.caption
    success, silentxbotz = await save_file(media)
    try:  
        if success and silentxbotz == 1 and await get_status(bot.me.id):            
            await send_movie_update(bot, file_name=media.file_name, caption=media.caption)
    except Exception as e:
        LOGGER.error(f"Error In Movie Update - {e}")
        pass

async def send_movie_update(bot, file_name, caption):
    try:
        file_name = await movie_name_format(file_name)
        caption = await movie_name_format(caption)
        year_match = re.search(r"\b(19|20)\d{2}\b", caption)
        year = year_match.group(0) if year_match else None      
        season_match = re.search(r"(?i)(?:s|season)0*(\d{1,2})", caption) or re.search(r"(?i)(?:s|season)0*(\d{1,2})", file_name)
        if year:
            file_name = file_name[:file_name.find(year) + 4]
        elif season_match:
            season = season_match.group(1)
            file_name = file_name[:file_name.find(season) + 1]
        quality = await get_qualities(caption) or "HDRip"
        pixel = await get_pixels(caption) or "720p"
        language = ", ".join([lang for lang in CAPTION_LANGUAGES if lang.lower() in caption.lower()]) or "Not Idea"
        if file_name in notified_movies:
            return 
        notified_movies.add(file_name)
        imdb_data = await get_imdb_details(file_name)
        title = imdb_data.get("title", file_name)
        imdb_link = imdb_data.get("url", "") if imdb_data else ""
        kind = imdb_data.get("kind", "").strip().upper().replace(" ", "_") if imdb_data else ""
        poster = await fetch_movie_poster(title, year)        
        search_movie = file_name.replace(" ", "-")
        unique_id = generate_unique_id(search_movie)
        reaction_counts[unique_id] = {"❤️": 0, "👍": 0, "👎": 0, "🔥": 0}
        user_reactions[unique_id] = {}        
        full_caption = SILENTX_UPDATE_CAPTION.format(file_name, kind, quality, pixel, language, imdb_link)
        buttons = [[
            InlineKeyboardButton(f"❤️ {reaction_counts[unique_id]['❤️']}", callback_data=f"r_{unique_id}_{search_movie}_heart"),                
            InlineKeyboardButton(f"👍 {reaction_counts[unique_id]['👍']}", callback_data=f"r_{unique_id}_{search_movie}_like"),
            InlineKeyboardButton(f"👎 {reaction_counts[unique_id]['👎']}", callback_data=f"r_{unique_id}_{search_movie}_dislike"),
            InlineKeyboardButton(f"🔥 {reaction_counts[unique_id]['🔥']}", callback_data=f"r_{unique_id}_{search_movie}_fire")
        ],[
            InlineKeyboardButton('Get File', url=f'https://telegram.me/{temp.U_NAME}?start=getfile-{search_movie}')
        ]]
        if poster:
            photo_file = io.BytesIO(poster)
            photo_file.name = await generate_random_filename()
            await bot.send_photo(chat_id=MOVIE_UPDATE_CHANNEL, photo=photo_file, caption=full_caption, reply_markup=InlineKeyboardMarkup(buttons))    
        else:
            image_url = "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"   
            await bot.send_photo(chat_id=MOVIE_UPDATE_CHANNEL, photo=image_url, caption=full_caption, reply_markup=InlineKeyboardMarkup(buttons))                
    except Exception as e:
        LOGGER.error(f"Error in send_movie_update: {e}")

@Client.on_callback_query(filters.regex(r"^r_"))
async def reaction_handler(client, query):
    try:
        data = query.data.split("_")
        if len(data) != 4:
            return        
        unique_id = data[1]
        search_movie = data[2]
        new_reaction = data[3]
        user_id = query.from_user.id
        emoji_map = {"heart": "❤️", "like": "👍", "dislike": "👎", "fire": "🔥"}
        if new_reaction not in emoji_map:
            return
        new_emoji = emoji_map[new_reaction]       
        if unique_id not in reaction_counts:
            return
        if user_id in user_reactions[unique_id]:
            old_emoji = user_reactions[unique_id][user_id]
            if old_emoji == new_emoji:
                return 
            else:
                reaction_counts[unique_id][old_emoji] -= 1
        user_reactions[unique_id][user_id] = new_emoji
        reaction_counts[unique_id][new_emoji] += 1
        updated_buttons = [[
            InlineKeyboardButton(f"❤️ {reaction_counts[unique_id]['❤️']}", callback_data=f"r_{unique_id}_{search_movie}_heart"),                
            InlineKeyboardButton(f"👍 {reaction_counts[unique_id]['👍']}", callback_data=f"r_{unique_id}_{search_movie}_like"),
            InlineKeyboardButton(f"👎 {reaction_counts[unique_id]['👎']}", callback_data=f"r_{unique_id}_{search_movie}_dislike"),
            InlineKeyboardButton(f"🔥 {reaction_counts[unique_id]['🔥']}", callback_data=f"r_{unique_id}_{search_movie}_fire")
        ],[
            InlineKeyboardButton('Get File', url=f'https://telegram.me/{temp.U_NAME}?start=getfile-{search_movie}')
        ]]
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(updated_buttons))
    except Exception as e:
        LOGGER.error("Reaction error:", e)
        
async def get_imdb_details(name):
    try:
        formatted_name = await movie_name_format(name)
        imdb = await get_poster(formatted_name)
        if not imdb:
            return {}
        return {
            "title": imdb.get("title", formatted_name),
            "kind": imdb.get("kind", "Movie"),
            "year": imdb.get("year"),
            "url" : imdb.get("url")
        }
    except Exception as e:
        LOGGER.error(f"IMDB fetch error: {e}")
        return {}

async def fetch_movie_poster(title: str, year: Optional[int] = None) -> Optional[bytes]:
    base_url = "https://image.silentxbotz.tech/api/v2/poster"
    params = {"title": title.strip()}
    if year is not None:
        params["year"] = str(year)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as response:
                if response.status != 200:
                    response_text = await response.text()
                    raise ValueError(f"Failed to fetch metadata: HTTP {response.status}")
                data = await response.json()
            backdrops_by_lang = data.get("backdrops", {}).get("by_language", {})
            preferred_langs = []
            if "original_language" in data:
                preferred_langs.append(data["original_language"])
            preferred_langs.extend(["en", "unknown"])
            for lang in preferred_langs:
                backdrops = backdrops_by_lang.get(lang, [])
                if backdrops:
                    best_backdrop_url = backdrops[0]["url"]
                    async with session.get(best_backdrop_url, timeout=aiohttp.ClientTimeout(total=20)) as img_resp:
                        if img_resp.status == 200:
                            return await img_resp.read()
                        else:
                            raise ValueError(f"Failed To Fetch Backdrop Image: HTTP {img_resp.status}")
            raise ValueError("No Language-Specific Backdrops Found")
    except aiohttp.ClientError as e:
        LOGGER.error(f"Network Error Occurred: {str(e)}")
    except asyncio.TimeoutError:
        LOGGER.error("Request Timed Out!")
    except ValueError as e:
        LOGGER.error(str(e))
    except Exception as e:
        LOGGER.error(f"Unexpected Error: {str(e)}")
    return None

def generate_unique_id(movie_name):
    return hashlib.md5(movie_name.encode('utf-8')).hexdigest()[:5]

async def get_qualities(text):
    qualities = ["ORG", "org", "hdcam", "HDCAM", "HQ", "hq", "HDRip", "hdrip", 
                 "camrip", "WEB-DL", "CAMRip", "hdtc", "predvd", "DVDscr", "dvdscr", 
                 "dvdrip", "HDTC", "dvdscreen", "HDTS", "hdts"]
    return ", ".join([q for q in qualities if q.lower() in text.lower()])


async def get_pixels(caption):
    pixels = ["480p", "480p HEVC", "720p", "720p HEVC", "1080p", "1080p HEVC", "2160p" "2K", "4K"]
    return ", ".join([p for p in pixels if p.lower() in caption.lower()])


async def movie_name_format(file_name):
  clean_filename = re.sub(r'http\S+', '', re.sub(r'@\w+|#\w+', '', file_name).replace('_', ' ').replace('[', '').replace(']', '').replace('(', '').replace(')', '').replace('{', '').replace('}', '').replace('.', ' ').replace('@', '').replace(':', '').replace(';', '').replace("'", '').replace('-', '').replace('!', '')).strip()
  return clean_filename


async def generate_random_filename(extension=".jpg"):
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d%H%M%S")
    sin_value = abs(math.sin(int(timestamp[-5:]))) 
    random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))   
    filename = f"silentxbotz_{int(sin_value*10000)}_{random_part}{extension}"
    return filename
