import xml.etree.ElementTree as ET
from aiohttp import ClientSession

from .. import LOGGER
from ..core.config_manager import Config
from ..helper.ext_utils.bot_utils import new_task
from ..helper.ext_utils.status_utils import get_readable_file_size
from ..helper.ext_utils.telegraph_helper import telegraph
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.message_utils import edit_message, send_message


@new_task
async def hydra_search(_, message):
    """
    Handles the /nzbsearch command: parses query, fetches results, and posts a Telegraph page.
    """
    key = message.text.split(maxsplit=1)
    if len(key) == 1:
        await send_message(
            message,
            "Please provide a search query. Example: `/nzbsearch movie title`.",
        )
        return

    query = key[1].strip()
    progress_msg = await send_message(message, f"🔎 Searching for '<b>{query}</b>'...")
    try:
        items = await search_nzbhydra(query)
        if not items:
            await edit_message(progress_msg, "No results found.")
            LOGGER.info(f"No results found for NZBHydra search: {query}")
            return

        page_url = await create_telegraph_page(query, items)
        buttons = ButtonMaker()
        buttons.url_button("📰 Results", page_url)
        button = buttons.build_menu()
        await edit_message(
            progress_msg,
            f"<b>Search results for:</b> <code>{query}</code>",
            button,
        )
    except Exception as e:
        LOGGER.exception(f"Error in hydra_search: {e!s}")
        await edit_message(progress_msg, "❌ Something went wrong. Please try again later.")


async def search_nzbhydra(query, limit=50):
    """
    Performs a search using NZBHydra API.
    Returns a list of XML <item> elements, or None if errors occur.
    """
    if not Config.HYDRA_IP or not Config.HYDRA_API_KEY:
        LOGGER.error("HYDRA_IP or HYDRA_API_KEY is not configured.")
        return None

    search_url = f"{Config.HYDRA_IP.rstrip('/')}/api"
    params = {
        "apikey": Config.HYDRA_API_KEY,
        "t": "search",
        "q": query,
        "limit": limit,
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/58.0.3029.110 Safari/537.3"
        ),
    }

    async with ClientSession() as session:
        try:
            async with session.get(
                search_url,
                params=params,
                headers=headers,
            ) as response:
                content = await response.text()
                if response.status == 200:
                    try:
                        root = ET.fromstring(content)
                        items = root.findall(".//item")
                        LOGGER.info(f"NZBHydra returned {len(items)} results for '{query}'")
                        return items
                    except ET.ParseError as parse_err:
                        LOGGER.error(f"Failed to parse NZBHydra XML: {parse_err!s}")
                        return None
                LOGGER.error(f"NZBHydra API failed. Status: {response.status}")
                LOGGER.error(f"Response Text: {content}")
                return None
        except Exception as e:
            LOGGER.error(f"Exception during NZBHydra search: {e!s}")
            return None


async def create_telegraph_page(query, items):
    """
    Creates a Telegraph page with formatted NZB search results.
    Returns the Telegraph page URL.
    """
    sorted_items = sorted(
        (
            int(item.findtext("size", default="0")), item
        )
        for item in items[:100]
    )
    sorted_items.sort(reverse=True, key=lambda x: x[0])

    content_lines = [f"<b>Search Results for:</b> <code>{query}</code><br><br>"]
    for idx, (size_bytes, item) in enumerate(sorted_items, 1):
        title = item.findtext("title", default="No Title Available")
        download_url = item.findtext("link", default=None)
        size = get_readable_file_size(size_bytes) if size_bytes else "Unknown"

        content_lines.append(
            f"{idx}. <b>{title}</b><br>"
            f"{_make_links(download_url)}"
            f"<b>Size:</b> {size}<br>"
            f"━━━━━━━━━━━━━━━━━━━━━━<br><br>"
        )

    page_content = "".join(content_lines)

    response = await telegraph.create_page(
        title=f"NZB Search: {query}",
        content=page_content,
    )
    LOGGER.info(f"Telegraph page created for NZBHydra search: {query}")
    return f"https://telegra.ph/{response['path']}"


def _make_links(url):
    """
    Helper to create download/share links HTML for a given URL.
    """
    if not url or url == "No Link Available":
        return "<i>No Download URL Available</i><br>"
    safe_url = url.replace("'", "%27")
    return (
        f"<b><a href='{safe_url}'>Download URL</a> | "
        f"<a href='http://t.me/share/url?url={safe_url}'>Share Download URL</a></b><br>"
    )