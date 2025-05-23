from ..helper.ext_utils.bot_utils import COMMAND_USAGE, new_task
from ..helper.ext_utils.help_messages import (
    YT_HELP_DICT,
    MIRROR_HELP_DICT,
    CLONE_HELP_DICT,
    help_string,
)
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.message_utils import (
    edit_message,
    delete_message,
    send_message,
)


@new_task
async def arg_usage(_, query):
    """
    Handles callback queries for help/argument usage navigation.
    Supports pagination and topic-specific help (mirror/yt/clone).
    """
    data = query.data.split()
    message = query.message
    await query.answer()
    action = data[1]

    if action == "close":
        return await delete_message(
            message, getattr(message, "reply_to_message", message)
        )

    pg_no = int(data[3]) if len(data) > 3 else 0

    if action in {"nex", "pre", "back"}:
        topic_map = {
            "mirror": "mirror",
            "yt": "yt",
            "clone": "clone",
            "m": "mirror",
            "y": "yt",
            "c": "clone",
        }
        topic = data[2]
        cmd_key = topic_map.get(topic, topic)
        if cmd_key in COMMAND_USAGE:
            await edit_message(
                message, COMMAND_USAGE[cmd_key][0], COMMAND_USAGE[cmd_key][pg_no + 1]
            )
        return

    if action in {"mirror", "yt", "clone"}:
        help_dict_map = {
            "mirror": MIRROR_HELP_DICT,
            "yt": YT_HELP_DICT,
            "clone": CLONE_HELP_DICT,
        }
        topic = action
        subtopic = data[2]
        help_dict = help_dict_map.get(topic)
        buttons = ButtonMaker()
        back_map = {"mirror": "m", "yt": "y", "clone": "c"}
        buttons.data_button("Back", f"help back {back_map[topic]} {pg_no}")
        button = buttons.build_menu()
        help_text = help_dict.get(subtopic, "No help available for this section.")
        await edit_message(message, help_text, button)
        return


@new_task
async def bot_help(_, message):
    """
    Sends the main help message.
    """
    await send_message(message, help_string)
