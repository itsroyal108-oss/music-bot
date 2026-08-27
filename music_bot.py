import os
import json
import asyncio
import urllib.parse
import urllib.request
import subprocess
import yt_dlp
from pyrogram import Client, filters, idle
from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    Message, 
    CallbackQuery
)
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped

# --- CONFIGURATION ---
API_ID = 37524365
API_HASH = "e392b8b8fb1213e15441149132854740"

BOT_TOKEN = "8584429165:AAE-LfllqArra-NVdJtpH_rrqGpP1ThuIkk"         # @BotFather se apna Bot Token yahan daalein
STRING_SESSION = "BQI8k40AZNgcMMSmqON-pijF1CCbdR0kYc1l_q2XbuJVdxHSNT1YRbmo2ESRIlQDQDa6QMLU25II5mwQsAM-olIJmxtyo6vv0rgf1cLoSXggnzgQcxsX4A_UVgk3j12eN1qJk9Byc1Ob8ZkPtbzZ_CT1ToF9Q-VSgZCeo8Crwds0HdaYtOrx1zC2mghuGvOMeHJwrvlu7KhhatBcXzhTanQkWFTItGMk3EGfK5fC6lXczcukscRirXODPxWbb5EvFj9Uwe-4MffJbdR762COWb4jWQD_1LHRp7qapG_1SkgM-3Qj_aAev-bx-mjho3UJOwrSSYWICGxzYoFMGpwS7gVT7COFbQAAAAIKAs5BAA"    # Assistant session string yahan daalein
BOT_OW6NER_ID = 6411550540                 # Apni numeric Telegram User ID yahan daalein

DATA_FILE = "playlists.json"
CHATS_FILE = "chats.json"
SETTINGS_FILE = "group_settings.json"
AUTH_FILE = "auth_users.json"
BAN_FILE = "banned.json"
CLONES_FILE = "clones.json"
UBC_FILE = "universal_broadcasts.json"
BROADCAST_FILE = "broadcasts.json"
DOWNLOAD_DIR = "downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Clients Setup
bot = Client("SpotibotMega", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user = Client("SpotibotAssistant", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
pytgcalls = PyTgCalls(user)

queues = {}

# --- STORAGE HELPERS ---
def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}

def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def register_chat(chat_id):
    chats = load_json(CHATS_FILE)
    if not isinstance(chats, list):
        chats = []
    if str(chat_id) not in chats:
        chats.append(str(chat_id))
        save_json(CHATS_FILE, chats)

def is_banned(user_id):
    banned = load_json(BAN_FILE)
    return isinstance(banned, list) and str(user_id) in banned

# --- PERMISSIONS CHECKER ---
async def is_authorized(chat, user_id):
    if user_id == BOT_OWNER_ID:
        return True
    try:
        member = await chat.get_member(user_id)
        if member.status in ["administrator", "creator"]:
            return True
    except Exception:
        pass
    auth_data = load_json(AUTH_FILE)
    chat_auth = auth_data.get(str(chat.id), [])
    return user_id in chat_auth

def parse_custom_buttons(text):
    buttons = []
    clean_text = text
    if text and "[" in text and "]" in text and "|" in text:
        lines = text.split("\n")
        new_lines = []
        row = []
        for line in lines:
            if line.strip().startswith("[") and line.strip().endswith("]") and "|" in line:
                btn_part = line.strip()[1:-1]
                b_name, b_url = btn_part.split("|", 1)
                row.append(InlineKeyboardButton(b_name.strip(), url=b_url.strip()))
                if len(row) == 2:
                    buttons.append(row)
                    row = []
            else:
                new_lines.append(line)
        if row:
            buttons.append(row)
        clean_text = "\n".join(new_lines).strip()
    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
    return clean_text, reply_markup

# --- YOUTUBE & AUDIO PROCESSING ENGINES ---
def search_yt_raw(query, limit=5):
    is_url = query.startswith("http://") or query.startswith("https://")
    search_target = query if is_url else f"ytsearch{limit}:{query}"
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(search_target, download=False)
        results = []
        if 'entries' in info:
            for entry in info['entries']:
                if entry:
                    results.append({
                        'id': entry.get('id'),
                        'url': entry.get('url'),
                        'title': entry.get('title', 'Unknown Track')[:35],
                        'duration': entry.get('duration', 0)
                    })
        elif 'id' in info:
            results.append({
                'id': info.get('id'),
                'url': info.get('url'),
                'title': info.get('title', 'Unknown Track')[:35],
                'duration': info.get('duration', 0)
            })
        return results

def download_audio_by_id(video_id, bitrate="192"):
    file_path = f"{DOWNLOAD_DIR}/{video_id}_{bitrate}.mp3"
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{DOWNLOAD_DIR}/{video_id}_{bitrate}.%(ext)s',
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': bitrate}],
        'noplaylist': True,
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
        return {
            'file_path': file_path,
            'title': info.get('title', 'Unknown Track'),
            'duration': info.get('duration', 0),
            'performer': info.get('uploader', 'Unknown Artist'),
            'id': video_id
        }

def download_video_by_id(video_id):
    file_path = f"{DOWNLOAD_DIR}/{video_id}.mp4"
    ydl_opts = {
        'format': 'best[height<=720]/bestvideo+bestaudio/best',
        'outtmpl': file_path,
        'noplaylist': True,
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
        return {
            'file_path': file_path,
            'title': info.get('title', 'Unknown Video'),
            'duration': info.get('duration', 0)
        }

def process_audio_effect(input_path, output_path, effect):
    if effect == "fast":
        cmd = f'ffmpeg -y -i "{input_path}" -filter:a "atempo=1.25" -vn "{output_path}"'
    elif effect == "slow":
        cmd = f'ffmpeg -y -i "{input_path}" -filter:a "atempo=0.85,asetrate=44100*0.9" -vn "{output_path}"'
    elif effect == "bass":
        cmd = f'ffmpeg -y -i "{input_path}" -filter:a "bass=g=10:f=110:w=0.6" -vn "{output_path}"'
    elif effect == "8d":
        cmd = f'ffmpeg -y -i "{input_path}" -filter:a "apulsator=hz=0.125" -vn "{output_path}"'
    else:
        return input_path
    subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path

def trim_audio_file(input_path, output_path, start_sec, duration_sec):
    cmd = f'ffmpeg -y -ss {start_sec} -t {duration_sec} -i "{input_path}" -c copy "{output_path}"'
    subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path

def fetch_lyrics_online(song_name):
    try:
        query = urllib.parse.quote(song_name)
        url = f"https://lrclib.net/api/get?track_name={query}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            if "plainLyrics" in data and data["plainLyrics"]:
                return data["plainLyrics"]
    except Exception:
        pass
    return "❌ ʟʏʀɪᴄꜱ ɴᴏᴛ ꜰᴏᴜɴᴅ ꜰᴏʀ ᴛʜɪꜱ ꜱᴏɴɢ."

# --- VC QUEUE HANDLER ---
async def play_next_stream(chat_id):
    if chat_id in queues and len(queues[chat_id]) > 0:
        next_song = queues[chat_id].pop(0)
        await pytgcalls.change_stream(chat_id, AudioPiped(next_song['url']))
        await bot.send_message(chat_id, f"🎶 ɴᴏᴡ ᴘʟᴀʏɪɴɢ ɪɴ ᴠᴄ:\n🔹 {next_song['title']}")
    else:
        try:
            await pytgcalls.leave_group_call(chat_id)
        except Exception:
            pass

# --- 1. USER HELP & MAIN MENUS ---
@bot.on_message(filters.command("start"))
async def start_cmd(client, message: Message):
    if is_banned(message.from_user.id):
        return
    register_chat(message.chat.id)
    btn_list = [
        [
            InlineKeyboardButton("📂 ᴍʏ ᴘʟᴀʏʟɪꜱᴛꜱ", callback_data="menu_myplaylists"),
            InlineKeyboardButton("📖 ᴜꜱᴇʀ ɢᴜɪᴅᴇ", callback_data="guide_main")
        ],
        [
            InlineKeyboardButton("📜 ᴄᴏᴍᴍᴀɴᴅꜱ", callback_data="menu_help"),
            InlineKeyboardButton("➕ ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ", url=f"https://t.me/{(await bot.get_me()).username}?startgroup=true")
        ]
    ]
    if message.from_user.id == BOT_OWNER_ID:
        btn_list.append([InlineKeyboardButton("👑 ᴏᴡɴᴇʀ ᴘᴀɴᴇʟ", callback_data="owner_panel_main")])
        
    text = (
        f"👋 ʜᴇʟʟᴏ {message.from_user.first_name}!\n\n"
        "⚡ ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ꜱᴘᴏᴛɪʙᴏᴛ ᴍᴇɢᴀ ᴍᴜꜱɪᴄ ʜᴜʙ\n"
        "ᴠᴄ ᴍᴇɪɴ ꜱᴏɴɢ ᴘʟᴀʏ ᴋᴀʀᴇɪɴ, ᴀᴜᴅɪᴏ/ᴠɪᴅᴇᴏ ᴅᴏᴡɴʟᴏᴀᴅ ᴋᴀʀᴇɪɴ, ʏᴀ ᴘʟᴀʏʟɪꜱᴛ ᴍᴀɴᴀɢᴇ ᴋᴀʀᴇɪɴ."
    )
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn_list))

