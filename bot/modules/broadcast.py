from asyncio import sleep
from time import time
from secrets import token_hex

from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked

from ..core.config_manager import Config
from ..core.tg_client import TgClient
from ..helper.ext_utils.bot_utils import new_task
from ..helper.ext_utils.db_handler import database
from ..helper.ext_utils.status_utils import get_readable_time
from ..helper.telegram_helper.message_utils import (
    edit_message,
    send_message,
)

bc_cache = {}


async def delete_broadcast(bc_id, message):
    """Delete broadcasted messages based on the broadcast ID."""
    if bc_id not in bc_cache:
        return await send_message(message, "Invalid Broadcast ID!")

    temp_wait = await send_message(
        message, "<i>Deleting the Broadcasted Message! Please Wait ...</i>"
    )
    total, success, failed = 0, 0, 0
    msgs = bc_cache.get(bc_id, [])
    for uid, msg_id in msgs:
        try:
            msg = await TgClient.bot.get_messages(uid, msg_id)
            await msg.delete()
            success += 1
        except FloodWait as e:
            await sleep(e.value)
            try:
                msg = await TgClient.bot.get_messages(uid, msg_id)
                await msg.delete()
                success += 1
            except Exception as e:
                print(f"Error deleting message for user {uid} after floodwait: {e}")
                failed += 1
        except Exception as e:
            print(f"Error deleting message for user {uid}: {e}")
            failed += 1
        total += 1
    return await edit_message(
        temp_wait,
        f"""⌬  <b><i>Broadcast Deleted Stats :</i></b>
┠ <b>Total Users:</b> <code>{total}</code>
┠ <b>Success:</b> <code>{success}</code>
┖ <b>Failed Attempts:</b> <code>{failed}</code>

<b>Broadcast ID:</b> <code>{bc_id}</code>""",
    )


async def edit_broadcast(bc_id, message, rply):
    """Edit broadcasted messages based on the broadcast ID."""
    if bc_id not in bc_cache:
        return await send_message(message, "Invalid Broadcast ID!")

    temp_wait = await send_message(
        message, "<i>Editing the Broadcasted Message! Please Wait ...</i>"
    )
    total, success, failed = 0, 0, 0
    for uid, msg_id in bc_cache[bc_id]:
        try:
            msg = await TgClient.bot.get_messages(uid, msg_id)
            if getattr(msg, "forward_from", None):
                return await edit_message(
                    temp_wait,
                    "<i>Forwarded Messages can't be Edited, Only can be Deleted!</i>",
                )
            await msg.edit(
                text=rply.text,
                entities=rply.entities,
                reply_markup=rply.reply_markup,
            )
            await sleep(0.3)
            success += 1
        except FloodWait as e:
            await sleep(e.value)
            try:
                msg = await TgClient.bot.get_messages(uid, msg_id)
                await msg.edit(
                    text=rply.text,
                    entities=rply.entities,
                    reply_markup=rply.reply_markup,
                )
                await sleep(0.3)
                success += 1
            except Exception as e:
                print(f"Error editing message for user {uid} after floodwait: {e}")
                failed += 1
        except Exception as e:
            print(f"Error editing message for user {uid}: {e}")
            failed += 1
        total += 1
    return await edit_message(
        temp_wait,
        f"""⌬  <b><i>Broadcast Edited Stats :</i></b>
┠ <b>Total Users:</b> <code>{total}</code>
┠ <b>Success:</b> <code>{success}</code>
┖ <b>Failed Attempts:</b> <code>{failed}</code>

<b>Broadcast ID:</b> <code>{bc_id}</code>""",
    )


