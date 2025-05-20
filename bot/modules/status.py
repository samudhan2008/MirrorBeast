import os
import random
import importlib.util
from psutil import cpu_percent, virtual_memory, disk_usage
from time import time
from asyncio import gather, iscoroutinefunction

from pyrogram.errors import QueryIdInvalid

from .. import (
    task_dict_lock,
    status_dict,
    task_dict,
    bot_start_time,
    intervals,
    sabnzbd_client,
    DOWNLOAD_DIR,
)
from ..core.torrent_manager import TorrentManager
from ..core.jdownloader_booter import jdownloader
from ..helper.ext_utils.bot_utils import new_task
from ..helper.ext_utils.status_utils import (
    EngineStatus,
    MirrorStatus,
    get_readable_file_size,
    get_readable_time,
    speed_string_to_bytes,
)
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.telegram_helper.message_utils import (
    send_message,
    delete_message,
    auto_delete_message,
    send_status_message,
    update_status_message,
    edit_message,
)
from ..helper.telegram_helper.button_build import ButtonMaker
from ..core.config_manager import Config

def get_owner_id():
    """
    Resolve OWNER_ID with the following priority:
    1. config.py in root directory
    2. OWNER_ID environment variable
    3. Config.OWNER_ID fallback
    """
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.py')
    if os.path.exists(config_path):
        spec = importlib.util.spec_from_file_location('config', config_path)
        config = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(config)
            if hasattr(config, 'OWNER_ID'):
                return config.OWNER_ID
        except Exception:
            pass
    owner_id_env = os.getenv('OWNER_ID')
    if owner_id_env is not None:
        try:
            return int(owner_id_env)
        except ValueError:
            pass
    return getattr(Config, 'OWNER_ID', 0)

OWNER_ID = get_owner_id()

EASTER_EGGS = [
    "💀 <b><i>Stop it, Get Some Help!</i></b>",
    "☠️ <b><i>Bro… there’s nothing here.</i></b>",
    "🧠 <b><i>Empty. Just like your head.</i></b>",
    "👻 <b><i>Ghost town, pal. No tasks here.</i></b>",
    "🎈 <b><i>All air, no substance. Zero tasks.</i></b>",
    "📭 <b><i>The taskbox is emptier than your DMs.</i></b>",
    "🥶 <b><i>Cold, dead silence. No action here.</i></b>",
    "🕳️ <b><i>A black hole of nothingness.</i></b>",
    "🫥 <b><i>Disappeared… like your crush did.</i></b>",
    "🪦 <b><i>Buried in inactivity. Nothing running.</i></b>",
    "😴 <b><i>Asleep on the job? Nope — nothing started.</i></b>",
    "🧍 <b><i>Standing still. Nothing’s moving.</i></b>",
    "🕸️ <b><i>Covered in cobwebs. No tasks alive.</i></b>",
    "🔍 <b><i>Searched everywhere — found nothing.</i></b>",
    "🫠 <b><i>Nothing but silence…</i></b>",
    "🐍 <b><i>No scripts hissing here.</i></b>",
    "📉 <b><i>Task levels: Rock bottom.</i></b>",
    "🎭 <b><i>An empty stage. No acts playing.</i></b>",
    "🎮 <b><i>No game. No players. Just you.</i></b>",
    "🚪 <b><i>Closed shop. Nothing’s running.</i></b>",
    "📺 <b><i>No broadcast found.</i></b>",
    "📝 <b><i>Blank slate. Zero tasks.</i></b>",
    "🦴 <b><i>Bone dry.</i></b>",
    "💨 <b><i>Gone with the wind. No processes.</i></b>",
    "🛸 <b><i>Abducted by aliens, maybe?</i></b>",
    "🕯️ <b><i>Lit a candle… still no tasks.</i></b>",
    "🦗 <b><i>Crickets…</i></b>",
    "🚫 <b><i>No entries, no fun.</i></b>",
    "🖥️ <b><i>System idle. Nada.</i></b>",
    "🌑 <b><i>Dark and empty.</i></b>",
    "🥲 <b><i>This hurts. No tasks yet.</i></b>",
    "📡 <b><i>Signal lost. No task detected.</i></b>",
    "🎶 <b><i>No song playing.</i></b>",
    "📂 <b><i>Folder’s empty too.</i></b>",
    "🥀 <b><i>Withered away. No work here.</i></b>",
    "🌫️ <b><i>Lost in the mist of nothingness.</i></b>",
    "🛌 <b><i>Taking a nap. No activity.</i></b>",
    "🚷 <b><i>Nothing allowed. No tasks here.</i></b>",
    "🥸 <b><i>You pretending there’s a task?</i></b>",
    "🎲 <b><i>Rolled a zero.</i></b>",
    "🗿 <b><i>Stone-cold nothing.</i></b>",
    "🧤 <b><i>Handled… except there’s nothing to handle.</i></b>",
    "📢 <b><i>Loud silence detected.</i></b>",
    "🔕 <b><i>No notifications. No jobs.</i></b>",
    "🥁 <b><i>Drumroll… for nothing.</i></b>",
    "🪑 <b><i>Empty chair vibes.</i></b>",
    "📸 <b><i>Snapshot of… absolutely nothing.</i></b>",
    "🐚 <b><i>Echoes of nothing.</i></b>",
    "🌪️ <b><i>A whirlwind of inactivity.</i></b>"
]

