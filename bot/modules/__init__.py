# Import all modules and functions for easy package-wide access.
# Organized by functional groups for clarity and maintainability.

# Bot settings
from .bot_settings import send_bot_settings, edit_bot_settings

# Task management
from .cancel_task import cancel, cancel_multi, cancel_all_buttons, cancel_all_update
from .force_start import remove_from_queue

# Permissions & users
from .chat_permission import authorize, unauthorize, add_sudo, remove_sudo
from .users_settings import get_users_settings, edit_user_settings, send_user_settings

# Google Drive
from .gd_count import count_node
from .gd_delete import delete_file
from .gd_search import gdrive_search, select_type
from .clone import clone_node

# Mirror/Leech
from .mirror_leech import (
    mirror, leech, qb_leech, qb_mirror, jd_leech, jd_mirror, nzb_leech, nzb_mirror,
)

# Search & RSS
from .search import torrent_search, torrent_search_update, initiate_search_tools
from .nzb_search import hydra_search
from .rss import get_rss_menu, rss_listener

# Status & Stats
from .status import task_status, status_pages
from .stats import bot_stats, stats_pages, get_packages_version

# YTDLP / File selector
from .ytdlp import ytdl, ytdl_leech
from .file_selector import select, confirm_selection

# Other tools/utilities
from .imdb import imdb_search, imdb_callback
from .mediainfo import mediainfo
from .speedtest import speedtest
from .help import arg_usage, bot_help
from .shell import run_shell
from .broadcast import broadcast
from .restart import (
    restart_bot, restart_notification, confirm_restart, restart_sessions
)
from .services import start, start_cb, login, ping, log, log_cb
from .exec import aioexecute, execute, clear

__all__ = [
    # Bot settings
    "send_bot_settings", "edit_bot_settings",

    # Task management
    "cancel", "cancel_multi", "cancel_all_buttons", "cancel_all_update",
    "remove_from_queue",

    # Permissions & users
    "authorize", "unauthorize", "add_sudo", "remove_sudo",
    "get_users_settings", "edit_user_settings", "send_user_settings",

    # Google Drive
    "count_node", "delete_file", "gdrive_search", "select_type", "clone_node",

    # Mirror/Leech
    "mirror", "leech", "qb_leech", "qb_mirror", "jd_leech", "jd_mirror", "nzb_leech", "nzb_mirror",

    # Search & RSS
    "torrent_search", "torrent_search_update", "initiate_search_tools",
    "hydra_search", "get_rss_menu", "rss_listener",

    # Status & Stats
    "task_status", "status_pages", "bot_stats", "stats_pages", "get_packages_version",

    # YTDLP / File selector
    "ytdl", "ytdl_leech", "select", "confirm_selection",

    # Other tools/utilities
    "imdb_search", "imdb_callback", "mediainfo", "speedtest", "arg_usage", "bot_help",
    "run_shell", "broadcast",
    "restart_bot", "restart_notification", "confirm_restart", "restart_sessions",
    "start", "start_cb", "login", "ping", "log", "log_cb",
    "aioexecute", "execute", "clear",
]