from asyncio import sleep

from .. import task_dict, task_dict_lock, user_data, multi_tags
from ..core.tg_client import Config, TgClient
from ..helper.ext_utils.bot_utils import new_task
from ..helper.ext_utils.status_utils import (
    get_task_by_gid,
    get_all_tasks,
    MirrorStatus,
)
from ..helper.telegram_helper import button_build
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.message_utils import (
    send_message,
    auto_delete_message,
    delete_message,
    edit_message,
)

@new_task
async def cancel(_, message):
    """
    Cancels a specific task by GID, reply, or multi-tag.
    """
    user_id = (message.from_user or message.sender_chat).id
    msg_split = message.text.split("_", maxsplit=1)
    task = None

    if len(msg_split) > 1:
        cmd_data = msg_split[1].split("@", maxsplit=1)
        if len(cmd_data) > 1 and cmd_data[1].strip() != TgClient.BNAME:
            return
        gid = cmd_data[0]
        if len(gid) == 6 and gid.isdigit():
            # Multi-tag cancel
            multi_tags.discard(int(gid))
            return
        task = await get_task_by_gid(gid)
        if task is None:
            await send_message(message, f"GID: <code>{gid}</code> Not Found.")
            return
    elif getattr(message, "reply_to_message_id", None):
        async with task_dict_lock:
            task = task_dict.get(message.reply_to_message_id)
        if task is None:
            await send_message(message, "This is not an active task!")
            return
    else:
        # Help message for cancel usage
        msg_text = (
            "Reply to an active Command message which was used to start the download"
            f" or send <code>/{BotCommands.CancelTaskCommand[0]} GID</code> to cancel it!"
        )
        await send_message(message, msg_text)
        return

    # Permission check: owner, task owner, or SUDO
    if (
        Config.OWNER_ID != user_id
        and task.listener.user_id != user_id
        and (user_id not in user_data or not user_data[user_id].get("SUDO"))
    ):
        await send_message(message, "This task is not for you!")
        return

    obj = task.task()
    await obj.cancel_task()

@new_task
async def cancel_multi(_, query):
    """
    Handles callback for cancelling multi-tasks.
    """
    data = query.data.split()
    user_id = query.from_user.id
    tag = int(data[2])
    # Only the user who started the multi-task or sudo can cancel
    if user_id != int(data[1]) and not await CustomFilters.sudo("", query):
        await query.answer("Not Yours!", show_alert=True)
        return

    if tag in multi_tags:
        multi_tags.discard(tag)
        msg = "Stopped!"
    else:
        msg = "Already Stopped/Finished!"
    await query.answer(msg, show_alert=True)
    await delete_message(query.message, getattr(query.message, "reply_to_message", None))

async def cancel_all(status, user_id):
    """
    Cancels all tasks of a given status for a user_id.
    """
    matches = await get_all_tasks(status.strip(), user_id)
    if not matches:
        return False
    for task in matches:
        obj = task.task()
        await obj.cancel_task()
        await sleep(2)
    return True

def create_cancel_buttons(is_sudo, user_id=""):
    """
    Creates inline buttons for bulk cancelling tasks.
    """
    buttons = button_build.ButtonMaker()
    # Map of status text to MirrorStatus constants
    status_map = {
        "Downloading": MirrorStatus.STATUS_DOWNLOAD,
        "Uploading": MirrorStatus.STATUS_UPLOAD,
        "Seeding": MirrorStatus.STATUS_SEED,
        "Spltting": MirrorStatus.STATUS_SPLIT,
        "Cloning": MirrorStatus.STATUS_CLONE,
        "Extracting": MirrorStatus.STATUS_EXTRACT,
        "Archiving": MirrorStatus.STATUS_ARCHIVE,
        "QueuedDl": MirrorStatus.STATUS_QUEUEDL,
        "QueuedUp": MirrorStatus.STATUS_QUEUEUP,
        "SampleVideo": MirrorStatus.STATUS_SAMVID,
        "ConvertMedia": MirrorStatus.STATUS_CONVERT,
        "FFmpeg": MirrorStatus.STATUS_FFMPEG,
        "Paused": MirrorStatus.STATUS_PAUSED,
        "All": "All",
    }
    for label, status in status_map.items():
        buttons.data_button(label, f"canall ms {status} {user_id}")
    if is_sudo:
        if user_id:
            buttons.data_button("All Added Tasks", f"canall bot ms {user_id}")
        else:
            buttons.data_button("My Tasks", f"canall user ms {user_id}")
    buttons.data_button("Close", f"canall close ms {user_id}")
    return buttons.build_menu(2)

@new_task
async def cancel_all_buttons(_, message):
    """
    Shows buttons to let user bulk-cancel tasks by status.
    """
    async with task_dict_lock:
        count = len(task_dict)
    if count == 0:
        await send_message(message, "No active tasks!")
        return
    is_sudo = await CustomFilters.sudo("", message)
    button = create_cancel_buttons(is_sudo, message.from_user.id)
    can_msg = await send_message(message, "Choose tasks to cancel!", button)
    await auto_delete_message(message, can_msg)

@new_task
async def cancel_all_update(_, query):
    """
    Handles all inline cancel-all actions from buttons.
    """
    data = query.data.split()
    message = query.message
    reply_to = getattr(message, "reply_to_message", message)
    user_id = int(data[3]) if len(data) > 3 and data[3].isdigit() else ""
    is_sudo = await CustomFilters.sudo("", query)
    # Only allow if sudo or user_id matches the requesting user
    if not is_sudo and user_id and user_id != query.from_user.id:
        await query.answer("Not Yours!", show_alert=True)
        return
    else:
        await query.answer()

    if data[1] == "close":
        await delete_message(reply_to, message)
        return
    elif data[1] == "back":
        button = create_cancel_buttons(is_sudo, user_id)
        await edit_message(message, "Choose tasks to cancel!", button)
        return
    elif data[1] == "bot":
        button = create_cancel_buttons(is_sudo, "")
        await edit_message(message, "Choose tasks to cancel!", button)
        return
    elif data[1] == "user":
        button = create_cancel_buttons(is_sudo, query.from_user.id)
        await edit_message(message, "Choose tasks to cancel!", button)
        return
    elif data[1] == "ms":
        # Confirm prompt for mass cancel
        buttons = button_build.ButtonMaker()
        buttons.data_button("Yes!", f"canall {data[2]} confirm {user_id}")
        buttons.data_button("Back", f"canall back confirm {user_id}")
        buttons.data_button("Close", f"canall close confirm {user_id}")
        button = buttons.build_menu(2)
        await edit_message(
            message, f"Are you sure you want to cancel all {data[2]} tasks?", button
        )
        return
    elif data[2] == "confirm":
        # Actually perform cancel
        res = await cancel_all(data[1], user_id)
        if not res:
            await send_message(reply_to, f"No matching tasks for {data[1]}!")
        else:
            await send_message(reply_to, f"All {data[1]} tasks cancelled!")
        return
    else:
        button = create_cancel_buttons(is_sudo, user_id)
        await edit_message(message, "Choose tasks to cancel.", button)