def parse_broadcast_args(message):
    """Parse broadcast command arguments and flags."""
    bc_id = ""
    forwarded = quietly = deleted = edited = False
    msg_args = message.command if hasattr(message, "command") else []
    rply = getattr(message, "reply_to_message", None)

    if len(msg_args) > 1:
        if not msg_args[1].startswith("-"):
            bc_id = msg_args[1] if bc_cache.get(msg_args[1], False) else ""
        for arg in msg_args:
            if arg in ["-f", "-forward"] and rply:
                forwarded = True
            if arg in ["-q", "-quiet"] and rply:
                quietly = True
            elif arg in ["-d", "-delete"] and bc_id:
                deleted = True
            elif arg in ["-e", "-edit"] and bc_id and rply:
                edited = True
    return bc_id, forwarded, quietly, deleted, edited


@new_task
async def broadcast(_, message):
    """Handle different broadcast actions: send, edit, delete, or forward."""
    if not Config.DATABASE_URL:
        return await send_message(
            message, "DATABASE_URL not provided to fetch PM Users!"
        )
    rply = getattr(message, "reply_to_message", None)
    bc_id, forwarded, quietly, deleted, edited = parse_broadcast_args(message)
    if not bc_id and not rply:
        return await send_message(
            message,
            """<b>By replying to msg to Broadcast:</b>
/broadcast bc_id -d -e -f -q

<b>Forward Broadcast with Tag:</b> -f or -forward
/cmd [reply_msg] -f

<b>Quietly Broadcast msg:</b> -q or -quiet
/cmd [reply_msg] -q -f

<b>Edit Broadcast msg:</b> -e or -edit
/cmd [reply_edited_msg] broadcast_id -e

<b>Delete Broadcast msg:</b> -d or -delete
/bc broadcast_id -d

<b>Notes:</b>
1. Broadcast msgs can be only edited or deleted until restart.
2. Forwarded msgs can't be Edited""",
        )
    if deleted:
        return await delete_broadcast(bc_id, message)
    elif edited:
        return await edit_broadcast(bc_id, message, rply)

    # Broadcasting logic
    start_time = time()
    status_tpl = """⌬  <b><i>Broadcast Stats :</i></b>
┠ <b>Total Users:</b> <code>{t}</code>
┠ <b>Success:</b> <code>{s}</code>
┠ <b>Blocked Users:</b> <code>{b}</code>
┠ <b>Deleted Accounts:</b> <code>{d}</code>
┖ <b>Unsuccess Attempt:</b> <code>{u}</code>"""
    updater = time()
    bc_hash, bc_msgs = token_hex(5), []
    pls_wait = await send_message(message, status_tpl.format(t=0, s=0, b=0, d=0, u=0))
    t, s, b, d, u = 0, 0, 0, 0, 0
    pm_uids = await database.get_pm_uids()
    for uid in pm_uids:
        bc_msg = None
        try:
            if forwarded:
                bc_msg = await rply.forward(uid, disable_notification=quietly)
            else:
                bc_msg = await rply.copy(uid, disable_notification=quietly)
            s += 1
        except FloodWait as e:
            await sleep(e.value * 1.1)
            try:
                if forwarded:
                    bc_msg = await rply.forward(uid, disable_notification=quietly)
                else:
                    bc_msg = await rply.copy(uid, disable_notification=quietly)
                s += 1
            except Exception as e:
                print(f"Error broadcasting to user {uid} after floodwait: {e}")
                u += 1
        except UserIsBlocked:
            await database.rm_pm_user(uid)
            b += 1
        except InputUserDeactivated:
            await database.rm_pm_user(uid)
            d += 1
        except Exception as e:
            print(f"Error broadcasting message to user {uid}: {e}")
            u += 1
        if bc_msg:
            bc_msgs.append((uid, bc_msg.id))
        t += 1
        if (time() - updater) > 10:
            await edit_message(pls_wait, status_tpl.format(t=t, s=s, b=b, d=d, u=u))
            updater = time()
    if bc_msgs:
        bc_cache[bc_hash] = bc_msgs
    await edit_message(
        pls_wait,
        f"{status_tpl.format(t=t, s=s, b=b, d=d, u=u)}\n\n<b>Elapsed Time:</b> <code>{get_readable_time(time() - start_time)}</code>\n<b>Broadcast ID:</b> <code>{bc_hash}</code>",
    )
