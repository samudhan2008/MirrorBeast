from contextlib import suppress
from re import IGNORECASE, findall, search

from imdb import Cinemagoer
from pycountry import countries as conn
from pyrogram.errors import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty

from ..core.tg_client import TgClient
from ..core.config_manager import Config
from ..helper.ext_utils.status_utils import get_readable_time
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.message_utils import (
    send_message,
    edit_message,
    delete_message,
)

imdb = Cinemagoer()

IMDB_GENRE_EMOJI = {
    "Action": "🚀",
    "Adult": "🔞",
    "Adventure": "🌋",
    "Animation": "🎠",
    "Biography": "📜",
    "Comedy": "🪗",
    "Crime": "🔪",
    "Documentary": "🎞",
    "Drama": "🎭",
    "Family": "👨‍👩‍👧‍👦",
    "Fantasy": "🫧",
    "Film Noir": "🎯",
    "Game Show": "🎮",
    "History": "🏛",
    "Horror": "🧟",
    "Musical": "🎻",
    "Music": "🎸",
    "Mystery": "🧳",
    "News": "📰",
    "Reality-TV": "🖥",
    "Romance": "🥰",
    "Sci-Fi": "🌠",
    "Short": "📝",
    "Sport": "⛳",
    "Talk-Show": "👨‍🍳",
    "Thriller": "🗡",
    "War": "⚔",
    "Western": "🪩",
}
LIST_ITEMS = 4


def safe_int(val, default=None):
    try:
        return int(val)
    except Exception:
        return default


def safe_str(val, default=""):
    return str(val) if val else default


def safe_list(val):
    return val if isinstance(val, list) else ([val] if val else [])


def list_to_str(k):
    if not k:
        return ""
    k = safe_list(k)
    if len(k) == 1:
        return safe_str(k[0])
    if LIST_ITEMS:
        k = k[:LIST_ITEMS]
        return " ".join(f"{elem}," for elem in k)[:-1] + " ..."
    return " ".join(f"{elem}," for elem in k)[:-1]


def list_to_hash(k, flagg=False, emoji=False):
    k = safe_list(k)
    listing = ""
    if not k:
        return ""
    if len(k) == 1:
        elem = k[0]
        ele = elem.replace(" ", "_").replace("-", "_")
        if flagg:
            try:
                conflag = (conn.get(name=elem)).flag
                return f"{conflag} #{ele}"
            except Exception:
                return f"#{ele}"
        if emoji:
            return f"{IMDB_GENRE_EMOJI.get(elem, '')} #{ele}"
        return f"#{ele}"
    # Multiple items
    k = k[:LIST_ITEMS] if LIST_ITEMS else k
    for elem in k:
        ele = elem.replace(" ", "_").replace("-", "_")
        if flagg:
            with suppress(AttributeError):
                conflag = (conn.get(name=elem)).flag
                listing += f"{conflag} "
        if emoji:
            listing += f"{IMDB_GENRE_EMOJI.get(elem, '')} "
        listing += f"#{ele}, "
    return listing[:-2]


def get_movie_year(query, file=None):
    query = (query.strip()).lower()
    year = findall(r"[1-2]\d{3}$", query, IGNORECASE)
    if year:
        return list_to_str(year[:1]), (query.replace(year[0], "")).strip()
    elif file is not None:
        year = findall(r"[1-2]\d{3}", file, IGNORECASE)
        if year:
            return list_to_str(year[:1]), query
    return None, query


