from ..helper.ext_utils.bot_utils import sync_to_async, new_task
from ..helper.ext_utils.links_utils import is_gdrive_link
from ..helper.ext_utils.status_utils import get_readable_file_size
from ..helper.mirror_leech_utils.gdrive_utils.count import GoogleDriveCount
from ..helper.telegram_helper.message_utils import delete_message, send_message

@new_task
async def count_node(_, message):
    """
    Counts files, folders, and size of a Google Drive link provided via command or reply.
    Sends a formatted summary message.
    """
    args = message.text.split()
    user = getattr(message, "from_user", None) or getattr(message, "sender_chat", None)
    username = getattr(user, "username", None)
    tag = f"@{username}" if username else getattr(message.from_user, "mention", "")

    link = args[1].strip() if len(args) > 1 else ""
    if not link and getattr(message, "reply_to_message", None):
        reply_to = message.reply_to_message
        if getattr(reply_to, "text", None):
            link = reply_to.text.split(maxsplit=1)[0].strip()

    if is_gdrive_link(link):
        progress_msg = await send_message(message, f"Counting: <code>{link}</code>")
        try:
            name, mime_type, size, files, folders = await sync_to_async(
                GoogleDriveCount().count, link, getattr(user, "id", None)
            )
            if mime_type is None:
                await delete_message(progress_msg)
                await send_message(message, name)
                return
            await delete_message(progress_msg)
            msg = (
                f"<b>Name:</b> <code>{name}</code>"
                f"\n\n<b>Size:</b> {get_readable_file_size(size)}"
                f"\n\n<b>Type:</b> {mime_type}"
            )
            if mime_type == "Folder":
                msg += f"\n<b>SubFolders:</b> {folders}"
                msg += f"\n<b>Files:</b> {files}"
            msg += f"\n\n<b>cc:</b> {tag}"
        except Exception as e:
            await delete_message(progress_msg)
            msg = f"An error occurred while counting: <code>{e}</code>"
            await send_message(message, msg)
            return
    else:
        msg = (
            "Please provide a valid Google Drive link as an argument or reply to a message containing the link."
        )

    await send_message(message, msg)