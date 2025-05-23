from asyncio import gather
from json import loads
from secrets import token_hex

from aiofiles.os import remove

from .. import LOGGER, bot_loop, task_dict, task_dict_lock
from ..core.config_manager import BinConfig
from ..helper.ext_utils.bot_utils import (
    COMMAND_USAGE,
    arg_parser,
    cmd_exec,
    sync_to_async,
)
from ..helper.ext_utils.exceptions import DirectDownloadLinkException
from ..helper.ext_utils.links_utils import (
    is_gdrive_id,
    is_gdrive_link,
    is_rclone_path,
    is_share_link,
)
from ..helper.ext_utils.task_manager import (
    pre_task_check,
    stop_duplicate_check,
    limit_checker,
)
from ..helper.ext_utils.status_utils import get_readable_file_size
from ..helper.listeners.task_listener import TaskListener
from ..helper.mirror_leech_utils.download_utils.direct_link_generator import (
    direct_link_generator,
)
from ..helper.mirror_leech_utils.gdrive_utils.clone import GoogleDriveClone
from ..helper.mirror_leech_utils.gdrive_utils.count import GoogleDriveCount
from ..helper.mirror_leech_utils.rclone_utils.transfer import RcloneTransferHelper
from ..helper.mirror_leech_utils.status_utils.gdrive_status import GoogleDriveStatus
from ..helper.mirror_leech_utils.status_utils.rclone_status import RcloneStatus
from ..helper.telegram_helper.message_utils import (
    auto_delete_message,
    delete_links,
    delete_message,
    send_message,
    send_status_message,
)


