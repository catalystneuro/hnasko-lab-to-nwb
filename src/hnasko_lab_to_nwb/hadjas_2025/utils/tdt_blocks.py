"""Read TDT blocks once per session.

The raw fiber photometry interface, the optogenetic stimulus interface and session_to_nwb all need parts of the
same TDT blocks. These functions read each part once and keep it until clear_tdt_block_cache is called at the
end of a session.
"""

import io
from contextlib import redirect_stdout
from functools import lru_cache
from pathlib import Path


def _read_block(folder_path: Path, **kwargs):
    import tdt

    with redirect_stdout(io.StringIO()):
        return tdt.read_block(str(folder_path), **kwargs)


@lru_cache(maxsize=4)
def read_tdt_stream(folder_path: Path, store: str):
    """Read one stream store of a TDT block (e.g. "Fi1r"), with its data, sampling rate and start time."""
    return _read_block(folder_path, evtype=["streams"], store=store).streams[store]


@lru_cache(maxsize=8)
def read_tdt_epocs(folder_path: Path) -> dict:
    """Read the epocs of a TDT block as {name: {"onset", "offset", "data"}} arrays, in seconds from block start."""
    epocs = _read_block(folder_path, evtype=["epocs"]).epocs
    return {name: dict(onset=epoc.onset, offset=epoc.offset, data=epoc.data) for name, epoc in epocs.items()}


@lru_cache(maxsize=8)
def read_tdt_start_timestamp(folder_path: Path) -> float:
    """Read the POSIX timestamp of the start of a TDT block."""
    return _read_block(folder_path, evtype=["scalars"]).info.start_date.timestamp()


def clear_tdt_block_cache() -> None:
    """Free the blocks read for a session."""
    read_tdt_stream.cache_clear()
    read_tdt_epocs.cache_clear()
    read_tdt_start_timestamp.cache_clear()
