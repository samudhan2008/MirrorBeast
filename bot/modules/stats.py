import asyncio
from platform import platform, version
from re import search as research
from time import time

from aiofiles.os import path as aiopath
from psutil import (
    Process,
    boot_time,
    cpu_count,
    cpu_freq,
    cpu_percent,
    disk_io_counters,
    disk_usage,
    getloadavg,
    net_io_counters,
    swap_memory,
    virtual_memory,
)

from .. import bot_cache, bot_start_time
from ..core.config_manager import Config, BinConfig
from ..helper.ext_utils.bot_utils import cmd_exec, compare_versions, new_task
from ..helper.ext_utils.status_utils import (
    get_progress_bar_string,
    get_readable_file_size,
    get_readable_time,
)
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.message_utils import (
    delete_message,
    edit_message,
    send_message,
)
from ..version import get_version

COMMANDS = {
    "aria2": ([BinConfig.ARIA2_NAME, "--version"], r"aria2 version ([\d.]+)"),
    "qBittorrent": ([BinConfig.QBIT_NAME, "--version"], r"qBittorrent v([\d.]+)"),
    "SABnzbd+": (
        [BinConfig.SABNZBD_NAME, "--version"],
        rf"{BinConfig.SABNZBD_NAME}-([\d.]+)",
    ),
    "python": (["python3", "--version"], r"Python ([\d.]+)"),
    "rclone": ([BinConfig.RCLONE_NAME, "--version"], r"rclone v([\d.]+)"),
    "yt-dlp": (["yt-dlp", "--version"], r"([\d.]+)"),
    "ffmpeg": (
        [BinConfig.FFMPEG_NAME, "-version"],
        r"ffmpeg version ([\d.]+(?:-\w+)?)",
    ),
    "7z": (["7z", "i"], r"7-Zip ([\d.]+)"),
    "aiohttp": (["uv", "pip", "show", "aiohttp"], r"Version: ([\d.]+)"),
    "pyrofork": (["uv", "pip", "show", "pyrofork"], r"Version: ([\d.]+)"),
    "gapi": (["uv", "pip", "show", "google-api-python-client"], r"Version: ([\d.]+)"),
    "mega": (["pip", "show", "megasdk"], r"Version: ([\d.]+)"),
}


