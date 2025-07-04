import logging
from struct import pack
import re
import base64
from typing import Dict, List, Optional, Tuple
from pyrogram.file_id import FileId
from pymongo.errors import DuplicateKeyError
from umongo import Instance, Document, fields
from motor.motor_asyncio import AsyncIOMotorClient
from marshmallow.exceptions import ValidationError
from info import *
from utils import get_settings, save_group_settings
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

processed_movies = set()

_db_stats_cache = {
    "timestamp": None,
    "primary_size": 0
}

# Initialize MongoDB clients with error handling
try:
    client = AsyncIOMotorClient(DATABASE_URI)
    db = client[DATABASE_NAME]
    instance = Instance.from_db(db)

    client2 = AsyncIOMotorClient(DATABASE_URI2)
    db2 = client2[DATABASE_NAME]
    instance2 = Instance.from_db(db2)
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise


def unpack_new_file_id(file_id: str) -> Tuple[str, Optional[str]]:
    """Extract file_id and file_ref from Telegram file_id"""
    try:
        decoded = FileId.decode(file_id)
        return str(decoded), decoded.file_reference
    except Exception as e:
        logger.error(f"Error unpacking file_id {file_id}: {e}")
        return file_id, None


@instance.register
class Media(Document):
    file_id = fields.StrField(attribute='_id')
    file_ref = fields.StrField(allow_none=True)
    file_name = fields.StrField(required=True)
    file_size = fields.IntField(required=True)
    file_type = fields.StrField(allow_none=True)
    mime_type = fields.StrField(allow_none=True)
    caption = fields.StrField(allow_none=True)

    class Meta:
        indexes = ('$file_name',)
        collection_name = COLLECTION_NAME


# Media2 is identical to Media but registered with instance2
Media2 = Media.register(instance2)


async def check_db_size(db) -> float:
    """Check and cache database size with improved caching logic"""
    try:
        now = datetime.utcnow()
        cache_valid = (_db_stats_cache["timestamp"] and 
                      (now - _db_stats_cache["timestamp"]) <= timedelta(minutes=10))
        
        if cache_valid and _db_stats_cache["primary_size"] < (512 - 80):
            logger.info(f"📊 DB Size (cached): {_db_stats_cache['primary_size']:.2f} MB")
            return _db_stats_cache["primary_size"]

        stats = await db.command("dbstats")
        db_size_mb = stats["dataSize"] / (1024 * 1024)
        
        _db_stats_cache.update({
            "primary_size": db_size_mb,
            "timestamp": now
        })
        
        logger.info(f"📊 DB Size (updated): {db_size_mb:.2f} MB")
        return db_size_mb
    except Exception as e:
        logger.error(f"Error checking database size: {e}")
        return 0


async def save_file(media) -> Tuple[bool, int]:
    """Save media file with improved error handling"""
    file_id, file_ref = unpack_new_file_id(media.file_id)
    
    # Safer file name cleaning
    file_name = re.sub(r"[\s@_\-\.\+\#\$%^&*\(\)!~`,;:'\"?/<>=\[\]\{\}\\\|]+", " ", str(media.file_name))
    file_name = re.sub(r"\s{2,}", " ", file_name).strip()
    
    saveMedia = Media
    if MULTIPLE_DB:
        exists = await Media.count_documents({'file_id': file_id}, limit=1)
        if exists:
            logger.warning(f'{file_name} is already saved in primary database!')
            return False, 0
        
        try:
            primary_db_size = await check_db_size(db)
            if primary_db_size >= 432:  # 512 - 80 MB left
                logger.info("Primary database is low on space. Switching to secondary db.")
                saveMedia = Media2
        except Exception as e:
            logger.error(f"Error checking primary DB size: {e}")
            saveMedia = Media

    try:
        file = saveMedia(
            file_id=file_id,
            file_ref=file_ref,
            file_name=file_name,
            file_size=media.file_size,
            file_type=media.file_type,
            mime_type=media.mime_type,
            caption=media.caption.html if media.caption else None,
        )
        await file.commit()
        logger.info(f'{file_name} saved successfully in {"secondary" if saveMedia==Media2 else "primary"} database')
        return True, 1
    except ValidationError as e:
        logger.error(f'Validation error while saving file: {e}')
        return False, 2
    except DuplicateKeyError:
        logger.warning(f'{file_name} is already saved in selected database')
        return False, 0
    except Exception as e:
        logger.error(f'Unexpected error saving file: {e}')
        return False, 3


async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0, filter=False):
    """Search files with safer regex compilation and improved pagination"""
    if chat_id is not None:
        settings = await get_settings(int(chat_id))
        max_results = 10 if settings.get('max_btn', False) else int(MAX_B_TN)

    query = query.strip()
    
    # Safer regex pattern construction
    if not query:
        raw_pattern = '.'
    else:
        raw_pattern = re.escape(query)
        if ' ' in query:
            raw_pattern = raw_pattern.replace(r'\ ', r'.*[\s\.\+\-_()]')
        else:
            raw_pattern = rf'(\b|[\.\+\-_]){raw_pattern}(\b|[\.\+\-_])'

    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except re.error as e:
        logger.error(f"Invalid regex pattern: {raw_pattern} - {e}")
        return [], '', 0

    filter_query = {'$or': [{'file_name': regex}]}
    if USE_CAPTION_FILTER:
        filter_query['$or'].append({'caption': regex})
    if file_type:
        filter_query['file_type'] = file_type

    try:
        total_results = await Media.count_documents(filter_query)
        if MULTIPLE_DB:
            total_results += await Media2.count_documents(filter_query)

        max_results = max_results + 1 if max_results % 2 != 0 else max_results
        logger.info(f"Using max_results={max_results}")

        cursor1 = Media.find(filter_query).sort('$natural', -1).skip(offset).limit(max_results)
        files1 = await cursor1.to_list(length=max_results)

        files = files1
        if MULTIPLE_DB and len(files1) < max_results:
            cursor2 = Media2.find(filter_query).sort('$natural', -1).skip(offset).limit(max_results - len(files1))
            files2 = await cursor2.to_list(length=max_results - len(files1))
            files = files1 + files2

        next_offset = offset + len(files)
        if next_offset >= total_results:
            next_offset = ''

        return files, next_offset, total_results
    except Exception as e:
        logger.error(f"Error during search: {e}")
        return [], '', 0