OWNER_RESPONSES = [
    "✨ <b>Dear Master, there are no tasks currently running.</b>",
    "🙏 <b>My deepest respects, but nothing is in progress right now.</b>",
    "💎 <b>Everything’s clear at the moment, Boss.</b>",
    "🫡 <b>No active tasks, Sir. Standing by.</b>",
    "👑 <b>Nothing in queue, My Liege.</b>",
    "🎩 <b>At your service, Master. The task list is empty.</b>",
    "⚙️ <b>No active processes, as you command.</b>",
    "🖥️ <b>The system is idle and awaiting your orders.</b>",
    "📊 <b>All clear, Captain. No current operations.</b>",
    "📭 <b>The taskbox is empty, Boss.</b>"
]

@new_task
async def task_status(_, message):
    """
    Show current task status or bot stats if no task is running.
    Fun responses for regular users, respectful for owner.
    """
    async with task_dict_lock:
        count = len(task_dict)

    if count == 0:
        current_time = get_readable_time(time() - bot_start_time)
        free = get_readable_file_size(disk_usage(DOWNLOAD_DIR).free)

        is_owner = (message.from_user.id == OWNER_ID)
        response = random.choice(OWNER_RESPONSES if is_owner else EASTER_EGGS)

        msg = (
            f"{response}\n\n"
            "⌬ <b><u>Bot Stats</u></b>\n"
            f"╭ <b>CPU</b> → {cpu_percent()}%\n"
            f"├ <b>RAM</b> → {virtual_memory().percent}%\n"
            f"├ <b>Free</b> → {free}\n"
            f"╰ <b>UP</b> → {current_time}\n"
        )
        reply_message = await send_message(message, msg)
        await auto_delete_message(message, reply_message)
    else:
        text = message.text.split() if getattr(message, "text", None) else []
        if len(text) > 1:
            user_id = message.from_user.id if text[1] == "me" else int(text[1])
        else:
            user_id = 0
            sid = message.chat.id
            if obj := intervals["status"].get(sid):
                obj.cancel()
                del intervals["status"][sid]
        await send_status_message(message, user_id)
        await delete_message(message)

async def get_download_status(download):
    """
    Get status and speed for a download task.
    Returns: (status_str, speed, engine_str)
    """
    eng = download.engine
    speed = (download.speed() if eng.startswith(("Pyro", "yt-dlp", "RClone", "Google-API")) else 0)
    status_func = download.status
    status = (await status_func() if iscoroutinefunction(status_func) else status_func())
    return status, speed, eng

