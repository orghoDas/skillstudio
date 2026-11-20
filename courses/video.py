"""Parse lesson video URLs into something a player can use (LRN-02).

The learn page plays only sources whose playback it can observe, so watch time
can be reported honestly:

* YouTube  -> {"provider": "youtube", "id": "<video id>"}
* Vimeo    -> {"provider": "vimeo", "id": "<numeric id>"}
* direct video file over http(s) -> {"provider": "file", "url": "<url>"}

Anything else returns ``None``.
"""

import re
from urllib.parse import parse_qs, urlparse

_YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{6,20}$")
_YOUTUBE_HOSTS = {"youtube.com", "youtube-nocookie.com", "music.youtube.com"}
_VIDEO_FILE = re.compile(r"\.(mp4|webm|ogg|ogv|m4v|mov)$", re.IGNORECASE)


def _host(parsed):
    host = (parsed.hostname or "").lower()
    for prefix in ("www.", "m."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    return host


def parse_video_url(url):
    """Return a player descriptor for ``url`` or ``None`` if unsupported."""
    if not url or not isinstance(url, str):
        return None
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https"):
        return None

    host = _host(parsed)
    path = parsed.path or ""

    if host == "youtu.be":
        video_id = path.lstrip("/").split("/")[0]
        return {"provider": "youtube", "id": video_id} if _YOUTUBE_ID.match(video_id) else None

    if host in _YOUTUBE_HOSTS:
        if path == "/watch":
            video_id = (parse_qs(parsed.query).get("v") or [""])[0]
        else:
            match = re.match(r"^/(?:embed|shorts|live|v)/([^/?#]+)", path)
            video_id = match.group(1) if match else ""
        return {"provider": "youtube", "id": video_id} if _YOUTUBE_ID.match(video_id) else None

    if host == "vimeo.com":
        match = re.match(r"^/(?:channels/[^/]+/|groups/[^/]+/videos/)?(\d+)", path)
        return {"provider": "vimeo", "id": match.group(1)} if match else None

    if host == "player.vimeo.com":
        match = re.match(r"^/video/(\d+)", path)
        return {"provider": "vimeo", "id": match.group(1)} if match else None

    if _VIDEO_FILE.search(path):
        return {"provider": "file", "url": parsed.geturl()}

    return None
