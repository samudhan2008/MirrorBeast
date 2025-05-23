from .. import LOGGER, user_data
from ..helper.ext_utils.bot_utils import (
    sync_to_async,
    get_telegraph_list,
    new_task,
)
from ..helper.mirror_leech_utils.gdrive_utils.search import GoogleDriveSearch
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.message_utils import send_message, edit_message


async def list_buttons(user_id, is_recursive=True, user_token=False):
    """
    Generates InlineKeyboard buttons for GDrive list options.
    """
    buttons = ButtonMaker()
    buttons.data_button(
        f"{'✅️' if user_token else '❌️'} User Token",
        f"list_types {user_id} ut {is_recursive} {user_token}",
        "header",
    )
    buttons.data_button(
        f"{'✅️' if is_recursive else '❌️'} Recursive",
        f"list_types {user_id} rec {is_recursive} {user_token}",
        "header",
    )
    buttons.data_button(
        "Folders", f"list_types {user_id} folders {is_recursive} {user_token}"
    )
    buttons.data_button(
        "Files", f"list_types {user_id} files {is_recursive} {user_token}"
    )
    buttons.data_button(
        "Both", f"list_types {user_id} both {is_recursive} {user_token}"
    )
    buttons.data_button("Cancel", f"list_types {user_id} cancel", "footer")
    return buttons.build_menu(2)


async def _list_drive(key, message, item_type, is_recursive, user_token, user_id):
    """
    Calls GoogleDriveSearch and updates the Telegram message with results or error.
    """
    LOGGER.info(
        f"GD Listing: {key} | type: {item_type} | rec: {is_recursive} | user_token: {user_token}"
    )
    target_id = ""
    if user_token:
        user_dict = user_data.get(user_id, {})
        target_id = user_dict.get("GDRIVE_ID", "")
        LOGGER.info(f"Using User Token GDRIVE_ID: {target_id}")

    try:
        telegraph_content, contents_no = await sync_to_async(
            GoogleDriveSearch(
                is_recursive=is_recursive, item_type=item_type
            ).drive_list,
            key,
            target_id,
            user_id,
        )
        if telegraph_content:
            try:
                button = await get_telegraph_list(telegraph_content)
            except Exception as e:
                LOGGER.error(f"Telegraph list fetch error: {e}")
                await edit_message(message, f"Error: {e}")
                return
            msg = f"<b>Found {contents_no} result{'s' if contents_no != 1 else ''} for <i>{key}</i></b>"
            await edit_message(message, msg, button)
        else:
            await edit_message(message, f"No result found for <i>{key}</i>")
    except Exception as e:
        LOGGER.error(f"GDrive search error: {e}")
        await edit_message(message, f"Search failed: {e}")


@new_task
async def select_type(_, query):
    """
    Callback handler for GDrive list type selection.
    """
    user_id = query.from_user.id
    message = query.message
    rply = getattr(message, "reply_to_message", None)
    key = None
    if rply and rply.text:
        key = rply.text.split(maxsplit=1)[1].strip()
    else:
        await query.answer("No search key found.", show_alert=True)
        return
    data = query.data.split()
    if user_id != int(data[1]):
        return await query.answer(text="Not Yours!", show_alert=True)
    action = data[2]
    is_recursive = data[3].lower() == "true"
    user_token = data[4].lower() == "true"
    if action == "rec":
        await query.answer()
        buttons = await list_buttons(user_id, not is_recursive, user_token)
        return await edit_message(message, "Choose list options:", buttons)
    elif action == "ut":
        await query.answer()
        buttons = await list_buttons(user_id, is_recursive, not user_token)
        return await edit_message(message, "Choose list options:", buttons)
    elif action == "cancel":
        await query.answer()
        return await edit_message(message, "<i>List has been canceled!</i>")
    await query.answer()
    item_type = action
    await edit_message(message, f"<b>Searching for <i>{key}</i>...</b>")
    await _list_drive(key, message, item_type, is_recursive, user_token, user_id)


@new_task
async def gdrive_search(_, message):
    """
    Entry point for /list command. Presents list options if a query is present.
    """
    if len(message.text.split()) == 1:
        return await send_message(
            message, "<i>Send a search query along with list command</i>"
        )
    user_id = message.from_user.id
    buttons = await list_buttons(user_id)
    await send_message(message, "Choose list options:", buttons)