def get_poster(query, bulk=False, id=False, file=None):
    if not id:
        year, title = get_movie_year(query, file)
        movieid = imdb.search_movie(title.lower(), results=10)
        if not movieid:
            return None
        filtered = (
            (
                list(filter(lambda k: str(k.get("year")) == str(year), movieid))
                or movieid
            )
            if year
            else movieid
        )
        filtered = (
            list(filter(lambda k: k.get("kind") in ["movie", "tv series"], filtered))
            or filtered
        )
        if bulk:
            return filtered
        movieid = filtered[0].movieID
    else:
        movieid = query
    movie = imdb.get_movie(movieid)
    date = movie.get("original air date") or movie.get("year") or "N/A"
    plot = movie.get("plot")
    plot = plot[0] if plot and len(plot) > 0 else movie.get("plot outline")
    if plot and len(plot) > 300:
        plot = f"{plot[:300]}..."
    # Defensive for missing keys
    return {
        "title": movie.get("title", ""),
        "trailer": movie.get("videos"),
        "votes": movie.get("votes"),
        "aka": list_to_str(movie.get("akas")),
        "seasons": movie.get("number of seasons"),
        "box_office": movie.get("box office"),
        "localized_title": movie.get("localized title"),
        "kind": movie.get("kind"),
        "imdb_id": f"tt{movie.get('imdbID', movieid)}",
        "cast": list_to_str(movie.get("cast")),
        "runtime": list_to_str(
            [get_readable_time(int(run) * 60) for run in movie.get("runtimes", ["0"])]
        ),
        "countries": list_to_hash(movie.get("countries"), True),
        "certificates": list_to_str(movie.get("certificates")),
        "languages": list_to_hash(movie.get("languages")),
        "director": list_to_str(movie.get("director")),
        "writer": list_to_str(movie.get("writer")),
        "producer": list_to_str(movie.get("producer")),
        "composer": list_to_str(movie.get("composer")),
        "cinematographer": list_to_str(movie.get("cinematographer")),
        "music_team": list_to_str(movie.get("music department")),
        "distributors": list_to_str(movie.get("distributors")),
        "release_date": date,
        "year": movie.get("year"),
        "genres": list_to_hash(movie.get("genres"), emoji=True),
        "poster": movie.get("full-size cover url"),
        "plot": plot,
        "rating": f"{movie.get('rating', '')} / 10",
        "url": f"https://www.imdb.com/title/tt{movieid}",
        "url_cast": f"https://www.imdb.com/title/tt{movieid}/fullcredits#cast",
        "url_releaseinfo": f"https://www.imdb.com/title/tt{movieid}/releaseinfo",
    }


async def imdb_search(_, message):
    if " " in message.text:
        k = await send_message(message, "<i>Searching IMDb ...</i>")
        title = message.text.split(" ", 1)[1]
        user_id = message.from_user.id
        buttons = ButtonMaker()
        imdb_url_match = search(r"imdb\.com/title/tt(\d+)", title, IGNORECASE)
        if imdb_url_match:
            movieid = imdb_url_match.group(1)
            movie = imdb.get_movie(movieid)
            if movie:
                buttons.data_button(
                    f"🎬 {movie.get('title', '')} ({movie.get('year', '')})",
                    f"imdb {user_id} movie {movieid}",
                )
            else:
                return await edit_message(k, "<i>No Results Found</i>")
        else:
            movies = get_poster(title, bulk=True)
            if not movies:
                return await edit_message(
                    k, "<i>No Results Found</i>, Try Again or Use <b>Title ID</b>"
                )
            for movie in movies:
                buttons.data_button(
                    f"🎬 {movie.get('title', '')} ({movie.get('year', '')})",
                    f"imdb {user_id} movie {movie.movieID}",
                )
        buttons.data_button("🚫 Close 🚫", f"imdb {user_id} close")
        await edit_message(
            k, "<b><i>Search Results found on IMDb.com</i></b>", buttons.build_menu(1)
        )
    else:
        await send_message(
            message,
            "<i>Send Movie / TV Series Name along with /imdb Command or send IMDb URL</i>",
        )


async def imdb_callback(_, query):
    message = query.message
    user_id = query.from_user.id
    data = query.data.split()
    if user_id != int(data[1]):
        await query.answer("Not Yours!", show_alert=True)
        return
    elif data[2] == "movie":
        await query.answer()
        imdb_data = get_poster(query=data[3], id=True)
        buttons = ButtonMaker()
        # Trailer button logic
        if imdb_data.get("trailer"):
            trailer = imdb_data["trailer"]
            if isinstance(trailer, list):
                buttons.url_button("▶️ IMDb Trailer ", trailer[-1])
            else:
                buttons.url_button("▶️ IMDb Trailer ", trailer)
        buttons.data_button("🚫 Close 🚫", f"imdb {user_id} close")
        buttons = buttons.build_menu(1)
        template = Config.IMDB_TEMPLATE or ""
        cap = template.format(**imdb_data) if imdb_data and template else "No Results"
        poster = imdb_data.get("poster")
        reply_to = getattr(message, "reply_to_message", None)
        if poster:
            try:
                await TgClient.bot.send_photo(
                    chat_id=reply_to.chat.id,
                    caption=cap,
                    photo=poster,
                    reply_to_message_id=reply_to.id,
                    reply_markup=buttons,
                )
            except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
                poster = poster.replace(".jpg", "._V1_UX360.jpg")
                await send_message(reply_to, cap, buttons, photo=poster)
        else:
            await send_message(
                reply_to,
                cap,
                buttons,
                "https://telegra.ph/file/5af8d90a479b0d11df298.jpg",
            )
        await delete_message(message)
    else:
        await query.answer()
        await delete_message(message, getattr(message, "reply_to_message", message))
