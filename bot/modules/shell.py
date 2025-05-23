from io import BytesIO
import shlex
import traceback
from .. import LOGGER
from ..helper.ext_utils.bot_utils import cmd_exec, new_task
from ..helper.telegram_helper.message_utils import send_message, send_file


@new_task
async def run_shell(_, message):
    """
    Executes a shell command from the user's message and returns the output.
    - Handles empty commands, long outputs, and errors gracefully.
    - Redacts sensitive tokens from output.
    - Logs all command executions.
    """
    try:
        # Extract command
        parts = message.text.split(maxsplit=1)
        if len(parts) == 1 or not parts[1].strip():
            await send_message(message, "<b>No command to execute was given.</b>")
            return
        cmd = parts[1].strip()
        # Optionally, use shlex.split for better parsing (if not using shell=True)
        # args = shlex.split(cmd)

        # Notify user command is running
        running_msg = await send_message(
            message, f"<i>Running shell command:</i> <code>{cmd}</code>"
        )

        # Run the command
        stdout, stderr, _ = await cmd_exec(cmd, shell=True)

        # Redact sensitive info (example: tokens, passwords)
        def redact(text):
            # Add more patterns as needed
            import re

            patterns = [r"(token|password|secret)[=:]\s*\S+", r"ghp_\w+"]
            for pat in patterns:
                text = re.sub(pat, r"\1=[REDACTED]", text, flags=re.IGNORECASE)
            return text

        stdout = redact(stdout)
        stderr = redact(stderr)

        reply = ""
        if stdout:
            reply += f"<b>Stdout</b>\n<code>{stdout}</code>\n"
            LOGGER.info(f"Shell - {cmd} - STDOUT: {stdout}")
        if stderr:
            reply += f"<b>Stderr</b>\n<code>{stderr}</code>"
            LOGGER.error(f"Shell - {cmd} - STDERR: {stderr}")

        # Telegram message limit is 4096, but use 3000 for safety
        if len(reply) > 3000:
            with BytesIO(reply.encode()) as out_file:
                out_file.name = "shell_output.txt"
                await send_file(
                    message, out_file, caption=f"<b>Output for:</b> <code>{cmd}</code>"
                )
                await delete_message(running_msg)
        elif reply:
            await edit_message(running_msg, reply)
        else:
            await edit_message(
                running_msg, "<b>No output was returned by the command.</b>"
            )
    except Exception as e:
        tb = traceback.format_exc()
        LOGGER.error(f"Shell command error: {e}\n{tb}")
        await send_message(message, f"<b>Shell command failed:</b> <code>{e}</code>")
