"""Security helpers — path validation, allowlisting."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from pathlib import Path

from forge_engine.core.config import settings

logger = logging.getLogger(__name__)


class SourcePathError(ValueError):
    """Raised when a caller-supplied source path fails validation."""


def _parse_roots_env(raw: str | None) -> list[Path]:
    if not raw:
        return []
    # Accept OS-native separator (":" on POSIX, ";" on Windows) and also ","
    separators = [os.pathsep, ","]
    parts: list[str] = [raw]
    for sep in separators:
        parts = [segment for chunk in parts for segment in chunk.split(sep)]
    roots: list[Path] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        try:
            roots.append(Path(p).expanduser().resolve())
        except (OSError, RuntimeError) as exc:
            logger.warning("Ignoring invalid import root %r: %s", p, exc)
    return roots


def allowed_import_roots() -> list[Path]:
    """Return the set of filesystem roots from which source videos may be imported.

    Always includes LIBRARY_PATH and the current user's home directory (this is a
    personal desktop tool). Additional roots may be configured via the
    FORGE_ALLOWED_IMPORT_ROOTS env var (OS-native path separator or comma).
    """
    roots: list[Path] = []
    try:
        roots.append(settings.LIBRARY_PATH.resolve())
    except (OSError, RuntimeError):
        pass
    try:
        roots.append(Path.home().resolve())
    except (OSError, RuntimeError):
        pass
    roots.extend(_parse_roots_env(os.environ.get("FORGE_ALLOWED_IMPORT_ROOTS")))
    # Dedupe while preserving order
    seen: set[str] = set()
    deduped: list[Path] = []
    for r in roots:
        key = str(r)
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped


def _is_within(candidate: Path, roots: Iterable[Path]) -> bool:
    for root in roots:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def validate_source_path(raw_path: str) -> Path:
    """Validate a user-supplied source media path.

    Rejects:
      - empty / non-string inputs
      - paths containing NUL or other ASCII control chars
      - paths that don't resolve to an existing regular file
      - paths whose resolved location is outside the allowlisted roots (prevents
        path traversal and symlink-escape attacks)

    Returns the canonical resolved Path on success.
    """
    if not isinstance(raw_path, str):
        raise SourcePathError("source_path must be a string")
    path_str = raw_path.strip()
    if not path_str:
        raise SourcePathError("source_path must not be empty")
    if any(ord(ch) < 32 for ch in path_str):
        raise SourcePathError("source_path contains control characters")

    try:
        resolved = Path(path_str).expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise SourcePathError(f"source file not found: {path_str}") from exc
    except (OSError, RuntimeError) as exc:
        raise SourcePathError(f"invalid source_path: {exc}") from exc

    if not resolved.is_file():
        raise SourcePathError("source_path must point to a regular file")

    roots = allowed_import_roots()
    if not _is_within(resolved, roots):
        logger.warning(
            "Rejected source_path %s: not inside any allowed root (%s)",
            resolved,
            ", ".join(str(r) for r in roots),
        )
        raise SourcePathError(
            "source_path is outside the allowed import roots; "
            "set FORGE_ALLOWED_IMPORT_ROOTS to extend the allowlist"
        )

    return resolved