class Clone(TaskListener):
    def __init__(
        self,
        client,
        message,
        _=None,
        __=None,
        ___=None,
        ____=None,
        _____=None,
        bulk=None,
        multi_tag=None,
        options="",
    ):
        super().__init__()
        self.client = client
        self.message = message
        self.multi_tag = multi_tag
        self.options = options
        self.same_dir = {}
        self.bulk = bulk or []
        self.is_clone = True

    async def new_event(self):
        text = self.message.text.split("\n")
        input_list = text[0].split(" ")

        check_msg, check_button = await pre_task_check(self.message)
        if check_msg:
            await delete_links(self.message)
            await auto_delete_message(
                await send_message(self.message, check_msg, check_button)
            )
            return

        args = {
            "link": "",
            "-i": 0,
            "-b": False,
            "-n": "",
            "-up": "",
            "-rcf": "",
            "-sync": False,
        }
        arg_parser(input_list[1:], args)
        self.up_dest = args["-up"]
        self.rc_flags = args["-rcf"]
        self.link = args["link"]
        self.name = args["-n"]

        # Multi and bulk
        try:
            self.multi = int(args["-i"])
        except Exception:
            self.multi = 0

        is_bulk = args["-b"]
        sync = args["-sync"]
        bulk_start = 0
        bulk_end = 0

        if not isinstance(is_bulk, bool) and is_bulk:
            dargs = is_bulk.split(":")
            bulk_start = int(dargs[0] or 0)
            if len(dargs) == 2:
                bulk_end = int(dargs[1] or 0)
            is_bulk = True

        if is_bulk:
            await self.init_bulk(input_list, bulk_start, bulk_end, Clone)
            return

        await self.get_tag(text)

        if not self.link and (reply_to := self.message.reply_to_message):
            self.link = reply_to.text.split("\n", 1)[0].strip()

        await self.run_multi(input_list, Clone)

        if not self.link:
            await send_message(
                self.message, COMMAND_USAGE["clone"][0], COMMAND_USAGE["clone"][1]
            )
            await delete_links(self.message)
            return

        LOGGER.info(f"Clone link: {self.link}")
        try:
            await self.before_start()
        except Exception as e:
            await send_message(self.message, str(e))
            await delete_links(self.message)
            return

        self._set_mode_engine()
        await delete_links(self.message)
        await self._proceed_to_clone(sync)

    async def _proceed_to_clone(self, sync):
        # Handle share links
        if is_share_link(self.link):
            try:
                self.link = await sync_to_async(direct_link_generator, self.link)
                LOGGER.info(f"Generated direct link: {self.link}")
            except DirectDownloadLinkException as e:
                LOGGER.error(str(e))
                if str(e).startswith("ERROR:"):
                    await send_message(self.message, str(e))
                    return

        if is_gdrive_link(self.link) or is_gdrive_id(self.link):
            await self._handle_gdrive_clone()
        elif is_rclone_path(self.link):
            await self._handle_rclone_clone(sync)
        else:
            await send_message(
                self.message, COMMAND_USAGE["clone"][0], COMMAND_USAGE["clone"][1]
            )

    async def _handle_gdrive_clone(self):
        self.name, mime_type, self.size, files, _ = await sync_to_async(
            GoogleDriveCount().count, self.link, self.user_id
        )
        if mime_type is None:
            await send_message(self.message, self.name)
            return
        msg, button = await stop_duplicate_check(self)
        if msg:
            await send_message(self.message, msg, button)
            return
        if limit_exceeded := await limit_checker(self):
            await send_message(
                self.message,
                f"""〶 <b><i><u>Limit Breached:</u></i></b>

╭ <b>Task Size</b> → {get_readable_file_size(self.size)}
├ <b>In Mode</b> → {self.mode[0]}
├ <b>Out Mode</b> → {self.mode[1]}
╰ {limit_exceeded}""",
            )
            return
        await self.on_download_start()
        LOGGER.info(f"Clone Started: Name: {self.name} - Source: {self.link}")
        drive = GoogleDriveClone(self)
        show_status_msg = self.multi <= 1
        # For small file counts, show simple cloning message
        msg = None
        if files <= 10:
            msg = await send_message(self.message, f"Cloning: <code>{self.link}</code>")
        else:
            gid = token_hex(5)
            async with task_dict_lock:
                task_dict[self.mid] = GoogleDriveStatus(self, drive, gid, "cl")
            if show_status_msg:
                await send_status_message(self.message)
        flink, mime_type, files, folders, dir_id = await sync_to_async(drive.clone)
        if msg:
            await delete_message(msg)
        if not flink:
            return
        await self.on_upload_complete(flink, files, folders, mime_type, dir_id=dir_id)
        LOGGER.info(f"Cloning Done: {self.name}")

    async def _handle_rclone_clone(self, sync):
        # Handle custom rclone config
        if self.link.startswith("mrcc:"):
            self.link = self.link.replace("mrcc:", "", 1)
            self.up_dest = self.up_dest.replace("mrcc:", "", 1)
            config_path = f"rclone/{self.user_id}.conf"
        else:
            config_path = "rclone.conf"

        remote, src_path = self.link.split(":", 1)
        src_path = src_path.strip("/")
        self.link = src_path

        # Handle rclone_select
        if self.link.startswith("rclone_select"):
            mime_type = "Folder"
            src_path = ""
            if not self.name:
                self.name = self.link
        else:
            cmd = [
                BinConfig.RCLONE_NAME,
                "lsjson",
                "--fast-list",
                "--stat",
                "--no-modtime",
                "--config",
                config_path,
                f"{remote}:{src_path}",
                "-v",
                "--log-systemd",
            ]
            res = await cmd_exec(cmd)
            if res[2] != 0:
                if res[2] != -9:
                    msg = f"Error: While getting rclone stat. Path: {remote}:{src_path}. Stderr: {res[1][:4000]}"
                    await send_message(self.message, msg)
                return
            rstat = loads(res[0])
            if rstat.get("IsDir"):
                if not self.name:
                    self.name = src_path.rsplit("/", 1)[-1] if src_path else remote
                self.up_dest += (
                    self.name if self.up_dest.endswith(":") else f"/{self.name}"
                )
                mime_type = "Folder"
            else:
                if not self.name:
                    self.name = src_path.rsplit("/", 1)[-1]
                mime_type = rstat.get("MimeType", "")

        await self.on_download_start()
        RCTransfer = RcloneTransferHelper(self)
        LOGGER.info(
            f"Clone Started: Name: {self.name} - Source: {self.link} - Destination: {self.up_dest}"
        )
        gid = token_hex(5)
        async with task_dict_lock:
            task_dict[self.mid] = RcloneStatus(self, RCTransfer, gid, "cl")
        if self.multi <= 1:
            await send_status_message(self.message)
        method = "sync" if sync else "copy"
        flink, destination = await RCTransfer.clone(
            config_path,
            remote,
            src_path,
            mime_type,
            method,
        )
        if self.link.startswith("rclone_select"):
            await remove(self.link)
        if not destination:
            return
        LOGGER.info(f"Cloning Done: {self.name}")

        # Gather rclone stats for completion
        cmd1 = [
            BinConfig.RCLONE_NAME,
            "lsf",
            "--fast-list",
            "-R",
            "--files-only",
            "--config",
            config_path,
            destination,
            "-v",
            "--log-systemd",
        ]
        cmd2 = [
            BinConfig.RCLONE_NAME,
            "lsf",
            "--fast-list",
            "-R",
            "--dirs-only",
            "--config",
            config_path,
            destination,
            "-v",
            "--log-systemd",
        ]
        cmd3 = [
            BinConfig.RCLONE_NAME,
            "size",
            "--fast-list",
            "--json",
            "--config",
            config_path,
            destination,
            "-v",
            "--log-systemd",
        ]
        res1, res2, res3 = await gather(
            cmd_exec(cmd1),
            cmd_exec(cmd2),
            cmd_exec(cmd3),
        )
        if res1[2] != 0 or res2[2] != 0 or res3[2] != 0:
            if res1[2] == -9:
                return
            files = None
            folders = None
            self.size = 0
            error = res1[1] or res2[1] or res3[1]
            msg = f"Error: While getting rclone stat. Path: {destination}. Stderr: {error[:4000]}"
            await self.on_upload_error(msg)
        else:
            files = len(res1[0].split("\n")) if res1[0] else 0
            folders = len(res2[0].strip().split("\n")) if res2[0] else 0
            rsize = loads(res3[0])
            self.size = rsize.get("bytes", 0)
            await self.on_upload_complete(flink, files, folders, mime_type, destination)


async def clone_node(client, message):
    bot_loop.create_task(Clone(client, message).new_event())