async def get_bad_files(query, file_type=None):
    query = query.strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s\.\+\-_()]')
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except:
        return []
    if USE_CAPTION_FILTER:
        filter = {'$or': [{'file_name': regex}, {'caption': regex}]}
    else:
        filter = {'file_name': regex}
    if file_type:
        filter['file_type'] = file_type
    cursor1 = Media.find(filter).sort('$natural', -1)
    files1 = await cursor1.to_list(length=(await Media.count_documents(filter)))
    if MULTIPLE_DB:
        cursor2 = Media2.find(filter).sort('$natural', -1)
        files2 = await cursor2.to_list(length=(await Media2.count_documents(filter)))
        files = files1 + files2
    else:
        files = files1
    total_results = len(files)
    return files, total_results
    

async def get_file_details(query):
    filter = {'file_id': query}
    cursor = Media.find(filter)
    filedetails = await cursor.to_list(length=1)
    if not filedetails:
        cursor2 = Media2.find(filter)
        filedetails = await cursor2.to_list(length=1)
    return filedetails


def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0
    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0
            r += bytes([i])
    return base64.urlsafe_b64encode(r).decode().rstrip("=")

def encode_file_ref(file_ref: bytes) -> str:
    return base64.urlsafe_b64encode(file_ref).decode().rstrip("=")

def unpack_new_file_id(new_file_id):
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )
    file_ref = encode_file_ref(decoded.file_reference)
    return file_id, file_ref

async def siletxbotz_fetch_media(limit: int) -> List[dict]:
    try:
        if MULTIPLE_DB:
            db_size = await check_db_size(Media)
            if db_size > MONGODB_SIZE_LIMIT:
                cursor = Media2.find().sort("$natural", -1).limit(limit)
                files = await cursor.to_list(length=limit)
                return files
        cursor = Media.find().sort("$natural", -1).limit(limit)
        files = await cursor.to_list(length=limit)
        return files
    except Exception as e:
        logger.error(f"Error in siletxbotz_fetch_media: {e}")
        return []

async def silentxbotz_clean_title(filename: str, is_series: bool = False) -> str:
    try:
        year_match = re.search(r"^(.*?(\d{4}|\(\d{4}\)))", filename, re.IGNORECASE)
        if year_match:
            title = year_match.group(1).replace('(', '').replace(')', '') 
            return re.sub(r"[._\-\[\]@()]+", " ", title).strip().title()
        if is_series:
            season_match = re.search(r"(.*?)(?:S(\d{1,2})|Season\s*(\d+)|Season(\d+))(?:\s*Combined)?", filename, re.IGNORECASE)
            if season_match:
                title = season_match.group(1).strip()
                season = season_match.group(2) or season_match.group(3) or season_match.group(4)
                title = re.sub(r"[._\-\[\]@()]+", " ", title).strip().title()
                return f"{title} S{int(season):02}"
        return re.sub(r"[._\-\[\]@()]+", " ", filename).strip().title()
    except Exception as e:
        logger.error(f"Error in truncate_title: {e}")
        return filename
        
async def siletxbotz_get_movies(limit: int = 20) -> List[str]:
    try:
        cursor = await siletxbotz_fetch_media(limit * 2)
        results = set()
        pattern = r"(?:s\d{1,2}|season\s*\d+|season\d+)(?:\s*combined)?(?:e\d{1,2}|episode\s*\d+)?\b"
        for file in cursor:
            file_name = getattr(file, "file_name", "")
            caption = getattr(file, "caption", "")
            if not (re.search(pattern, file_name, re.IGNORECASE) or re.search(pattern, caption, re.IGNORECASE)):
                title = await silentxbotz_clean_title(file_name)
                results.add(title)
            if len(results) >= limit:
                break
        return sorted(list(results))[:limit]
    except Exception as e:
        logger.error(f"Error in siletxbotz_get_movies: {e}")
        return []

async def siletxbotz_get_series(limit: int = 30) -> Dict[str, List[int]]:
    try:
        cursor = await siletxbotz_fetch_media(limit * 5)
        grouped = defaultdict(list)
        pattern = r"(.*?)(?:S(\d{1,2})|Season\s*(\d+)|Season(\d+))(?:\s*Combined)?(?:E(\d{1,2})|Episode\s*(\d+))?\b"
        for file in cursor:
            file_name = getattr(file, "file_name", "")
            caption = getattr(file, "caption", "")
            match = None
            if file_name:
                match = re.search(pattern, file_name, re.IGNORECASE)
            if not match and caption:
                match = re.search(pattern, caption, re.IGNORECASE)
            if match:
                title = await silentxbotz_clean_title(match.group(1), is_series=True)
                season = int(match.group(2) or match.group(3) or match.group(4))
                grouped[title].append(season)
        return {title: sorted(set(seasons))[:10] for title, seasons in grouped.items() if seasons}
    except Exception as e:
        logger.error(f"Error in siletxbotz_get_series: {e}")
        return []