async def get_stats(event, key="home"):
    """Return stats message and button layout for the given stat page."""
    user_id = getattr(event, "from_user", event).id
    btns = ButtonMaker()
    btns.data_button("Back", f"stats {user_id} home")

    if key == "home":
        btns = ButtonMaker()
        btns.data_button("Bot Stats", f"stats {user_id} stbot")
        btns.data_button("OS Stats", f"stats {user_id} stsys")
        btns.data_button("Repo Stats", f"stats {user_id} strepo")
        btns.data_button("Pkgs Stats", f"stats {user_id} stpkgs")
        btns.data_button("Bot Task Limits", f"stats {user_id} tlimits")
        msg = "⌬ <b><i>Bot & OS Statistics!</i></b>"

    elif key == "stbot":
        total, used, free, disk = disk_usage("/")
        swap = swap_memory()
        memory = virtual_memory()
        disk_io = disk_io_counters()
        msg = (
            "⌬ <b><i>BOT STATISTICS :</i></b>\n"
            f"╰ <b>Bot Uptime :</b> {get_readable_time(time() - bot_start_time)}\n"
            "\n"
            "╭ <b><i>RAM ( MEMORY ) :</i></b>\n"
            f"├ {get_progress_bar_string(memory.percent)} {memory.percent}%\n"
            f"╰ <b>U :</b> {get_readable_file_size(memory.used)} | <b>F :</b> {get_readable_file_size(memory.available)} | <b>T :</b> {get_readable_file_size(memory.total)}\n"
            "\n"
            "╭ <b><i>SWAP MEMORY :</i></b>\n"
            f"├ {get_progress_bar_string(swap.percent)} {swap.percent}%\n"
            f"╰ <b>U :</b> {get_readable_file_size(swap.used)} | <b>F :</b> {get_readable_file_size(swap.free)} | <b>T :</b> {get_readable_file_size(swap.total)}\n"
            "\n"
            "╭ <b><i>DISK :</i></b>\n"
            f"├ {get_progress_bar_string(disk)} {disk}%\n"
            f"├ <b>Total Disk Read :</b> {f'{get_readable_file_size(disk_io.read_bytes)} ({get_readable_time(disk_io.read_time / 1000)})' if disk_io else 'Access Denied'}\n"
            f"├ <b>Total Disk Write :</b> {f'{get_readable_file_size(disk_io.write_bytes)} ({get_readable_time(disk_io.write_time / 1000)})' if disk_io else 'Access Denied'}\n"
            f"╰ <b>U :</b> {get_readable_file_size(used)} | <b>F :</b> {get_readable_file_size(free)} | <b>T :</b> {get_readable_file_size(total)}"
        )

    elif key == "stsys":
        cpu_usage = cpu_percent(interval=0.5)
        freq = cpu_freq()
        net = net_io_counters()
        msg = (
            "⌬ <b><i>OS SYSTEM :</i></b>\n"
            f"╭ <b>OS Uptime :</b> {get_readable_time(time() - boot_time())}\n"
            f"├ <b>OS Version :</b> {version()}\n"
            f"╰ <b>OS Arch :</b> {platform()}\n"
            "\n"
            "⌬ <b><i>NETWORK STATS :</i></b>\n"
            f"╭ <b>Upload Data:</b> {get_readable_file_size(net.bytes_sent)}\n"
            f"├ <b>Download Data:</b> {get_readable_file_size(net.bytes_recv)}\n"
            f"├ <b>Pkts Sent:</b> {str(net.packets_sent)[:-3] + 'k' if net.packets_sent > 999 else net.packets_sent}\n"
            f"├ <b>Pkts Received:</b> {str(net.packets_recv)[:-3] + 'k' if net.packets_recv > 999 else net.packets_recv}\n"
            f"╰ <b>Total I/O Data:</b> {get_readable_file_size(net.bytes_recv + net.bytes_sent)}\n"
            "\n"
            "╭ <b>CPU :</b>\n"
            f"├ {get_progress_bar_string(cpu_usage)} {cpu_usage}%\n"
            f"├ <b>CPU Frequency :</b> {f'{freq.current / 1000:.2f} GHz' if freq else 'Access Denied'}\n"
            f"├ <b>System Avg Load :</b> {', '.join(str(round((x / cpu_count() * 100), 2)) + '%' for x in getloadavg())}, (1m, 5m, 15m)\n"
            f"├ <b>P-Core(s) :</b> {cpu_count(logical=False)} | <b>V-Core(s) :</b> {cpu_count(logical=True) - cpu_count(logical=False)}\n"
            f"├ <b>Total Core(s) :</b> {cpu_count(logical=True)}\n"
            f"╰ <b>Usable CPU(s) :</b> {len(Process().cpu_affinity())}"
        )

    elif key == "strepo":
        last_commit, changelog = "No Data", "N/A"
        if await aiopath.exists(".git"):
            last_commit = (
                await cmd_exec(
                    "git log -1 --pretty='%cd ( %cr )' --date=format-local:'%d/%m/%Y'",
                    True,
                )
            )[0]
            changelog = (
                await cmd_exec(
                    "git log -1 --pretty=format:'<code>%s</code> <b>By</b> %an'",
                    True,
                )
            )[0]
        try:
            official_v = (
                await cmd_exec(
                    f"curl -o latestversion.py https://raw.githubusercontent.com/BeastBots/MirrorBeast/{Config.UPSTREAM_BRANCH}/bot/version.py -s && python3 latestversion.py && rm latestversion.py",
                    True,
                )
            )[0]
        except Exception:
            official_v = "-"
        msg = (
            "⌬ <b><i>Repo Statistics :</i></b>\n\n"
            f"╭ <b>Bot Updated :</b> {last_commit}\n"
            f"├ <b>Current Version :</b> {get_version()}\n"
            f"├ <b>Latest Version :</b> {official_v}\n"
            f"╰ <b>Last ChangeLog :</b> {changelog}\n\n"
            f"⌬ <b>REMARKS :</b> <code>{compare_versions(get_version(), official_v)}</code>"
        )

    elif key == "stpkgs":
        v = bot_cache.get("eng_versions", {})
        msg = (
            "⌬ <b><i>Packages Statistics :</i></b>\n\n"
            f"╭ <b>python:</b> {v.get('python', '-')}\n"
            f"├ <b>aria2:</b> {v.get('aria2', '-')}\n"
            f"├ <b>qBittorrent:</b> {v.get('qBittorrent', '-')}\n"
            f"├ <b>SABnzbd+:</b> {v.get('SABnzbd+', '-')}\n"
            f"├ <b>rclone:</b> {v.get('rclone', '-')}\n"
            f"├ <b>yt-dlp:</b> {v.get('yt-dlp', '-')}\n"
            f"├ <b>ffmpeg:</b> {v.get('ffmpeg', '-')}\n"
            f"├ <b>7z:</b> {v.get('7z', '-')}\n"
            f"├ <b>Aiohttp:</b> {v.get('aiohttp', '-')}\n"
            f"├ <b>Pyrofork:</b> {v.get('pyrofork', '-')}\n"
            f"├ <b>Google API:</b> {v.get('gapi', '-')}\n"
            f"╰ <b>Mega SDK:</b> {v.get('mega', '-')}"
        )

    elif key == "tlimits":
        msg = (
            "⌬ <b><i>Bot Task Limits :</i></b>\n\n"
            f"╭ <b>Direct Limit :</b> {Config.DIRECT_LIMIT or '∞'} GB\n"
            f"├ <b>Torrent Limit :</b> {Config.TORRENT_LIMIT or '∞'} GB\n"
            f"├ <b>GDriveDL Limit :</b> {Config.GD_DL_LIMIT or '∞'} GB\n"
            f"├ <b>RCloneDL Limit :</b> {Config.RC_DL_LIMIT or '∞'} GB\n"
            f"├ <b>Clone Limit :</b> {Config.CLONE_LIMIT or '∞'} GB\n"
            f"├ <b>JDown Limit :</b> {Config.JD_LIMIT or '∞'} GB\n"
            f"├ <b>NZB Limit :</b> {Config.NZB_LIMIT or '∞'} GB\n"
            f"├ <b>YT-DLP Limit :</b> {Config.YTDLP_LIMIT or '∞'} GB\n"
            f"├ <b>Playlist Limit :</b> {Config.PLAYLIST_LIMIT or '∞'}\n"
            f"├ <b>Mega Limit :</b> {Config.MEGA_LIMIT or '∞'} GB\n"
            f"├ <b>Leech Limit :</b> {Config.LEECH_LIMIT or '∞'} GB\n"
            f"├ <b>Archive Limit :</b> {Config.ARCHIVE_LIMIT or '∞'} GB\n"
            f"├ <b>Extract Limit :</b> {Config.EXTRACT_LIMIT or '∞'} GB\n"
            f"╰ <b>Threshold Storage :</b> {Config.STORAGE_LIMIT or '∞'} GB\n"
            "\n"
            f"╭ <b>Token Validity :</b> {Config.VERIFY_TIMEOUT or 'Disabled'}\n"
            f"├ <b>User Time Limit :</b> {Config.USER_TIME_INTERVAL or '0'}s / task\n"
            f"├ <b>User Max Tasks :</b> {Config.USER_MAX_TASKS or '∞'}\n"
            f"╰ <b>Bot Max Tasks :</b> {Config.BOT_MAX_TASKS or '∞'}"
        )

    btns.data_button("Close", f"stats {user_id} close", "footer")
    return msg, btns.build_menu(2)