@bot.on_message(filters.command(["help", "menu"]))
async def help_cmd(client, message: Message):
    if is_banned(message.from_user.id):
        return
    register_chat(message.chat.id)
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("👑 ᴏᴘᴇɴ ᴏᴡɴᴇʀ ᴘᴀɴᴇʟ", callback_data="owner_panel_main")]]) if message.from_user.id == BOT_OWNER_ID else None
    
    text = (
        "🎵 ꜱᴘᴏᴛɪʙᴏᴛ ᴍᴀɪɴ ᴍᴇɴᴜ\n\n"
        "🎧 ᴠᴏɪᴄᴇ ᴄʜᴀᴛ (ᴠᴄ) ᴄᴏɴᴛʀᴏʟꜱ\n"
        "🔹 /play <song/link> - ᴠᴄ ᴍᴇɪɴ ʟɪᴠᴇ ꜱᴏɴɢ ᴘʟᴀʏ ᴋᴀʀᴇɪɴ\n"
        "🔹 /playplylist <name> - ᴘᴏᴏʀɪ ʟɪꜱᴛ ᴠᴄ ᴍᴇɪɴ ᴄʜᴀʟᴀʏᴇɪɴ\n"
        "🔹 /pause - ᴠᴄ ꜱᴛʀᴇᴀᴍ ᴘᴀᴜꜱᴇ ᴋᴀʀᴇɪɴ\n"
        "🔹 /resume - ᴠᴄ ꜱᴛʀᴇᴀᴍ ʀᴇꜱᴜᴍᴇ ᴋᴀʀᴇɪɴ\n"
        "🔹 /skip - ꜱɪɴɢʟᴇ ꜱᴏɴɢ ꜱᴋɪᴘ ᴋᴀʀᴇɪɴ\n"
        "🔹 /skipplylist - ᴘᴏᴏʀɪ ᴘʟᴀʏʟɪꜱᴛ ꜱᴋɪᴘ ᴋᴀʀᴇɪɴ\n"
        "🔹 /stop - ᴠᴄ ʟᴇᴀᴠᴇ & ᴍᴜꜱɪᴄ ꜱᴛᴏᴘ\n\n"
        "🎭 ᴇɴᴛᴇʀᴛᴀɪɴᴍᴇɴᴛ ᴀᴜᴛʜᴏʀɪᴛʏ\n"
        "🔹 /approve entertainment - ᴍᴇᴍʙᴇʀ ᴋᴏ ᴘᴇʀᴍɪꜱꜱɪᴏɴ ᴅᴇɪɴ\n"
        "🔹 /demote entertainment - ᴘᴇʀᴍɪꜱꜱɪᴏɴ ᴡᴀᴘᴀꜱ ʟᴇɪɴ\n\n"
        "🤖 ᴄʟᴏɴᴇ ᴍᴀɴᴀɢᴇʀ\n"
        "🔹 /clone - ᴄʟᴏɴᴇ ɪɴꜰᴏ & ꜱᴜᴘᴘᴏʀᴛ ʟɪɴᴋꜱ\n\n"
        "📥 ᴅᴏᴡɴʟᴏᴀᴅᴇʀ & ᴇꜰꜰᴇᴄᴛꜱ\n"
        "🔹 /song <name> - ᴅᴏᴡɴʟᴏᴀᴅ ᴍᴘ3 ᴡɪᴛʜ ꜰɪʟᴛᴇʀꜱ\n"
        "🔹 /video <name> - ᴅᴏᴡɴʟᴏᴀᴅ 720ᴘ ᴠɪᴅᴇᴏ\n"
        "🔹 /trim <start> <dur> <song> - ʀɪɴɢᴛᴏɴᴇ ᴄᴜᴛ ᴋᴀʀᴇɪɴ\n"
        "🔹 /lyrics <song> - ʟɪᴠᴇ ʟʏʀɪᴄꜱ ᴅᴇᴋʜᴇɪɴ\n"
        "🔹 /guide - ꜱᴛᴇᴘ-ʙʏ-ꜱᴛᴇᴘ ɢᴜɪᴅᴇ ᴅᴇᴋʜᴇɪɴ\n\n"
        "📑 ᴘʟᴀʏʟɪꜱᴛ ᴍᴀɴᴀɢᴇʀ\n"
        "🔹 /makeplylist <1-5> - ɴᴇᴡ ᴘʟᴀʏʟɪꜱᴛ ꜱʟᴏᴛ\n"
        "🔹 /rename <slot> <new name> - ᴘʟᴀʏʟɪꜱᴛ ʀᴇɴᴀᴍᴇ\n"
        "🔹 /addplylist <name> <song> - ꜱᴏɴɢ ᴀᴅᴅ ᴋᴀʀᴇɪɴ\n"
        "🔹 /myplylist <name> - ꜱᴀᴠᴇᴅ ꜱᴏɴɢꜱ ᴅᴇᴋʜᴇɪɴ\n"
        "🔹 /delsong <name> - ꜱᴏɴɢ ʜᴀᴛᴀʏᴇɪɴ\n"
        "🔹 /dellist <name> - ᴘʟᴀʏʟɪꜱᴛ ᴅᴇʟᴇᴛᴇ\n"
        "🔹 /alldel - ꜱᴀᴀʀɪ ᴘʟᴀʏʟɪꜱᴛꜱ ᴅᴇʟᴇᴛᴇ"
    )
    await message.reply_text(text, reply_markup=btn)

