import os
from os import getcwd, path as ospath
from re import search
from shlex import split

from aiofiles import open as aiopen
from aiofiles.os import mkdir, path as aiopath, remove as aioremove
from aiohttp import ClientSession

from .. import LOGGER
from ..core.tg_client import TgClient
from ..helper.ext_utils.bot_utils import cmd_exec
from ..helper.ext_utils.telegraph_helper import telegraph
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.telegram_helper.message_utils import send_message, edit_message

# Emoji mapping for info sections
SECTION_EMOJIS = {
    "General": "🗒",
    "Video": "🎞",
    "Audio": "🔊",
    "Text": "🔠",
    "Menu": "🗃",
}


async def gen_mediainfo(message, link=None, media=None, mmsg=None):
    """
    Generates a MediaInfo report for a file or URL and posts to Telegraph.
    """
    temp_send = await send_message(message, "<i>Generating MediaInfo...</i>")
    des_path = None
    tc = ""
    try:
        path = "mediainfo/"
        if not await aiopath.isdir(path):
            await mkdir(path)
        file_size = 0

        # Download from direct link
        if link:
            filename = search(r".+/(.+)", link)
            filename = filename.group(1) if filename else "tempfile"
            des_path = ospath.join(path, filename)
            headers = {
                "user-agent": (
                    "Mozilla/5.0 (Linux; Android 12; 2201116PI) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/107.0.0.0 Mobile Safari/537.36"
                )
            }
            async with ClientSession() as session:
                async with session.get(link, headers=headers) as response:
                    if response.status != 200:
                        raise Exception(
                            f"Failed to download file (HTTP {response.status})"
                        )
                    file_size = int(response.headers.get("Content-Length", 0))
                    async with aiopen(des_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(10_000_000):
                            await f.write(chunk)
                            break  # Download only first chunk for mediainfo

        # Download from Telegram media
        elif media:
            des_path = ospath.join(path, getattr(media, "file_name", "media"))
            file_size = getattr(media, "file_size", 0)
            if file_size <= 50_000_000:  # 50 MB
                await mmsg.download(ospath.join(getcwd(), des_path))
            else:
                async for chunk in TgClient.bot.stream_media(media, limit=5):
                    async with aiopen(des_path, "ab") as f:
                        await f.write(chunk)

        if not des_path or not await aiopath.exists(des_path):
            raise Exception("Failed to prepare file for MediaInfo.")

        stdout, _, _ = await cmd_exec(split(f'mediainfo "{des_path}"'))
        tc = f"<h4>📌 {ospath.basename(des_path)}</h4><br><br>"
        if stdout:
            tc += parseinfo(stdout, file_size)
        else:
            tc += "<i>No MediaInfo output generated.</i>"
    except Exception as e:
        LOGGER.error(f"MediaInfo Error: {e}")
        await edit_message(temp_send, f"MediaInfo stopped: <code>{e}</code>")
        return
    finally:
        if des_path and await aiopath.exists(des_path):
            await aioremove(des_path)
    # Post to Telegraph
    try:
        link_id = (await telegraph.create_page(title="MediaInfo X", content=tc))["path"]
        await temp_send.edit(
            f"<b>MediaInfo:</b>\n\n➲ <b>Link :</b> https://graph.org/{link_id}",
            disable_web_page_preview=False,
        )
    except Exception as e:
        await edit_message(temp_send, f"Failed to post MediaInfo to Telegraph: {e}")


def parseinfo(out, size):
    """
    Formats mediainfo CLI output to HTML with emoji sections and file size.
    """
    lines = out.strip().split("\n")
    tc, in_section = "", False
    size_line = (
        f"File size                                 : {size / (1024 * 1024):.2f} MiB"
    )
    for line in lines:
        # Section headers
        for section, emoji in SECTION_EMOJIS.items():
            if line.startswith(section):
                if in_section:
                    tc += "</pre><br>"
                tc += f"<h4>{emoji} {line.replace('Text', 'Subtitle')}</h4>"
                tc += "<br><pre>"
                in_section = True
                break
        else:
            # Replace file size line
            if line.startswith("File size"):
                line = size_line
            if in_section:
                tc += line + "\n"
    if in_section:
        tc += "</pre><br>"
    return tc


async def mediainfo(_, message):
    """
    Entrypoint for /mediainfo command.
    Determines if input is a link or a Telegram media reply, then generates report.
    """
    rply = getattr(message, "reply_to_message", None)
    help_msg = f"""
<b>By replying to media:</b>
<code>/{BotCommands.MediaInfoCommand[0]} or /{BotCommands.MediaInfoCommand[1]} [media]</code>

<b>By reply/sending download link:</b>
<code>/{BotCommands.MediaInfoCommand[0]} or /{BotCommands.MediaInfoCommand[1]} [link]</code>
"""
    # If command contains link as argument or reply is text
    if (len(message.command) > 1) or (rply and getattr(rply, "text", None)):
        link = rply.text if rply and getattr(rply, "text", None) else message.command[1]
        return await gen_mediainfo(message, link)
    elif rply:
        # Find the first available media type
        file = next(
            (
                i
                for i in [
                    getattr(rply, "document", None),
                    getattr(rply, "video", None),
                    getattr(rply, "audio", None),
                    getattr(rply, "voice", None),
                    getattr(rply, "animation", None),
                    getattr(rply, "video_note", None),
                ]
                if i is not None
            ),
            None,
        )
        if file:
            return await gen_mediainfo(message, None, file, rply)
        else:
            return await send_message(message, help_msg)
    else:
        return await send_message(message, help_msg)
