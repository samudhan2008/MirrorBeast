from .. import (
    task_dict,
    task_dict_lock,
    user_data,
    queued_up,
    queued_dl,
    queue_dict_lock,
)
from ..core.config_manager import Config
from ..helper.ext_utils.bot_utils import new_task
from ..helper.ext_utils.status_utils import get_task_by_gid
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.telegram_helper.message_utils import send_message
from ..helper.ext_utils.task_manager import start_dl_from_queued, start_up_from_queued


@new_task
async def remove_from_queue(_, message):
    """
    Force starts a queued download/upload task by GID or by reply.
    Allows download (fd), upload (fu), or both to be forced.
    Only allowed for the task owner, bot owner, or sudo users.
    """
    user = getattr(message, "from_user", None) or getattr(message, "sender_chat", None)
    user_id = getattr(user, "id", None)
    msg_args = message.text.split()
    status = msg_args[1] if len(msg_args) > 1 and msg_args[1] in {"fd", "fu"} else ""
    gid = None
    task = None

    if (status and len(msg_args) > 2) or (not status and len(msg_args) > 1):
        gid = msg_args[2] if status else msg_args[1]
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
        # Help message
        help_msg = f"""Reply to an active command message used to start the task.
<code>/{BotCommands.ForceStartCommand[0]}</code> fd (force download only) or fu (force upload only) or nothing (force both).
Or send <code>/{BotCommands.ForceStartCommand[0]} GID</code> [fu|fd] to force start by GID.
Examples:
<code>/{BotCommands.ForceStartCommand[1]}</code> GID fu (force upload)
<code>/{BotCommands.ForceStartCommand[1]}</code> GID (force download and upload)
By replying to task cmd:
<code>/{BotCommands.ForceStartCommand[1]}</code>
<code>/{BotCommands.ForceStartCommand[1]}</code> fd
"""
        await send_message(message, help_msg)
        return

    # Permission check
    listener = getattr(task, "listener", None)
    if not listener or not hasattr(listener, "user_id"):
        await send_message(message, "No valid task listener found.")
        return

    is_owner = Config.OWNER_ID == user_id
    is_task_owner = listener.user_id == user_id
    is_sudo = user_id in user_data and user_data[user_id].get("SUDO")
    if not (is_owner or is_task_owner or is_sudo):
        await send_message(message, "You are not authorized to force start this task!")
        return

    # Handle force start logic
    msg = ""
    async with queue_dict_lock:
        mid = getattr(listener, "mid", None)
        if status == "fu":
            listener.force_upload = True
            if mid in queued_up:
                await start_up_from_queued(mid)
                msg = "Task has been force started to upload!"
            else:
                msg = "Force upload enabled for this task!"
        elif status == "fd":
            listener.force_download = True
            if mid in queued_dl:
                await start_dl_from_queued(mid)
                msg = "Task has been force started to download only!"
            else:
                msg = "This task is not in the download queue!"
        else:
            listener.force_download = True
            listener.force_upload = True
            if mid in queued_up:
                await start_up_from_queued(mid)
                msg = "Task has been force started to upload!"
            elif mid in queued_dl:
                await start_dl_from_queued(mid)
                msg = "Task has been force started to download and upload will start once download finishes!"
            else:
                msg = "This task is not in any queue!"

    if msg:
        await send_message(message, msg)