# --- 2. EXCLUSIVE OWNER PANEL COMMANDS & GUI ---
@bot.on_message(filters.command(["owner", "ownerpanel", "adminpanel"]))
async def owner_panel_cmd(client, message: Message):
    if message.from_user.id != BOT_OWNER_ID:
        await message.reply_text("❌ ᴏɴʟʏ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ ᴄᴀɴ ᴀᴄᴄᴇꜱꜱ ᴛʜɪꜱ ᴘᴀɴᴇʟ.")
        return

    btn = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 ʙʀᴏᴀᴅᴄᴀꜱᴛ ʜᴜʙ", callback_data="owner_bc_info"),
            InlineKeyboardButton("🤖 ᴄʟᴏɴᴇ ᴍᴀɴᴀɢᴇʀ", callback_data="owner_clones_info")
        ],
        [
            InlineKeyboardButton("📊 ꜱʏꜱᴛᴇᴍ ꜱᴛᴀᴛꜱ", callback_data="owner_stats_run"),
            InlineKeyboardButton("🧹 ᴄʟᴇᴀɴ ᴄᴀᴄʜᴇ", callback_data="owner_clean_run")
        ],
        [
            InlineKeyboardButton("💾 ᴇxᴘᴏʀᴛ ʙᴀᴄᴋᴜᴘ", callback_data="owner_backup_run"),
            InlineKeyboardButton("❌ ᴄʟᴏꜱᴇ ᴘᴀɴᴇʟ", callback_data="cancel_action")
        ]
    ])
    text = (
        "👑 ꜱᴘᴏᴛɪʙᴏᴛ ꜱᴇᴄᴜʀᴇ ᴏᴡɴᴇʀ ᴘᴀɴᴇʟ\n\n"
        "ᴡᴇʟᴄᴏᴍᴇ ʙᴀᴄᴋ, ᴏᴡɴᴇʀ! ɴɪᴄʜᴇ ᴅɪʏᴇ ɢᴀʏᴇ ʙᴜᴛᴛᴏɴꜱ ꜱᴇ ᴀᴀᴘ ʙᴏᴛ ᴋᴇ ꜱᴀᴀʀᴇ ꜱʏꜱᴛᴇᴍ ᴄᴏɴᴛʀᴏʟꜱ ᴍᴀɴᴀɢᴇ ᴋᴀʀ ꜱᴀᴋᴛᴇ ʜᴀɪɴ."
    )
    await message.reply_text(text, reply_markup=btn)

# --- 3. CLONE SYSTEM ENGINE ---
@bot.on_message(filters.command("clone"))
async def clone_command(client, message: Message):
    user_id = message.from_user.id
    
    if user_id == BOT_OWNER_ID and len(message.command) > 1:
        new_token = message.command[1]
        clones = load_json(CLONES_FILE)
        if not isinstance(clones, list):
            clones = []
        if new_token not in clones:
            try:
                test_bot = Client(f"test_{new_token[:6]}", api_id=API_ID, api_hash=API_HASH, bot_token=new_token)
                await test_bot.start()
                b_name = (await test_bot.get_me()).first_name
                await test_bot.stop()
                clones.append(new_token)
                save_json(CLONES_FILE, clones)
                await message.reply_text(f"✅ ᴄʟᴏɴᴇ ʙᴏᴛ `{b_name}` ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴀᴅᴅᴇᴅ!")
            except Exception as e:
                await message.reply_text(f"❌ ɪɴᴠᴀʟɪᴅ ᴛᴏᴋᴇɴ: {str(e)}")
        else:
            await message.reply_text("⚠️ ᴛʜɪꜱ ᴄʟᴏɴᴇ ɪꜱ ᴀʟʀᴇᴀᴅʏ ʀᴇɢɪꜱᴛᴇʀᴇᴅ.")
        return

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👑 ʙᴏᴛ ᴏᴡɴᴇʀ", url="https://t.me/Roaster_Gang"),
            InlineKeyboardButton("⚡ ᴄʟᴏɴᴇ ꜱᴜᴘᴘᴏʀᴛ", url="https://t.me/PW_GROUP_LINK_Official")
        ],
        [
            InlineKeyboardButton("✨ 𝕁𝕠𝕚𝕟 ℙ𝕎 𝕆𝕗𝕗𝕚𝕔𝕚𝕒𝕝 ℂ𝕙𝕒𝕥𝕚𝕟𝕘 𝔾𝕣𝕠𝕦𝕡", url="https://t.me/PW_GROUP_LINK_Official")
        ]
    ])

    clone_text = (
        "👑 ʜᴇʟʟᴏ ℂ𝕝𝕚𝕔𝕜 𝕙𝕖𝕣𝕖 𝕥𝕠𝕠 𝕛𝕠𝕚𝕟 𝕡𝕨 𝕠𝕗𝕗𝕚𝕔𝕚𝕒𝕝 𝕔𝕙𝕒𝕥𝕚𝕟𝕘 𝕘𝕣𝕠𝕦𝕡𒐫𒐫 !\n\n"
        "ᴀɢᴀʀ ᴀᴀᴘᴋᴏ ɪꜱ ʙᴏᴛ ᴋᴀ ᴄʟᴏɴᴇ ʙᴀɴᴀɴᴀ ʜᴀɪ, ᴛᴏʜ ᴀᴀᴘ ʜᴀᴍᴀʀᴇ ʙᴏᴛ ᴏᴡɴᴇʀ ꜱᴇ ꜱᴀᴍᴘᴀʀᴋ ᴋᴀʀᴇɪɴ.\n\n"
        "✨ ᴏᴡɴᴇʀ ᴜꜱᴇʀɴᴀᴍᴇ: @Roaster_Gang\n"
        "⚡ ᴄʟᴏɴᴇ ꜱᴇᴛᴜᴘ ꜱᴜᴘᴘᴏʀᴛ: @PW_GROUP_LINK_Official"
    )
    await message.reply_text(clone_text, reply_markup=buttons)

@bot.on_message(filters.command("clones"))
async def list_clones_handler(client, message: Message):
    if message.from_user.id != BOT_OWNER_ID:
        return
    clones = load_json(CLONES_FILE)
    if not isinstance(clones, list) or len(clones) == 0:
        await message.reply_text("ℹ️ ɴᴏ ᴄʟᴏɴᴇ ʙᴏᴛꜱ ᴀʀᴇ ᴄᴜʀʀᴇɴᴛʟʏ ʀᴇɢɪꜱᴛᴇʀᴇᴅ.")
        return

    text = f"🤖 ᴀᴄᴛɪᴠᴇ ᴄʟᴏɴᴇ ʙᴏᴛꜱ ʟɪꜱᴛ ({len(clones)}):\n\n"
    for i, tok in enumerate(clones):
        text += f"🔹 {i+1}. `{tok[:10]}...{tok[-5:]}`\n"
    await message.reply_text(text)

@bot.on_message(filters.command("delclone"))
async def delete_clone_handler(client, message: Message):
    if message.from_user.id != BOT_OWNER_ID:
        return
    if len(message.command) < 2:
        await message.reply_text("🔹 ᴜꜱᴀɢᴇ: `/delclone <bot_token>`")
        return

    target_token = message.command[1]
    clones = load_json(CLONES_FILE)
    if isinstance(clones, list) and target_token in clones:
        clones.remove(target_token)
        save_json(CLONES_FILE, clones)
        await message.reply_text("🗑️ ᴄʟᴏɴᴇ ʙᴏᴛ ᴛᴏᴋᴇɴ ʜᴀꜱ ʙᴇᴇɴ ʀᴇᴍᴏᴠᴇᴅ.")
    else:
        await message.reply_text("❌ ᴄʟᴏɴᴇ ᴛᴏᴋᴇɴ ɴᴏᴛ ꜰᴏᴜɴᴅ ɪɴ ᴅᴀᴛᴀʙᴀꜱᴇ.")

