"""HTTP Range request support for video streaming.

FastAPI's FileResponse advertises ``Accept-Ranges: bytes`` but doesn't
actually serve 206 Partial Content — every Range request gets the whole
file. That's a real problem for the iPhone preview path, where AVPlayer
needs to scrub by fetching small ranges over and over: a 30 MB clip would
be re-downloaded entirely on every seek.

This helper parses ``Range: bytes=...`` exactly per RFC 7233 and returns
either a 206 with the requested slice or a normal 200 streaming the whole
file. Single-range only (multipart byte-ranges are vanishingly rare and
not worth the complexity).
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import Response, StreamingResponse

logger = logging.getLogger(__name__)

# Block size for streaming. 1 MiB keeps memory low without making the loop
# overhead noticeable on local-disk reads.
CHUNK = 1024 * 1024

_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


def _parse_range(header: str, file_size: int) -> tuple[int, int] | None:
    """Return inclusive (start, end) byte offsets, or None if malformed.

    ``bytes=0-1023``    → 0–1023 (first 1024 bytes)
    ``bytes=1024-``     → 1024–EOF
    ``bytes=-500``      → last 500 bytes
    """
    match = _RANGE_RE.match(header.strip())
    if match is None:
        return None
    start_raw, end_raw = match.group(1), match.group(2)
    if not start_raw and not end_raw:
        return None
    if not start_raw:
        # Suffix range: last N bytes.
        length = int(end_raw)
        if length <= 0:
            return None
        start = max(0, file_size - length)
        end = file_size - 1
    else:
        start = int(start_raw)
        end = int(end_raw) if end_raw else file_size - 1
    if start < 0 or end >= file_size or start > end:
        return None
    return start, end


def _iter_file(path: Path, start: int, length: int):
    """Yield ``length`` bytes from ``path`` starting at ``start``. Caller
    owns the file lifetime — we open here and let the response close it."""
    remaining = length
    with path.open("rb") as f:
        f.seek(start)
        while remaining > 0:
            chunk = f.read(min(CHUNK, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def serve_file_with_range(
    request: Request,
    path: Path,
    media_type: str,
    cache_control: str = "public, max-age=3600",
) -> Response:
    """Serve ``path`` honouring an optional ``Range`` request header.

    Returns:
        - 416 Range Not Satisfiable if the header is present but malformed
          or out-of-bounds (per RFC 7233 §4.4).
        - 206 Partial Content with the requested slice when the header is
          well-formed.
        - 200 OK streaming the whole file when no Range header is present.
    """
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        file_size = path.stat().st_size
    except OSError as exc:
        logger.warning("stat() failed for %s: %s", path, exc)
        raise HTTPException(status_code=500, detail="Cannot stat file") from exc

    base_headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": cache_control,
        # Helps proxies cache by content rather than URL when relevant.
        "Content-Type": media_type,
    }

    range_header = request.headers.get("range") or request.headers.get("Range")
    if range_header is None:
        # Full-content path — stream the whole file.
        return StreamingResponse(
            _iter_file(path, 0, file_size),
            media_type=media_type,
            headers={**base_headers, "Content-Length": str(file_size)},
        )

    parsed = _parse_range(range_header, file_size)
    if parsed is None:
        return Response(
            status_code=416,
            headers={**base_headers, "Content-Range": f"bytes */{file_size}"},
        )
    start, end = parsed
    length = end - start + 1
    headers = {
        **base_headers,
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Content-Length": str(length),
    }
    return StreamingResponse(
        _iter_file(path, start, length),
        status_code=206,
        media_type=media_type,
        headers=headers,
    )


# ─── Helper for tests ────────────────────────────────────────────────────────

def _make_tmp_file(path: str | os.PathLike, payload: bytes) -> Path:
    """Test helper: write ``payload`` and return the Path. Lives here so the
    test module doesn't need to know the I/O details we assume above."""
    p = Path(path)
    p.write_bytes(payload)
    return p
