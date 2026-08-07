"""AsyncSqliteSaver registry for workflow checkpoints.

aiosqlite connections are bound to the event loop that created them, so one
saver is kept per running loop instead of a single process-wide instance
(production serves all requests on one loop; tests spin up many).
"""

import asyncio
import os
from typing import Dict, Optional

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "workflow_checkpoints.sqlite3"
)

_locks: Dict[int, asyncio.Lock] = {}
_connections: Dict[int, aiosqlite.Connection] = {}
_savers: Dict[int, AsyncSqliteSaver] = {}


def _db_path() -> str:
    return os.environ.get("WORKFLOW_CHECKPOINT_DB", _DEFAULT_DB_PATH)


async def get_checkpointer() -> AsyncSqliteSaver:
    key = id(asyncio.get_running_loop())
    if key in _savers:
        return _savers[key]
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        if key not in _savers:
            path = os.path.abspath(_db_path())
            os.makedirs(os.path.dirname(path), exist_ok=True)
            connection = await aiosqlite.connect(path)
            saver = AsyncSqliteSaver(connection)
            await saver.setup()
            _connections[key] = connection
            _savers[key] = saver
    return _savers[key]


async def close_checkpointer() -> None:
    """Close the saver bound to the current loop (FastAPI lifespan)."""
    loop_key: Optional[int] = None
    try:
        loop_key = id(asyncio.get_running_loop())
    except RuntimeError:
        pass
    keys = [loop_key] if loop_key in _connections else list(_connections)
    for key in keys:
        connection = _connections.pop(key, None)
        _savers.pop(key, None)
        _locks.pop(key, None)
        if connection is not None:
            try:
                await connection.close()
            except RuntimeError:
                # Connection belongs to an already-closed loop; nothing to do.
                pass


def _close_connection_sync(connection: aiosqlite.Connection) -> None:
    try:
        asyncio.run(connection.close())
    except Exception:
        pass


async def close_all_checkpointers() -> None:
    """Close every registered saver, including ones bound to other loops.

    Foreign-loop connections are closed on a throwaway loop inside a worker
    thread; aiosqlite resolves their futures with call_soon_threadsafe, so
    this is safe from any event loop.
    """
    current_loop: Optional[asyncio.AbstractEventLoop] = None
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        pass
    foreign = []
    for key, connection in list(_connections.items()):
        _connections.pop(key, None)
        _savers.pop(key, None)
        _locks.pop(key, None)
        if current_loop is not None and key == id(current_loop):
            try:
                await connection.close()
            except RuntimeError:
                pass
        else:
            foreign.append(connection)
    for connection in foreign:
        await asyncio.to_thread(_close_connection_sync, connection)