# --- 4. ENTERTAINMENT AUTHORITY ---
@bot.on_message(filters.command("approve") & filters.group)
async def approve_entertainment(client, message: Message):
    user_id = message.from_user.id
    chat = message.chat

    member = await chat.get_member(user_id)
    if member.status not in ["administrator", "creator"] and user_id != BOT_OWNER_ID:
        await message.reply_text("❌ ᴏɴʟʏ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ᴀᴘᴘʀᴏᴠᴇ ᴍᴇᴍʙᴇʀꜱ.")
        return

    target_user = None
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    elif len(message.command) > 2 and message.command[2].isdigit():
        target_user = await client.get_users(int(message.command[2]))

    if not target_user:
        await message.reply_text("🔹 ᴜꜱᴀɢᴇ: Reply to a user with `/approve entertainment`")
        return

    auth_data = load_json(AUTH_FILE)
    chat_id_str = str(chat.id)
    if chat_id_str not in auth_data:
        auth_data[chat_id_str] = []

    if target_user.id not in auth_data[chat_id_str]:
        auth_data[chat_id_str].append(target_user.id)
        save_json(AUTH_FILE, auth_data)
        await message.reply_text(f"🎭 ᴇɴᴛᴇʀᴛᴀɪɴᴍᴇɴᴛ ᴀᴄᴄᴇꜱꜱ ɢʀᴀɴᴛᴇᴅ ᴛᴏ {target_user.mention}!")
    else:
        await message.reply_text("⚠️ ᴜꜱᴇʀ ɪꜱ ᴀʟʀᴇᴀᴅʏ ᴀᴘᴘʀᴏᴠᴇᴅ.")

@bot.on_message(filters.command("demote") & filters.group)
async def demote_entertainment(client, message: Message):
    user_id = message.from_user.id
    chat = message.chat

    member = await chat.get_member(user_id)
    if member.status not in ["administrator", "creator"] and user_id != BOT_OWNER_ID:
        await message.reply_text("❌ ᴏɴʟʏ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ᴅᴇᴍᴏᴛᴇ ᴍᴇᴍʙᴇʀꜱ.")
        return

    target_user = None
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    elif len(message.command) > 2 and message.command[2].isdigit():
        target_user = await client.get_users(int(message.command[2]))

    if not target_user:
        await message.reply_text("🔹 ᴜꜱᴀɢᴇ: Reply to a user with `/demote entertainment`")
        return

    auth_data = load_json(AUTH_FILE)
    chat_id_str = str(chat.id)
    if chat_id_str in auth_data and target_user.id in auth_data[chat_id_str]:
        auth_data[chat_id_str].remove(target_user.id)
        save_json(AUTH_FILE, auth_data)
        await message.reply_text(f"🎭 ᴇɴᴛᴇʀᴛᴀɪɴᴍᴇɴᴛ ᴀᴄᴄᴇꜱꜱ ʀᴇᴍᴏᴠᴇᴅ ꜰʀᴏᴍ {target_user.mention}.")
    else:
        await message.reply_text("❌ ᴜꜱᴇʀ ɪꜱ ɴᴏᴛ ɪɴ ᴀᴘᴘʀᴏᴠᴇᴅ ʟɪꜱᴛ.")

# --- 5. VC MUSIC CONTROLS ---
@bot.on_message(filters.command("play") & filters.group)
async def play_vc_handler(client, message: Message):
    if not await is_authorized(message.chat, message.from_user.id):
        await message.reply_text("❌ ʏᴏᴜ ɴᴇᴇᴅ ᴀᴅᴍɪɴ ᴏʀ ᴇɴᴛᴇʀᴛᴀɪɴᴍᴇɴᴛ ᴀᴘᴘʀᴏᴠᴀʟ.")
        return

    if len(message.command) < 2:
        await message.reply_text("🔹 ᴜꜱᴀɢᴇ: `/play <song name / yt url>`")
        return

    query = message.text.split(None, 1)[1]
    status_msg = await message.reply_text(f"🔍 ꜱᴇᴀʀᴄʜɪɴɢ: `{query}`...")

    loop = asyncio.get_event_loop()
    try:
        results = await loop.run_in_executor(None, search_yt_raw, query, 1)
        if not results:
            await status_msg.edit_text("❌ ɴᴏ ꜱᴏɴɢ ꜰᴏᴜɴᴅ.")
            return

        song = results[0]
        chat_id = message.chat.id

        if chat_id not in queues:
            queues[chat_id] = []

        try:
            await pytgcalls.join_group_call(chat_id, AudioPiped(song['url']))
            await status_msg.edit_text(f"🎶 ɴᴏᴡ ᴘʟᴀʏɪɴɢ ɪɴ ᴠᴄ:\n🔹 {song['title']}")
        except Exception:
            queues[chat_id].append(song)
            await status_msg.edit_text(f"➕ ᴀᴅᴅᴇᴅ ᴛᴏ ᴠᴄ Qᴜᴇᴜᴇ:\n🔹 {song['title']}")
    except Exception as e:
        await status_msg.edit_text(f"❌ ᴇʀʀᴏʀ: {str(e)}")

@bot.on_message(filters.command("pause") & filters.group)
async def pause_vc_handler(client, message: Message):
    if not await is_authorized(message.chat, message.from_user.id):
        return
    try:
        await pytgcalls.pause_stream(message.chat.id)
        await message.reply_text("⏸️ ᴠᴄ ꜱᴛʀᴇᴀᴍ ᴘᴀᴜꜱᴇᴅ.")
    except Exception:
        await message.reply_text("❌ ɴᴏ ᴀᴄᴛɪᴠᴇ ꜱᴛʀᴇᴀᴍ.")

@bot.on_message(filters.command("resume") & filters.group)
async def resume_vc_handler(client, message: Message):
    if not await is_authorized(message.chat, message.from_user.id):
        return
    try:
        await pytgcalls.resume_stream(message.chat.id)
        await message.reply_text("▶️ ᴠᴄ ꜱᴛʀᴇᴀᴍ ʀᴇꜱᴜᴍᴇᴅ.")
    except Exception:
        await message.reply_text("❌ ɴᴏ ᴘᴀᴜꜱᴇᴅ ꜱᴛʀᴇᴀᴍ.")

@bot.on_message(filters.command("skip") & filters.group)
async def skip_single_handler(client, message: Message):
    if not await is_authorized(message.chat, message.from_user.id):
        await message.reply_text("❌ ʏᴏᴜ ɴᴇᴇᴅ ᴀᴅᴍɪɴ ᴏʀ ᴇɴᴛᴇʀᴛᴀɪɴᴍᴇɴᴛ ᴀᴘᴘʀᴏᴠᴀʟ.")
        return

    chat_id = message.chat.id
    if chat_id in queues and len(queues[chat_id]) > 0:
        await play_next_stream(chat_id)
        await message.reply_text("⏭️ ꜱᴋɪᴘᴘᴇᴅ ꜱɪɴɢʟᴇ ꜱᴏɴɢ.")
    else:
        try:
            await pytgcalls.leave_group_call(chat_id)
            await message.reply_text("⏹️ Qᴜᴇᴜᴇ ᴇᴍᴘᴛʏ. ᴠᴄ ʟᴇꜰᴛ.")
        except Exception:
            await message.reply_text("❌ ɴᴏ ꜱᴏɴɢ ᴛᴏ ꜱᴋɪᴘ.")

@bot.on_message(filters.command(["skipplylist", "skipplaylist"]) & filters.group)
async def skip_playlist_handler(client, message: Message):
    if not await is_authorized(message.chat, message.from_user.id):
        await message.reply_text("❌ ʏᴏᴜ ɴᴇᴇᴅ ᴀᴅᴍɪɴ ᴏʀ ᴇɴᴛᴇʀᴛᴀɪɴᴍᴇɴᴛ ᴀᴘᴘʀᴏᴠᴀʟ.")
        return

    chat_id = message.chat.id
    if chat_id in queues:
        queue_count = len(queues[chat_id])
        queues[chat_id].clear()
    else:
        queue_count = 0

    try:
        await pytgcalls.leave_group_call(chat_id)
        await message.reply_text(f"⏭️ ꜰᴜʟʟ ᴘʟᴀʏʟɪꜱᴛ ꜱᴋɪᴘᴘᴇᴅ!\n🗑️ ᴄʟᴇᴀʀᴇᴅ {queue_count} Qᴜᴇᴜᴇᴅ ᴛʀᴀᴄᴋꜱ & ʀᴇꜱᴇᴛ ᴠᴄ.")
    except Exception:
        await message.reply_text("❌ ɴᴏ ᴀᴄᴛɪᴠᴇ ᴘʟᴀʏʟɪꜱᴛ ꜱᴛʀᴇᴀᴍ ᴛᴏ ꜱᴋɪᴘ.")