@new_task
async def status_pages(_, query):
    """
    Handle status page callbacks (pagination, refresh, overview, etc).
    """
    data = query.data.split()
    key = int(data[1])
    action = data[2]

    if action == "ref":
        await update_status_message(key, force=True)
    elif action in ["nex", "pre"]:
        async with task_dict_lock:
            if key in status_dict:
                if action == "nex":
                    status_dict[key]["page_no"] += status_dict[key]["page_step"]
                else:
                    status_dict[key]["page_no"] -= status_dict[key]["page_step"]
    elif action == "ps":
        async with task_dict_lock:
            if key in status_dict:
                status_dict[key]["page_step"] = int(data[3])
    elif action == "st":
        async with task_dict_lock:
            if key in status_dict:
                status_dict[key]["status"] = data[3]
        await update_status_message(key, force=True)
    elif action == "ov":
        message = query.message
        task_types = [
            "Download", "Upload", "Seed", "Archive", "Extract", "Split",
            "QueueDl", "QueueUp", "Clone", "CheckUp", "Pause", "SamVid",
            "ConvertMedia", "FFmpeg"
        ]
        tasks = {t: 0 for t in task_types}
        dl_speed = up_speed = seed_speed = 0

        async with task_dict_lock:
            status_results = await gather(
                *(get_download_status(download) for download in task_dict.values())
            )

        eng_status = EngineStatus()
        if any(eng in (eng_status.STATUS_ARIA2, eng_status.STATUS_QBIT) for _, __, eng in status_results):
            dl, seed = await TorrentManager.overall_speed()
            dl_speed += dl
            seed_speed += seed

        if any(eng == eng_status.STATUS_SABNZBD for _, __, eng in status_results):
            if sabnzbd_client.LOGGED_IN:
                try:
                    kbps = float((await sabnzbd_client.get_downloads())["queue"].get("kbpersec", "0"))
                except Exception:
                    kbps = 0
                dl_speed += int(kbps * 1024)

        if any(eng == eng_status.STATUS_JD for _, __, eng in status_results):
            if jdownloader.is_connected:
                try:
                    jd_speed = await jdownloader.device.downloadcontroller.get_speed_in_bytes()
                except Exception:
                    jd_speed = 0
                dl_speed += jd_speed

        for status, speed, _ in status_results:
            match status:
                case MirrorStatus.STATUS_DOWNLOAD:
                    tasks["Download"] += 1
                    if speed:
                        dl_speed += speed_string_to_bytes(speed)
                case MirrorStatus.STATUS_UPLOAD:
                    tasks["Upload"] += 1
                    up_speed += speed_string_to_bytes(speed)
                case MirrorStatus.STATUS_SEED:
                    tasks["Seed"] += 1
                case MirrorStatus.STATUS_ARCHIVE:
                    tasks["Archive"] += 1
                case MirrorStatus.STATUS_EXTRACT:
                    tasks["Extract"] += 1
                case MirrorStatus.STATUS_SPLIT:
                    tasks["Split"] += 1
                case MirrorStatus.STATUS_QUEUEDL:
                    tasks["QueueDl"] += 1
                case MirrorStatus.STATUS_QUEUEUP:
                    tasks["QueueUp"] += 1
                case MirrorStatus.STATUS_CLONE:
                    tasks["Clone"] += 1
                case MirrorStatus.STATUS_CHECK:
                    tasks["CheckUp"] += 1
                case MirrorStatus.STATUS_PAUSED:
                    tasks["Pause"] += 1
                case MirrorStatus.STATUS_SAMVID:
                    tasks["SamVid"] += 1
                case MirrorStatus.STATUS_CONVERT:
                    tasks["ConvertMedia"] += 1
                case MirrorStatus.STATUS_FFMPEG:
                    tasks["FFmpeg"] += 1
                case _:
                    tasks["Download"] += 1

        msg = (
            "㊂ <b>Tasks Overview</b> :\n\n"
            f"╭ <b>Download:</b> {tasks['Download']} | <b>Upload:</b> {tasks['Upload']}\n"
            f"├ <b>Seed:</b> {tasks['Seed']} | <b>Archive:</b> {tasks['Archive']}\n"
            f"├ <b>Extract:</b> {tasks['Extract']} | <b>Split:</b> {tasks['Split']}\n"
            f"├ <b>QueueDL:</b> {tasks['QueueDl']} | <b>QueueUP:</b> {tasks['QueueUp']}\n"
            f"├ <b>Clone:</b> {tasks['Clone']} | <b>CheckUp:</b> {tasks['CheckUp']}\n"
            f"├ <b>Paused:</b> {tasks['Pause']} | <b>SamVideo:</b> {tasks['SamVid']}\n"
            f"╰ <b>Convert:</b> {tasks['ConvertMedia']} | <b>FFmpeg:</b> {tasks['FFmpeg']}\n\n"
            f"╭ <b>Total Download Speed:</b> {get_readable_file_size(dl_speed)}/s\n"
            f"├ <b>Total Upload Speed:</b> {get_readable_file_size(up_speed)}/s\n"
            f"╰ <b>Total Seeding Speed:</b> {get_readable_file_size(seed_speed)}/s"
        )
        button = ButtonMaker()
        button.data_button("Back", f"status {data[1]} ref")
        await edit_message(message, msg, button.build_menu())

    try:
        await query.answer()
    except QueryIdInvalid:
        pass