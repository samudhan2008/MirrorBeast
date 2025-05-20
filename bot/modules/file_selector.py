from aiofiles.os import remove, path as aiopath
from asyncio import iscoroutinefunction

from .. import (
    task_dict,
    task_dict_lock,
    user_data,
    LOGGER,
    sabnzbd_client,
)
from ..core.config_manager import Config
from ..core.torrent_manager import TorrentManager
from ..helper.ext_utils.bot_utils import (
    bt_selection_buttons,
    new_task,
)
from ..helper.ext_utils.status_utils import get_task_by_gid, MirrorStatus
from ..helper.telegram_helper.message_utils import (
    send_message,
    send_status_message,
    delete_message,
)

@new_task
async def select(_, message):
    """
    Allows the user to pause a running download and select files for download (BT/NZB/Aria2).
    """
    if not Config.BASE_URL:
        await send_message(message, "Base URL not defined!")
        return

    user_id = getattr(message.from_user, "id", None)
    msg_split = message.text.split()
    task = None

    if len(msg_split) > 1:
        gid = msg_split[1]
        task = await get_task_by_gid(gid)
        if task is None:
            await send_message(message, f"GID: <code>{gid}</code> Not Found.")
            return
    elif getattr(message, "reply_to_message_id", None):
        reply_to_id = message.reply_to_message_id
        async with task_dict_lock:
            task = task_dict.get(reply_to_id)
        if task is None:
            await send_message(message, "This is not an active task!")
            return
    else:
        usage_msg = (
            "Reply to an active /cmd which was used to start the download or add gid along with cmd\n\n"
            "This command is mainly for selection in case you decided to select files from an already added torrent/nzb. "
            "But you can always use /cmd with arg `s` to select files before the download starts."
        )
        await send_message(message, usage_msg)
        return

    listener = getattr(task, "listener", None)
    allowed = (
        Config.OWNER_ID == user_id
        or (listener and listener.user_id == user_id)
        or (user_id in user_data and user_data[user_id].get("SUDO"))
    )
    if not allowed:
        await send_message(message, "This task is not for you!")
        return

    if not iscoroutinefunction(getattr(task, "status", lambda: None)):
        await send_message(message, "The task has finished the download stage!")
        return

    cur_status = await task.status() if hasattr(task, "status") else None
    if cur_status not in [
        MirrorStatus.STATUS_DOWNLOAD,
        MirrorStatus.STATUS_PAUSED,
        MirrorStatus.STATUS_QUEUEDL,
    ]:
        await send_message(
            message,
            "Task should be in download, paused, or queued (for torrent/nzb file) status!",
        )
        return

    name = task.name() if hasattr(task, "name") else ""
    if name.startswith("[METADATA]") or name.startswith("Trying"):
        await send_message(message, "Try after downloading metadata has finished!")
        return

    try:
        if not getattr(task, "queued", False):
            await task.update()
            id_ = task.gid()
            if listener and listener.is_nzb:
                await sabnzbd_client.pause_job(id_)
            elif listener and listener.is_qbit:
                id_ = task.hash()
                await TorrentManager.qbittorrent.torrents.stop([id_])
            else:
                try:
                    await TorrentManager.aria2.forcePause(id_)
                except Exception as e:
                    LOGGER.error(f"{e} Error in pause, likely after aria2 abuse.")
        if listener:
            listener.select = True
    except Exception as e:
        LOGGER.error(f"Error in selection preparation: {e}")
        await send_message(message, "This is not a bittorrent or sabnzbd task!")
        return

    SBUTTONS = bt_selection_buttons(id_)
    msg = "Your download has been paused. Choose files then press the 'Done Selecting' button to resume downloading."
    await send_message(message, msg, SBUTTONS)

@new_task
async def confirm_selection(_, query):
    """
    Handles selection confirmation: resumes download, deletes unwanted files, or cancels the task.
    """
    user_id = query.from_user.id
    data = query.data.split()
    message = query.message
    gid = data[2] if len(data) > 2 else None
    task = await get_task_by_gid(gid)
    if task is None:
        await query.answer("This task has been cancelled!", show_alert=True)
        await delete_message(message)
        return

    listener = getattr(task, "listener", None)
    if not listener or user_id != listener.user_id:
        await query.answer("This task is not for you!", show_alert=True)
        return

    action = data[1]
    if action == "pin":
        await query.answer(data[3] if len(data) > 3 else "Pinned", show_alert=True)
        return

    if action == "done":
        await query.answer()
        id_ = data[3] if len(data) > 3 else None

        if hasattr(task, "seeding"):
            if listener.is_qbit:
                try:
                    tor_info_list = await TorrentManager.qbittorrent.torrents.info(hashes=[id_])
                    if not tor_info_list:
                        raise ValueError("No info found for the provided hash.")
                    tor_info = tor_info_list[0]
                    path = tor_info.content_path.rsplit("/", 1)[0]
                    res = await TorrentManager.qbittorrent.torrents.files(id_)
                    for f in res:
                        if getattr(f, "priority", 1) == 0:
                            f_paths = [f"{path}/{f.name}", f"{path}/{f.name}.!qB"]
                            for f_path in f_paths:
                                if await aiopath.exists(f_path):
                                    try:
                                        await remove(f_path)
                                    except Exception:
                                        pass
                    if not getattr(task, "queued", False):
                        await TorrentManager.qbittorrent.torrents.start([id_])
                except Exception as e:
                    LOGGER.error(f"Qbittorrent file selection cleanup error: {e}")
            else:
                try:
                    res = await TorrentManager.aria2.getFiles(id_)
                    for f in res:
                        if f.get("selected") == "false" and await aiopath.exists(f.get("path", "")):
                            try:
                                await remove(f["path"])
                            except Exception:
                                pass
                    if not getattr(task, "queued", False):
                        try:
                            await TorrentManager.aria2.unpause(id_)
                        except Exception as e:
                            LOGGER.error(
                                f"{e} Error in resume, likely after aria2 abuse. Try to use select cmd again!"
                            )
                except Exception as e:
                    LOGGER.error(f"Aria2 selection cleanup error: {e}")
        elif listener.is_nzb:
            try:
                await sabnzbd_client.resume_job(id_)
            except Exception as e:
                LOGGER.error(f"SABnzbd resume_job error: {e}")
        await send_status_message(message)
        await delete_message(message)
    else:
        await delete_message(message)
        await task.cancel_task()