@bot.on_message(filters.command("stop") & filters.group)
async def stop_vc_handler(client, message: Message):
    if not await is_authorized(message.chat, message.from_user.id):
        return
    chat_id = message.chat.id
    if chat_id in queues:
        queues[chat_id].clear()
    try:
        await pytgcalls.leave_group_call(chat_id)
        await message.reply_text("⏹️ ᴍᴜꜱɪᴄ ꜱᴛᴏᴘᴘᴇᴅ & ᴠᴄ ʟᴇꜰᴛ.")
    except Exception:
        await message.reply_text("❌ ʙᴏᴛ ɪꜱ ɴᴏᴛ ɪɴ ᴠᴄ.")

# --- 6. PLAYLIST SUITE ---
@bot.on_message(filters.command("makeplylist"))
async def makeplylist_handler(client, message: Message):
    user_id = str(message.from_user.id)
    slot = int(message.command[1]) if len(message.command) > 1 and message.command[1].isdigit() else 1
    
    if slot < 1 or slot > 5:
        await message.reply_text("❌ ꜱʟᴏᴛ ᴍᴜꜱᴛ ʙᴇ 1 ᴛᴏ 5.")
        return

    data = load_json(DATA_FILE)
    if user_id not in data:
        data[user_id] = {}
    
    list_key = f"playlist{slot}"
    if list_key in data[user_id]:
        await message.reply_text(f"⚠️ `{list_key}` ᴀʟʀᴇᴀᴅʏ ᴇxɪꜱᴛꜱ!")
        return

    data[user_id][list_key] = {"name": list_key, "songs": []}
    save_json(DATA_FILE, data)
    await message.reply_text(f"✅ `{list_key}` ᴄʀᴇᴀᴛᴇᴅ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ!")

@bot.on_message(filters.command("rename"))
async def rename_handler(client, message: Message):
    user_id = str(message.from_user.id)
    if len(message.command) < 3 or not message.command[1].isdigit():
        await message.reply_text("🔹 ᴜꜱᴀɢᴇ: `/rename <slot 1-5> <new name>`")
        return

    slot = int(message.command[1])
    new_name = message.text.split(None, 2)[2]
    list_key = f"playlist{slot}"

    data = load_json(DATA_FILE)
    if user_id in data and list_key in data[user_id]:
        old_name = data[user_id][list_key]["name"]
        data[user_id][list_key]["name"] = new_name
        save_json(DATA_FILE, data)
        await message.reply_text(f"✏️ ʀᴇɴᴀᴍᴇᴅ: `{old_name}` ➜ `{new_name}`")
    else:
        await message.reply_text(f"❌ ᴘʟᴀʏʟɪꜱᴛ ꜱʟᴏᴛ {slot} ɴᴏᴛ ꜰᴏᴜɴᴅ!")

@bot.on_message(filters.command("addplylist"))
async def addplylist_handler(client, message: Message):
    user_id = str(message.from_user.id)
    if len(message.command) < 3:
        await message.reply_text("🔹 ᴜꜱᴀɢᴇ: `/addplylist <name> <song>`")
        return

    list_name = message.command[1]
    song_name = message.text.split(None, 2)[2]
    data = load_json(DATA_FILE)

    if user_id not in data:
        await message.reply_text("❌ ɴᴏ ᴘʟᴀʏʟɪꜱᴛꜱ ꜰᴏᴜɴᴅ.")
        return

    target_key = next((k for k, v in data[user_id].items() if v["name"].lower() == list_name.lower()), None)
    if not target_key:
        await message.reply_text(f"❌ `{list_name}` ɴᴏᴛ ꜰᴏᴜɴᴅ.")
        return

    if len(data[user_id][target_key]["songs"]) >= 10:
        await message.reply_text("⚠️ ᴍᴀx 10 ꜱᴏɴɢꜱ ᴀʟʟᴏᴡᴇᴅ!")
        return

    data[user_id][target_key]["songs"].append(song_name)
    save_json(DATA_FILE, data)
    await message.reply_text(f"🎵 ᴀᴅᴅᴇᴅ: `{song_name}` ➜ `{list_name}`")

@bot.on_message(filters.command("myplylist"))
async def myplylist_handler(client, message: Message):
    user_id = str(message.from_user.id)
    if len(message.command) < 2:
        await message.reply_text("🔹 ᴜꜱᴀɢᴇ: `/myplylist <name>`")
        return

    list_name = message.command[1]
    data = load_json(DATA_FILE)
    target = next((v for k, v in data.get(user_id, {}).items() if v["name"].lower() == list_name.lower()), None)

    if not target:
        await message.reply_text(f"❌ `{list_name}` ɴᴏᴛ ꜰᴏᴜɴᴅ.")
        return

    songs = target["songs"]
    if not songs:
        await message.reply_text(f"📄 `{target['name']}` ɪꜱ ᴇᴍᴘᴛʏ.")
    else:
        song_list_str = "\n".join([f"🔹 {i+1}. {s}" for i, s in enumerate(songs)])
        await message.reply_text(f"🎧 ᴘʟᴀʏʟɪꜱᴛ: `{target['name']}` ({len(songs)}/10)\n\n{song_list_str}")

@bot.on_message(filters.command("delsong"))
async def delsong_handler(client, message: Message):
    user_id = str(message.from_user.id)
    if len(message.command) < 2:
        await message.reply_text("🔹 ᴜꜱᴀɢᴇ: `/delsong <song name>`")
        return

    song_name = message.text.split(None, 1)[1].lower()
    data = load_json(DATA_FILE)

    if user_id not in data:
        await message.reply_text("❌ ɴᴏ ᴘʟᴀʏʟɪꜱᴛꜱ ꜰᴏᴜɴᴅ.")
        return

    removed = False
    for key, p_data in data[user_id].items():
        for s in list(p_data["songs"]):
            if s.lower() == song_name:
                p_data["songs"].remove(s)
                removed = True
                break

    if removed:
        save_json(DATA_FILE, data)
        await message.reply_text("🗑️ ꜱᴏɴɢ ʀᴇᴍᴏᴠᴇᴅ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ.")
    else:
        await message.reply_text("❌ ꜱᴏɴɢ ɴᴏᴛ ꜰᴏᴜɴᴅ ɪɴ ʏᴏᴜʀ ʟɪꜱᴛꜱ.")

@bot.on_message(filters.command("dellist"))
async def dellist_handler(client, message: Message):
    user_id = str(message.from_user.id)
    if len(message.command) < 2:
        await message.reply_text("🔹 ᴜꜱᴀɢᴇ: `/dellist <playlist name>`")
        return

    list_name = message.command[1]
    data = load_json(DATA_FILE)

    if user_id not in data:
        await message.reply_text("❌ ɴᴏ ᴘʟᴀʏʟɪꜱᴛꜱ ꜰᴏᴜɴᴅ.")
        return

    key_del = next((k for k, v in data[user_id].items() if v["name"].lower() == list_name.lower()), None)
    if key_del:
        del data[user_id][key_del]
        save_json(DATA_FILE, data)
        await message.reply_text(f"🗑️ ᴘʟᴀʏʟɪꜱᴛ `{list_name}` ᴅᴇʟᴇᴛᴇᴅ!")
    else:
        await message.reply_text(f"❌ ᴘʟᴀʏʟɪꜱᴛ `{list_name}` ɴᴏᴛ ꜰᴏᴜɴᴅ!")

