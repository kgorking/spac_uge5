# utils/xlsx_chunk_reader.py

import pandas as pd
import logging

def read_xlsx_in_chunks(
    path, 
    sheet_name=0, 
    chunk_size=1000, 
    header=0,
    usecols=None
):
    """
    Generator function that yields DataFrame chunks of size `chunk_size`
    from the given Excel file `path`.

    :param path: Path to the .xlsx file
    :param sheet_name: sheet name or index (default=0)
    :param chunk_size: number of rows to read per chunk
    :param header: row number to use as the column names
    :param usecols: columns to read (optional)
    :yields: DataFrame with up to `chunk_size` rows

    Example usage:
        for df_chunk in read_xlsx_in_chunks("large.xlsx", chunk_size=500):
            process(df_chunk)
    """
    logger = logging.getLogger("XLSXChunkReader")

    start_row = 0
    chunk_num = 0

    # We must handle the header row carefully if header=0. 
    # We'll read the header from the first chunk, then use `header=None` 
    # for subsequent chunks, manually reusing columns from the first chunk.

    # First: read one chunk with a proper header
    first_chunk = pd.read_excel(
        path,
        sheet_name=sheet_name,
        skiprows=range(1, start_row + 1),  # e.g. row 1 is the header
        nrows=chunk_size,
        header=header,
        usecols=usecols,
        engine="openpyxl"
    )
    if first_chunk.empty:
        logger.warning(f"No rows found in first chunk of '{path}'.")
        return

    # Keep the columns from the first chunk
    columns = list(first_chunk.columns)
    chunk_num += 1
    yield first_chunk

    start_row += chunk_size

    while True:
        # For subsequent chunks, skip the header row so we set header=None
        # and skip the same # of rows
        df_chunk = pd.read_excel(
            path,
            sheet_name=sheet_name,
            skiprows=range(1, start_row + 1),  
            nrows=chunk_size,
            header=None,
            usecols=usecols,
            engine="openpyxl"
        )
        if df_chunk.empty:
            logger.debug(f"Reached end of file '{path}', no more rows.")
            break

        # Manually assign columns from first chunk
        df_chunk.columns = columns

        start_row += chunk_size
        chunk_num += 1
        logger.debug(f"Yielding chunk #{chunk_num} from '{path}'.")
        yield df_chunk
