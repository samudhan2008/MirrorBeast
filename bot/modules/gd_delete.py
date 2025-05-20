from .. import LOGGER
from ..helper.ext_utils.bot_utils import sync_to_async, new_task
from ..helper.ext_utils.links_utils import is_gdrive_link
from ..helper.mirror_leech_utils.gdrive_utils.delete import GoogleDriveDelete
from ..helper.telegram_helper.message_utils import auto_delete_message, send_message

@new_task
async def delete_file(_, message):
    """
    Deletes a Google Drive file/folder by link, either from command argument or reply.
    Notifies user of result and auto-deletes the response message.
    """
    args = message.text.split(maxsplit=1)
    user = getattr(message, "from_user", None) or getattr(message, "sender_chat", None)
    link = ""

    if len(args) > 1:
        link = args[1].strip()
    elif getattr(message, "reply_to_message", None) and getattr(message.reply_to_message, "text", None):
        link = message.reply_to_message.text.split(maxsplit=1)[0].strip()

    if is_gdrive_link(link):
        LOGGER.info(f"Attempting GDrive delete: {link} (user: {getattr(user, 'id', None)})")
        try:
            msg = await sync_to_async(GoogleDriveDelete().deletefile, link, getattr(user, "id", None))
        except Exception as e:
            LOGGER.error(f"Error deleting GDrive file: {e}")
            msg = f"Error deleting Google Drive file: {e}"
    else:
        msg = (
            "Please provide a valid Google Drive link either as an argument or by replying to a message containing the link."
        )
    reply_message = await send_message(message, msg)
    await auto_delete_message(message, reply_message)