@bot.on_message(filters.command("alldel"))
async def alldel_handler(client, message: Message):
    user_id = str(message.from_user.id)
    data = load_json(DATA_FILE)

    if user_id in data and data[user_id]:
        del data[user_id]
        save_json(DATA_FILE, data)
        await message.reply_text("💥 ᴀʟʟ ʏᴏᴜʀ ᴘʟᴀʏʟɪꜱᴛꜱ ʜᴀᴠᴇ ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ.")
    else:
        await message.reply_text("❌ ɴᴏ ᴘʟᴀʏʟɪꜱᴛꜱ ꜰᴏᴜɴᴅ ᴛᴏ ᴅᴇʟᴇᴛᴇ.")

@bot.on_message(filters.command("playplylist") & filters.group)
async def playplylist_vc(client, message: Message):
    if not await is_authorized(message.chat, message.from_user.id):
        await message.reply_text("❌ ʏᴏᴜ ɴᴇᴇᴅ ᴀᴅᴍɪɴ ᴏʀ ᴇɴᴛᴇʀᴛᴀɪɴᴍᴇɴᴛ ᴀᴘᴘʀᴏᴠᴀʟ.")
        return

    user_id = str(message.from_user.id)
    if len(message.command) < 2:
        await message.reply_text("🔹 ᴜꜱᴀɢᴇ: `/playplylist <playlist name>`")
        return

    list_name = message.command[1]
    data = load_json(DATA_FILE)
    target = next((v for k, v in data.get(user_id, {}).items() if v["name"].lower() == list_name.lower()), None)

    if not target or not target["songs"]:
        await message.reply_text("❌ ᴘʟᴀʏʟɪꜱᴛ ɪꜱ ᴇᴍᴘᴛʏ ᴏʀ ɴᴏᴛ ꜰᴏᴜɴᴅ.")
        return

    chat_id = message.chat.id
    if chat_id not in queues:
        queues[chat_id] = []

    status = await message.reply_text(f"⏳ ʟᴏᴀᴅɪɴɢ {len(target['songs'])} ꜱᴏɴɢꜱ ꜰʀᴏᴍ `{target['name']}`...")
    loop = asyncio.get_event_loop()

    added = 0
    for s_name in target["songs"]:
        try:
            results = await loop.run_in_executor(None, search_yt_raw, s_name, 1)
            if results:
                queues[chat_id].append(results[0])
                added += 1
        except Exception:
            continue

    if chat_id in queues and len(queues[chat_id]) > 0:
        first_song = queues[chat_id].pop(0)
        try:
            await pytgcalls.join_group_call(chat_id, AudioPiped(first_song['url']))
            await status.edit_text(f"🎶 ɴᴏᴡ ᴘʟᴀʏɪɴɢ ᴘʟᴀʏʟɪꜱᴛ:\n🔹 {first_song['title']}\n➕ {added-1} ꜱᴏɴɢꜱ ᴀᴅᴅᴇᴅ ᴛᴏ Qᴜᴇᴜᴇ!")
        except Exception:
            await status.edit_text(f"✅ {added} ꜱᴏɴɢꜱ ᴀᴅᴅᴇᴅ ᴛᴏ ᴀᴄᴛɪᴠᴇ ᴠᴄ Qᴜᴇᴜᴇ!")

