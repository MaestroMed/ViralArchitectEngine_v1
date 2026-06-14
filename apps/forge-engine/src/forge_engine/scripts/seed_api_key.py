"""Bootstrap CLI for API keys.

Usage:
    python -m forge_engine.scripts.seed_api_key create "iPhone Air — etostark__"
    python -m forge_engine.scripts.seed_api_key list
    python -m forge_engine.scripts.seed_api_key revoke <key_id>

Designed for the very first key — before /v1/api-keys is callable (chicken
and egg). After that the HTTP endpoints work the same.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime

from sqlalchemy import select, update

from forge_engine.core.database import async_session_maker, init_db
from forge_engine.models.api_key import ApiKey, generate_key, hash_key


async def _create(label: str) -> int:
    raw = generate_key()
    row = ApiKey(label=label, key_hash=hash_key(raw))
    async with async_session_maker() as db:
        db.add(row)
        await db.commit()
        await db.refresh(row)
    print(f"Created key id={row.id}")
    print(f"Label:   {label}")
    print(f"Key:     {raw}")
    print()
    print("Store this value now — it cannot be retrieved later.")
    print("Use it as the X-API-Key header on every /v1 request.")
    return 0


async def _list() -> int:
    async with async_session_maker() as db:
        result = await db.execute(
            select(ApiKey).order_by(ApiKey.created_at.desc())
        )
        rows = result.scalars().all()
    if not rows:
        print("(no keys)")
        return 0
    for r in rows:
        state = "revoked" if r.revoked_at else "active"
        last = r.last_used_at.isoformat() if r.last_used_at else "—"
        print(f"{r.id}  [{state:7}]  {r.label!r:40}  last_used={last}")
    return 0


async def _revoke(key_id: str) -> int:
    async with async_session_maker() as db:
        result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
        row = result.scalar_one_or_none()
        if row is None:
            print(f"No such key: {key_id}", file=sys.stderr)
            return 2
        if row.revoked_at is not None:
            print(f"Already revoked: {key_id}")
            return 0
        await db.execute(
            update(ApiKey).where(ApiKey.id == key_id).values(revoked_at=datetime.utcnow())
        )
        await db.commit()
    print(f"Revoked: {key_id}")
    return 0


async def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="forge-keys", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_create = sub.add_parser("create", help="Mint a new API key")
    p_create.add_argument("label", help="Human label (e.g. 'iPhone Air')")
    sub.add_parser("list", help="List all keys")
    p_revoke = sub.add_parser("revoke", help="Revoke a key by id")
    p_revoke.add_argument("key_id")
    args = parser.parse_args(argv)

    # init_db is safe to call: it's idempotent and ensures the api_keys table
    # exists even on a fresh DB.
    await init_db()

    if args.cmd == "create":
        return await _create(args.label)
    if args.cmd == "list":
        return await _list()
    if args.cmd == "revoke":
        return await _revoke(args.key_id)
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main(sys.argv[1:])))