@new_task
async def bot_stats(_, message):
    """Entry point for displaying stats (as a new message)."""
    msg, btns = await get_stats(message)
    await send_message(message, msg, btns)


@new_task
async def stats_pages(_, query):
    """Callback handler for stats navigation."""
    data = query.data.split()
    message = query.message
    user_id = query.from_user.id
    if user_id != int(data[1]):
        await query.answer("Not Yours!", show_alert=True)
    elif data[2] == "close":
        await query.answer()
        await delete_message(message, getattr(message, "reply_to_message", message))
    else:
        await query.answer()
        msg, btns = await get_stats(query, data[2])
        await edit_message(message, msg, btns)


async def get_version_async(command, regex):
    """Run a command and extract version using regex."""
    try:
        out, err, code = await cmd_exec(command)
        if code != 0:
            return f"Error: {err.strip()}"
        match = research(regex, out)
        return match.group(1) if match else "-"
    except Exception as e:
        return f"Exception: {str(e)}"


@new_task
async def get_packages_version():
    """Get and cache versions of all key packages (async, parallelized)."""
    tasks = [get_version_async(cmd, regex) for cmd, regex in COMMANDS.values()]
    versions = await asyncio.gather(*tasks)
    bot_cache["eng_versions"] = dict(zip(COMMANDS.keys(), versions))
    if await aiopath.exists(".git"):
        last_commit = await cmd_exec(
            "git log -1 --date=short --pretty=format:'%cd <b>From</b> %cr'",
            True,
        )
        bot_cache["commit"] = last_commit[0] if last_commit else "No Data"
    else:
        bot_cache["commit"] = "No UPSTREAM_REPO"