# --- 7. DOWNLOADER SUITE ---
@bot.on_message(filters.command(["song", "download"]))
async def song_downloader(client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("🔹 ᴜꜱᴀɢᴇ: `/song <song name>`")
        return

    query = message.text.split(None, 1)[1]
    status_msg = await message.reply_text(f"🔍 ꜱᴇᴀʀᴄʜɪɴɢ: `{query}`...")

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, search_yt_raw, query, 5)

    if not results:
        await status_msg.edit_text("❌ ɴᴏ ꜱᴏɴɢꜱ ꜰᴏᴜɴᴅ.")
        return

    btn = []
    for res in results:
        btn.append([InlineKeyboardButton(f"🎵 {res['title']}", callback_data=f"opt_{res['id']}")])
    btn.append([InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_action")])

    await status_msg.edit_text("🎧 ꜱᴇʟᴇᴄᴛ ʏᴏᴜʀ ᴛʀᴀᴄᴋ:", reply_markup=InlineKeyboardMarkup(btn))

@bot.on_message(filters.command("video"))
async def video_downloader(client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("🔹 ᴜꜱᴀɢᴇ: `/video <video name>`")
        return

    query = message.text.split(None, 1)[1]
    status_msg = await message.reply_text(f"🔍 ꜱᴇᴀʀᴄʜɪɴɢ ᴠɪᴅᴇᴏ: `{query}`...")

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, search_yt_raw, query, 1)

    if not results:
        await status_msg.edit_text("❌ ɴᴏ ᴠɪᴅᴇᴏ ꜰᴏᴜɴᴅ.")
        return

    target_id = results[0]['id']
    await status_msg.edit_text("⏳ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ᴠɪᴅᴇᴏ (720ᴘ)...")

    try:
        info = await loop.run_in_executor(None, download_video_by_id, target_id)
        await message.reply_video(
            video=info['file_path'],
            caption=f"🎬 {info['title']}",
            duration=info['duration']
        )
        await status_msg.delete()
        if os.path.exists(info['file_path']):
            os.remove(info['file_path'])
    except Exception as e:
        await status_msg.edit_text(f"❌ ᴇʀʀᴏʀ: {str(e)}")

@bot.on_message(filters.command("trim"))
async def trim_downloader(client, message: Message):
    if len(message.command) < 4 or not message.command[1].isdigit() or not message.command[2].isdigit():
        await message.reply_text("🔹 ᴜꜱᴀɢᴇ: `/trim <start_sec> <duration_sec> <song name>`\nᴇxᴀᴍᴘʟᴇ: `/trim 30 30 Kesariya`")
        return

    start_sec = int(message.command[1])
    dur_sec = int(message.command[2])
    query = message.text.split(None, 3)[3]

    status_msg = await message.reply_text(f"✂️ ᴘʀᴏᴄᴇꜱꜱɪɴɢ ʀɪɴɢᴛᴏɴᴇ ({dur_sec}ꜱ)...")
    loop = asyncio.get_event_loop()

    try:
        results = await loop.run_in_executor(None, search_yt_raw, query, 1)
        if not results:
            await status_msg.edit_text("❌ ꜱᴏɴɢ ɴᴏᴛ ꜰᴏᴜɴᴅ.")
            return

        info = await loop.run_in_executor(None, download_audio_by_id, results[0]['id'], "192")
        out_trim = f"{DOWNLOAD_DIR}/trim_{results[0]['id']}.mp3"
        await loop.run_in_executor(None, trim_audio_file, info['file_path'], out_trim, start_sec, dur_sec)

        await message.reply_audio(
            audio=out_trim,
            title=f"{info['title']} (RINGTONE)",
            performer=info['performer'],
            duration=dur_sec
        )
        await status_msg.delete()

        for f in [info['file_path'], out_trim]:
            if os.path.exists(f):
                os.remove(f)
    except Exception as e:
        await status_msg.edit_text(f"❌ ᴇʀʀᴏʀ: {str(e)}")

@bot.on_message(filters.command("lyrics"))
async def lyrics_handler(client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("🔹 ᴜꜱᴀɢᴇ: `/lyrics <song name>`")
        return

    query = message.text.split(None, 1)[1]
    status = await message.reply_text(f"🔍 ꜰᴇᴛᴄʜɪɴɢ ʟʏʀɪᴄꜱ: `{query}`...")

    loop = asyncio.get_event_loop()
    lyrics_text = await loop.run_in_executor(None, fetch_lyrics_online, query)

    if len(lyrics_text) > 4000:
        lyrics_text = lyrics_text[:4000] + "..."
    await status.edit_text(f"📝 ʟʏʀɪᴄꜱ: {query.upper()}\n\n{lyrics_text}")

# --- 8. DYNAMIC MEDIA WELCOME ---
@bot.on_message(filters.new_chat_members)
async def welcome_member(client, message: Message):
    chat = message.chat
    register_chat(chat.id)
    settings = load_json(SETTINGS_FILE)
    chat_cfg = settings.get(str(chat.id), {})

    for member in message.new_chat_members:
        if member.id == (await bot.get_me()).id:
            continue

        first_name = member.first_name or ""
        last_name = member.last_name or ""
        full_name = f"{first_name} {last_name}".strip()
        username = f"@{member.username}" if member.username else "No Username"
        mention = f"[{first_name}](tg://user?id={member.id})"
        chat_name = chat.title
        members_count = await chat.get_members_count()

        default_template = (
            "👋 ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ {chatname}!\n\n"
            "🔹 ɴᴀᴍᴇ: {fullname}\n"
            "🔹 ᴜꜱᴇʀɴᴀᴍᴇ: {username}\n"
            "🔹 ᴜꜱᴇʀ ɪᴅ: {id}\n"
            "🔹 ᴛᴏᴛᴀʟ ᴍᴇᴍʙᴇʀꜱ: {memberscount}"
        )

        raw_template = chat_cfg.get("welcome_text", default_template)
        formatted_text = raw_template.format(
            mention=mention,
            username=username,
            id=member.id,
            firstname=first_name,
            lastname=last_name,
            fullname=full_name,
            chatname=chat_name,
            memberscount=members_count
        )

        media_type = chat_cfg.get("media_type")
        file_id = chat_cfg.get("media_file_id")

        try:
            if media_type == "photo" and file_id:
                await chat.send_photo(photo=file_id, caption=formatted_text)
            elif media_type == "video" and file_id:
                await chat.send_video(video=file_id, caption=formatted_text)
            else:
                await chat.send_message(text=formatted_text)
        except Exception:
            await chat.send_message(text=formatted_text)

@bot.on_message(filters.command("setwelcome") & filters.group)
async def setwelcome_handler(client, message: Message):
    user = message.from_user
    member = await message.chat.get_member(user.id)

    if member.status not in ["administrator", "creator"] and user.id != BOT_OWNER_ID:
        await message.reply_text("❌ ᴏɴʟʏ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ꜱᴇᴛ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇꜱꜱᴀɢᴇ.")
        return

    settings = load_json(SETTINGS_FILE)
    chat_id_str = str(message.chat.id)
    if chat_id_str not in settings:
        settings[chat_id_str] = {}

    reply = message.reply_to_message
    if reply:
        if reply.photo:
            settings[chat_id_str]["media_type"] = "photo"
            settings[chat_id_str]["media_file_id"] = reply.photo.file_id
            settings[chat_id_str]["welcome_text"] = reply.caption or "👋 ᴡᴇʟᴄᴏᴍᴇ {mention} ᴛᴏ {chatname}!"
        elif reply.video:
            settings[chat_id_str]["media_type"] = "video"
            settings[chat_id_str]["media_file_id"] = reply.video.file_id
            settings[chat_id_str]["welcome_text"] = reply.caption or "👋 ᴡᴇʟᴄᴏᴍᴇ {mention} ᴛᴏ {chatname}!"
        elif reply.text:
            settings[chat_id_str]["media_type"] = "text"
            settings[chat_id_str]["welcome_text"] = reply.text
    elif len(message.command) > 1:
        settings[chat_id_str]["media_type"] = "text"
        settings[chat_id_str]["welcome_text"] = message.text.split(None, 1)[1]
    else:
        await message.reply_text("🔹 ᴜꜱᴀɢᴇ: Reply to Photo/Video/Text with `/setwelcome`\nTags: `{mention}`, `{username}`, `{id}`, `{fullname}`, `{chatname}`, `{memberscount}`")
        return

    save_json(SETTINGS_FILE, settings)
    await message.reply_text("✅ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇꜱꜱᴀɢᴇ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴜᴘᴅᴀْتᴇᴅ!")

# --- 9. BROADCAST ENGINE (STICKER + BUTTONS SUPPORT) ---
@bot.on_message(filters.command(["ubc", "universalbroadcast"]))
async def universal_bc(client, message: Message):
    if message.from_user.id != BOT_OWNER_ID:
        return

    raw_text = message.text.split(None, 1)[1] if len(message.command) > 1 else ""
    reply = message.reply_to_message

    if not raw_text and not reply:
        await message.reply_text("🔹 ᴜꜱᴀɢᴇ: `/ubc <message>`\nButtons: `[Button Name | https://link.com]`")
        return

    clean_text, reply_markup = parse_custom_buttons(raw_text or (reply.caption if reply and reply.caption else ""))
    chats = load_json(CHATS_FILE)
    if not chats:
        await message.reply_text("❌ ɴᴏ ᴄʜᴀᴛꜱ ʀᴇɢɪꜱᴛᴇʀᴇᴅ.")
        return

    status = await message.reply_text("🌐 ꜱᴛᴀʀᴛɪɴɢ ᴜɴɪᴠᴇʀꜱᴀʟ ʙʀᴏᴀᴅᴄᴀꜱᴛ (ᴍᴀɪɴ + ᴀʟʟ ᴄʟᴏɴᴇꜱ)...")

    clones = load_json(CLONES_FILE)
    all_bots = [bot]
    if isinstance(clones, list):
        for tok in clones:
            try:
                b_temp = Client(f"clone_run_{tok[:6]}", api_id=API_ID, api_hash=API_HASH, bot_token=tok)
                await b_temp.start()
                all_bots.append(b_temp)
            except Exception:
                continue

    total_sent = 0
    sent_records = []

    for b_inst in all_bots:
        for cid in chats:
            try:
                sent_msg = None
                if reply and reply.sticker:
                    sent_msg = await b_inst.send_sticker(chat_id=int(cid), sticker=reply.sticker.file_id, reply_markup=reply_markup)
                elif reply and reply.photo:
                    sent_msg = await b_inst.send_photo(chat_id=int(cid), photo=reply.photo.file_id, caption=clean_text, reply_markup=reply_markup)
                elif reply and reply.video:
                    sent_msg = await b_inst.send_video(chat_id=int(cid), video=reply.video.file_id, caption=clean_text, reply_markup=reply_markup)
                else:
                    sent_msg = await b_inst.send_message(chat_id=int(cid), text=clean_text, reply_markup=reply_markup)

                if sent_msg:
                    sent_records.append({"token": b_inst.bot_token if hasattr(b_inst, "bot_token") else BOT_TOKEN, "chat_id": int(cid), "message_id": sent_msg.id})
                    total_sent += 1
                await asyncio.sleep(0.04)
            except Exception:
                continue

    save_json(UBC_FILE, sent_records)
    await status.edit_text(f"✅ ᴜɴɪᴠᴇʀꜱᴀʟ ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ!\n\n🤖 ʙᴏᴛꜱ ᴜꜱᴇᴅ: {len(all_bots)}\n📬 ᴛᴏᴛᴀʟ ᴅᴇʟɪᴠᴇʀᴇᴅ: {total_sent}")

@bot.on_message(filters.command(["delubc", "deluniversalbroadcast"]))
async def del_universal_bc(client, message: Message):
    if message.from_user.id != BOT_OWNER_ID:
        return
    data = load_json(UBC_FILE)
    if not isinstance(data, list) or len(data) == 0:
        await message.reply_text("❌ ɴᴏ ᴜɴɪᴠᴇʀꜱᴀʟ ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴛᴏ ᴅᴇʟᴇᴛᴇ.")
        return

    status = await message.reply_text("🗑️ ᴅᴇʟᴇᴛɪɴɢ ᴜɴɪᴠᴇʀꜱᴀʟ ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴍᴇꜱꜱᴀɢᴇꜱ...")
    del_count = 0
    for item in data:
        try:
            await bot.delete_messages(chat_id=item["chat_id"], message_ids=item["message_id"])
            del_count += 1
        except Exception:
            continue

    save_json(UBC_FILE, [])
    await status.edit_text(f"🗑️ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ʀᴇᴄᴀʟʟᴇᴅ {del_count} ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴍᴇꜱꜱᴀɢᴇꜱ.")

@bot.on_message(filters.command(["broadcast", "bc", "gbc"]))
async def broadcast_cmd(client, message: Message):
    if message.from_user.id != BOT_OWNER_ID:
        return
    raw_text = message.text.split(None, 1)[1] if len(message.command) > 1 else ""
    reply = message.reply_to_message

    if not raw_text and not reply:
        await message.reply_text("🔹 ᴜꜱᴀɢᴇ: `/broadcast <message>` ya sticker/photo/video ko reply karein.")
        return

    clean_text, reply_markup = parse_custom_buttons(raw_text or (reply.caption if reply and reply.caption else ""))
    chats = load_json(CHATS_FILE)
    sent_data = []
    success = 0
    await message.reply_text("📢 ꜱᴇɴᴅɪɴɢ ʙʀᴏᴀᴅᴄᴀꜱᴛ...")

    for cid in chats:
        try:
            sent_msg = None
            if reply and reply.sticker:
                sent_msg = await bot.send_sticker(chat_id=int(cid), sticker=reply.sticker.file_id, reply_markup=reply_markup)
            elif reply and reply.photo:
                sent_msg = await bot.send_photo(chat_id=int(cid), photo=reply.photo.file_id, caption=clean_text, reply_markup=reply_markup)
            elif reply and reply.video:
                sent_msg = await bot.send_video(chat_id=int(cid), video=reply.video.file_id, caption=clean_text, reply_markup=reply_markup)
            else:
                sent_msg = await bot.send_message(chat_id=int(cid), text=clean_text, reply_markup=reply_markup)

            if sent_msg:
                sent_data.append({"chat_id": int(cid), "message_id": sent_msg.id})
                success += 1
            await asyncio.sleep(0.04)
        except Exception:
            continue

    save_json(BROADCAST_FILE, sent_data)
    await message.reply_text(f"✅ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ꜱᴇɴᴛ ᴛᴏ {success} ᴄʜᴀᴛꜱ.")

@bot.on_message(filters.command("delbroadcast"))
async def del_broadcast_cmd(client, message: Message):
    if message.from_user.id != BOT_OWNER_ID:
        return
    data = load_json(BROADCAST_FILE)
    if not isinstance(data, list) or len(data) == 0:
        await message.reply_text("❌ ɴᴏ ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴛᴏ ᴅᴇʟᴇᴛᴇ.")
        return

    del_count = 0
    for item in data:
        try:
            await bot.delete_messages(chat_id=item["chat_id"], message_ids=item["message_id"])
            del_count += 1
        except Exception:
            continue

    save_json(BROADCAST_FILE, [])
    await message.reply_text(f"🗑️ ᴅᴇʟᴇᴛᴇᴅ ꜰʀᴏᴍ {del_count} ᴄʜᴀᴛꜱ.")

@bot.on_message(filters.command("stats"))
async def stats_handler(client, message: Message):
    if message.from_user.id != BOT_OWNER_ID:
        return
    chats = load_json(CHATS_FILE)
    clones = load_json(CLONES_FILE)
    c_count = len(clones) if isinstance(clones, list) else 0
    count = len(chats) if isinstance(chats, list) else 0
    await message.reply_text(f"📊 ᴛᴏᴛᴀʟ ʀᴇɢɪꜱᴛᴇʀᴇᴅ ᴄʜᴀᴛꜱ: `{count}`\n🤖 ᴛᴏᴛᴀʟ ᴄʟᴏɴᴇ ʙᴏᴛꜱ: `{c_count}`")

@bot.on_message(filters.command("backup"))
async def backup_handler(client, message: Message):
    if message.from_user.id != BOT_OWNER_ID:
        return
    for f in [DATA_FILE, CHATS_FILE, SETTINGS_FILE, AUTH_FILE, BAN_FILE, CLONES_FILE]:
        if os.path.exists(f):
            await message.reply_document(document=f)

@bot.on_message(filters.command("clean"))
async def clean_handler(client, message: Message):
    if message.from_user.id != BOT_OWNER_ID:
        return
    count = 0
    for f in os.listdir(DOWNLOAD_DIR):
        p = os.path.join(DOWNLOAD_DIR, f)
        if os.path.isfile(p):
            os.remove(p)
            count += 1
    await message.reply_text(f"🧹 ᴄʟᴇᴀɴᴇᴅ {count} ᴛᴇᴍᴘ ꜰɪʟᴇꜱ.")

# --- 10. INLINE CALLBACK DISPATCHER ---
@bot.on_callback_query()
async def callback_handler(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id

    if data.startswith("owner_") and user_id != BOT_OWNER_ID:
        await query.answer("❌ ᴀᴄᴄᴇꜱꜱ ᴅᴇɴɪᴇᴅ: ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ!", show_alert=True)
        return

    if data == "owner_panel_main":
        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Stats", callback_data="owner_stats_run"), InlineKeyboardButton("🧹 Clean", callback_data="owner_clean_run")],
            [InlineKeyboardButton("💾 Backup", callback_data="owner_backup_run"), InlineKeyboardButton("❌ Close", callback_data="cancel_action")]
        ])
        await query.message.edit_text("👑 Secure Owner Panel", reply_markup=btn)
    elif data == "owner_stats_run":
        chats = load_json(CHATS_FILE)
        await query.answer(f"Total Registered Chats: {len(chats) if isinstance(chats, list) else 0}", show_alert=True)
    elif data == "owner_clean_run":
        count = sum(1 for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f)))
        for f in os.listdir(DOWNLOAD_DIR):
            p = os.path.join(DOWNLOAD_DIR, f)
            if os.path.isfile(p): os.remove(p)
        await query.answer(f"Cleaned {count} temp files!", show_alert=True)
    elif data == "owner_backup_run":
        for f in [DATA_FILE, CHATS_FILE, SETTINGS_FILE, AUTH_FILE, BAN_FILE, CLONES_FILE]:
            if os.path.exists(f): await query.message.reply_document(document=f)
    elif data == "cancel_action":
        await query.message.delete()
    elif data == "guide_main":
        await query.message.edit_text("📖 Guide: Use /play <song> in group VC.")
    elif data == "menu_help":
        await query.message.delete()
        await help_cmd(client, query.message)

# --- 11. 24-HOUR PROMOTION BACKGROUND TASK ---
async def promo_loop():
    while True:
        await asyncio.sleep(86400)
        chats = load_json(CHATS_FILE)
        if not chats:
            continue
        bot_info = await bot.get_me()
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ", url=f"https://t.me/{bot_info.username}?startgroup=true")]])
        for cid in chats:
            try:
                await bot.send_message(
                    chat_id=int(cid),
                    text="⚡ ᴇɴᴊᴏʏ ʜɪɢʜ ǫᴜᴀʟɪᴛʏ ᴍᴜꜱɪᴄ ɪɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ ᴠᴄ ᴛᴏᴏ!\nᴄʟɪᴄᴋ ʙᴇʟᴏᴡ ᴛᴏ ᴀᴅᴅ ᴍᴇ.",
                    reply_markup=btn
                )
                await asyncio.sleep(0.05)
            except Exception:
                continue

# --- START BOT ENGINE ---
async def main():
    await user.start()
    await bot.start()
    await pytgcalls.start()
    asyncio.create_task(promo_loop())
    print("🚀 Ultimate Mega VC Bot (Owner Panel Locked) Online!")
    await idle()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
