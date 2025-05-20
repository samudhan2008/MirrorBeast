from aiofiles import open as aiopen
from contextlib import redirect_stdout, suppress
from io import StringIO, BytesIO
from os import path as ospath, getcwd, chdir
from textwrap import indent
from traceback import format_exc

from .. import LOGGER
from ..core.tg_client import TgClient
from ..helper.ext_utils.bot_utils import sync_to_async, new_task
from ..helper.telegram_helper.message_utils import send_file, send_message

namespaces = {}

def namespace_of(message):
    """
    Returns a unique namespace (dict) for each chat.
    Initializes with some useful objects/variables.
    """
    chat_id = message.chat.id
    if chat_id not in namespaces:
        namespaces[chat_id] = {
            "__name__": "__main__",
            "__file__": "<exec>",
            "__builtins__": globals()["__builtins__"],
            "bot": TgClient.bot,
            "message": message,
            "user": message.from_user or message.sender_chat,
            "chat": message.chat,
        }
    return namespaces[chat_id]

def log_input(message):
    user = message.from_user or message.sender_chat
    LOGGER.info(
        f"IN: {message.text} (user={getattr(user, 'id', None)}, chat={message.chat.id})"
    )

async def send(msg, message):
    """
    Sends result as file if large, else as code message.
    """
    msg_s = str(msg)
    if len(msg_s) > 2000:
        with BytesIO(msg_s.encode()) as out_file:
            out_file.name = "output.txt"
            await send_file(message, out_file)
    else:
        LOGGER.info(f"OUT: '{msg_s[:256]}'{'...' if len(msg_s) > 256 else ''}")
        await send_message(message, f"<code>{msg_s}</code>")

def cleanup_code(code):
    """
    Removes code block markers and whitespace.
    """
    code = code.strip()
    if code.startswith("```") and code.endswith("```"):
        return "\n".join(code.split("\n")[1:-1])
    return code.strip("` \n")

async def do(func, message):
    """
    Core executor for exec/aexec commands.
    """
    log_input(message)
    if len(message.text.split(maxsplit=1)) < 2:
        return "No code found to execute."
    content = message.text.split(maxsplit=1)[1]
    body = cleanup_code(content)
    env = namespace_of(message)
    temp_file = ospath.join(getcwd(), "bot/modules/temp.txt")

    try:
        async with aiopen(temp_file, "w") as temp:
            await temp.write(body)
    except Exception as e:
        LOGGER.error(f"Failed to save temp code: {e}")

    stdout = StringIO()

    try:
        if func == "exec":
            exec(f"def func():\n{indent(body, '  ')}", env)
        else:
            exec(f"async def func():\n{indent(body, '  ')}", env)
    except Exception as e:
        return f"{e.__class__.__name__}: {e}"

    rfunc = env["func"]

    try:
        with redirect_stdout(stdout):
            if func == "exec":
                func_return = await sync_to_async(rfunc)
            else:
                func_return = await rfunc()
    except Exception:
        value = stdout.getvalue()
        return f"{value}{format_exc()}"
    else:
        value = stdout.getvalue()
        if func_return is None:
            if value:
                return value
            with suppress(Exception):
                eval_result = await sync_to_async(eval, body, env)
                return f"{repr(eval_result)}"
        return f"{value}{func_return}" if func_return is not None else value

@new_task
async def aioexecute(_, message):
    """Executes async Python code in an isolated per-chat namespace."""
    await send(await do("aexec", message), message)

@new_task
async def execute(_, message):
    """Executes sync Python code in an isolated per-chat namespace."""
    await send(await do("exec", message), message)

@new_task
async def clear(_, message):
    """
    Clears the local namespace for the current chat.
    """
    log_input(message)
    global namespaces
    chat_id = message.chat.id
    if chat_id in namespaces:
        del namespaces[chat_id]
    await send("Locals Cleared.", message)