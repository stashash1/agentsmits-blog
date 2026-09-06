#!/usr/bin/env python3
"""Cross-platform file-locking shim.

Mimics the subset of fcntl.flock() used by the agentsmits-blog pipeline:
    flock(fd, LOCK_EX | LOCK_NB)  # try-exclusive non-blocking
    flock(fd, LOCK_UN)            # release

On Linux/macOS: delegates to fcntl.flock (POSIX flock(2) semantics).
On Windows:    emulates with msvcrt.locking on the underlying file
               descriptor (1-byte lock region). Blocking lock is not
               implemented because the pipeline only ever uses try-lock.

`fd` may be either an int (file descriptor from os.open or open().fileno())
or a file-like object with a .fileno() method (matching fcntl.flock's
leniency).
"""
from __future__ import annotations
import sys

# Lock operation constants (matching fcntl values on POSIX).
LOCK_SH = 1
LOCK_EX = 2
LOCK_NB = 4
LOCK_UN = 8


def _resolve_fd(fd) -> int:
    """Return an int file descriptor, accepting int or file-like."""
    if isinstance(fd, int):
        return fd
    # File-like: duck-typed .fileno()
    fn = getattr(fd, "fileno", None)
    if fn is None:
        raise TypeError(f"expected int or file-like object, got {type(fd).__name__}")
    return fn()


if sys.platform == "win32":
    import msvcrt
    import errno as _errno

    _OP_MAP_BLOCKING = {
        LOCK_EX: msvcrt.LK_LOCK,    # blocking exclusive
    }
    _OP_MAP_NB = {
        LOCK_EX: msvcrt.LK_NBLCK,   # non-blocking exclusive
    }
    _OP_UNLOCK = msvcrt.LK_UNLCK    # unlock

    def flock(fd, op):
        """Best-effort flock() emulation on Windows.

        Supported ops:
            LOCK_EX | LOCK_NB: try exclusive lock, raise BlockingIOError on contention
            LOCK_UN:           release lock
        Other combinations raise NotImplementedError.
        """
        fileno = _resolve_fd(fd)
        nb = bool(op & LOCK_NB)
        base = op & ~LOCK_NB
        if nb and base in _OP_MAP_NB:
            try:
                msvcrt.locking(fileno, _OP_MAP_NB[base], 1)
            except OSError as exc:
                # Normalize to BlockingIOError so callers see the same exception
                # they would on POSIX (matching fcntl.flock behaviour).
                raise BlockingIOError(_errno.EAGAIN,
                                      "Resource temporarily unavailable") from exc
            return None
        if base == LOCK_UN:
            try:
                msvcrt.locking(fileno, _OP_UNLOCK, 1)
            except OSError:
                # Idempotent unlock: ignore if not held (msvcrt raises EINVAL
                # if the byte range was not locked).
                pass
            return None
        if base in _OP_MAP_BLOCKING:
            try:
                msvcrt.locking(fileno, _OP_MAP_BLOCKING[base], 1)
            except OSError:
                if base != LOCK_UN:
                    raise
            return None
        raise NotImplementedError(f"flock mode {op!r} not supported on Windows")

else:
    import fcntl as _fcntl

    def flock(fd, op):
        return _fcntl.flock(fd, op)

    # Re-export the canonical POSIX constants.
    LOCK_SH = _fcntl.LOCK_SH
    LOCK_EX = _fcntl.LOCK_EX
    LOCK_NB = _fcntl.LOCK_NB
    LOCK_UN = _fcntl.LOCK_UN
