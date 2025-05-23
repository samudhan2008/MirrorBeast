from .. import user_data
from ..helper.ext_utils.bot_utils import update_user_ldata, new_task
from ..helper.ext_utils.db_handler import database
from ..helper.telegram_helper.message_utils import send_message


def extract_id_and_thread(msg, message):
    """
    Utility to extract chat/user ID and thread ID from message or reply.
    Returns (chat_id, thread_id)
    """
    chat_id = None
    thread_id = None
    if len(msg) > 1:
        if "|" in msg[1]:
            parts = msg[1].split("|")
            chat_id = int(parts[0])
            thread_id = int(parts[1]) if len(parts) > 1 else None
        else:
            chat_id = int(msg[1].strip())
    elif getattr(message, "reply_to_message", None) and (
        not hasattr(message, "message_thread_id")
        or message.reply_to_message.id != getattr(message, "message_thread_id", None)
    ):
        reply_to = message.reply_to_message
        chat_id = (
            getattr(reply_to, "from_user", None)
            or getattr(reply_to, "sender_chat", None)
        ).id
    else:
        if getattr(message, "is_topic_message", False):
            thread_id = getattr(message, "message_thread_id", None)
        chat_id = message.chat.id
    return chat_id, thread_id


@new_task
async def authorize(_, message):
    msg = message.text.split()
    chat_id, thread_id = extract_id_and_thread(msg, message)
    if chat_id is None:
        await send_message(message, "Could not determine chat/user ID to authorize.")
        return

    # Already authorized check
    if chat_id in user_data and user_data[chat_id].get("AUTH"):
        thread_ids = user_data[chat_id].get("thread_ids", [])
        if thread_id is not None:
            if thread_id in thread_ids:
                msg_text = "Already Done 👍"
            else:
                user_data[chat_id]["thread_ids"] = thread_ids + [thread_id]
                msg_text = "Done 👍"
        else:
            msg_text = "Already Done 👍"
    else:
        update_user_ldata(chat_id, "AUTH", True)
        if thread_id is not None:
            update_user_ldata(chat_id, "thread_ids", [thread_id])
        await database.update_user_data(chat_id)
        msg_text = "Done 👍"
    await send_message(message, msg_text)


@new_task
async def unauthorize(_, message):
    msg = message.text.split()
    chat_id, thread_id = extract_id_and_thread(msg, message)
    if chat_id is None:
        await send_message(message, "Could not determine chat/user ID to unauthorize.")
        return

    if chat_id in user_data and user_data[chat_id].get("AUTH"):
        thread_ids = user_data[chat_id].get("thread_ids", [])
        if thread_id is not None and thread_id in thread_ids:
            user_data[chat_id]["thread_ids"] = [
                tid for tid in thread_ids if tid != thread_id
            ]
            # If no more authorized threads, remove AUTH as well
            if not user_data[chat_id]["thread_ids"]:
                update_user_ldata(chat_id, "AUTH", False)
        else:
            update_user_ldata(chat_id, "AUTH", False)
        await database.update_user_data(chat_id)
        msg_text = "Unauthorized"
    else:
        msg_text = "Already Unauthorized!"
    await send_message(message, msg_text)


def extract_target_id(msg, message):
    """
    Utility to extract a user/chat ID for sudo operations.
    """
    if len(msg) > 1:
        try:
            return int(msg[1].strip())
        except Exception:
            return None
    elif getattr(message, "reply_to_message", None):
        return (
            getattr(message.reply_to_message, "from_user", None)
            or getattr(message.reply_to_message, "sender_chat", None)
        ).id
    return None


@new_task
async def add_sudo(_, message):
    msg = message.text.split()
    id_ = extract_target_id(msg, message)
    if id_ is not None:
        if id_ in user_data and user_data[id_].get("SUDO"):
            msg_text = "Already Sudo!"
        else:
            update_user_ldata(id_, "SUDO", True)
            await database.update_user_data(id_)
            msg_text = "Promoted as Sudo"
    else:
        msg_text = "Provide ID or reply to the message of the user you want to promote."
    await send_message(message, msg_text)


@new_task
async def remove_sudo(_, message):
    msg = message.text.split()
    id_ = extract_target_id(msg, message)
    if id_ is not None:
        if id_ in user_data and user_data[id_].get("SUDO"):
            update_user_ldata(id_, "SUDO", False)
            await database.update_user_data(id_)
            msg_text = "Demoted"
        else:
            msg_text = "User is not a Sudo user."
    else:
        msg_text = "Provide ID or reply to the message of the user you want to demote."
    await send_message(message, msg_text)
