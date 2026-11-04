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
    """Read one stream store of a TDT block (e.g. "Fi1r"), with its data, sampling rate and start time.

    Parameters
    ----------
    folder_path : Path
        Path to the TDT block folder.
    store : str
        Name of the stream store.

    Returns
    -------
    tdt.StructType
        The stream, with "data" as (channels, samples) or (samples,), "fs" in Hz and "start_time" in seconds.
    """
    return _read_block(folder_path, evtype=["streams"], store=store).streams[store]


@lru_cache(maxsize=8)
def read_tdt_epocs(folder_path: Path) -> dict:
    """Read the epocs of a TDT block, with times in seconds from the block start.

    Parameters
    ----------
    folder_path : Path
        Path to the TDT block folder.

    Returns
    -------
    dict
        {epoc name: {"onset": array, "offset": array, "data": array}}. An onset without an offset (the recording
        stopped first) has an offset of inf.
    """
    epocs = _read_block(folder_path, evtype=["epocs"]).epocs
    return {name: dict(onset=epoc.onset, offset=epoc.offset, data=epoc.data) for name, epoc in epocs.items()}


@lru_cache(maxsize=8)
def read_tdt_start_timestamp(folder_path: Path) -> float:
    """Read the POSIX timestamp of the start of a TDT block.

    Parameters
    ----------
    folder_path : Path
        Path to the TDT block folder.

    Returns
    -------
    float
        The block start, in seconds since the epoch. It does not depend on the time zone of the computer reading
        the block, unlike the start_date of tdt.read_block.
    """
    return _read_block(folder_path, evtype=["scalars"]).info.start_date.timestamp()


def clear_tdt_block_cache() -> None:
    """Free the blocks read for a session."""
    read_tdt_stream.cache_clear()
    read_tdt_epocs.cache_clear()
    read_tdt_start_timestamp.cache_clear()
