# pdf_downloader/downloader.py

import sys
import logging
import os
import pandas as pd
import requests
import shutil
import openpyxl
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.xlsx_chunk_reader import read_xlsx_in_chunks

###########################
# Potential second link columns
# If your .xlsx has a second link in "Report Html Address" or a different column,
# adjust accordingly. For demonstration we assume "Report Html Address" is the fallback.
###########################
PRIMARY_LINK_COL = "Pdf_URL"
SECONDARY_LINK_COL = "Report Html Address"
BRNUM_COL = "BRnum"

# Global worker ID mapping
_worker_id_map = {}
_map_lock = threading.Lock()

def get_worker_id():
    """
    Returns a stable ID (1..3) for the calling OS thread.
    Once assigned, that OS thread always has the same ID
    for the entire lifetime of the program.
    If more than 3 unique threads show up, they all get ID=3.
    """
    global _worker_id_map
    tid = threading.get_ident()
    with _map_lock:
        if tid in _worker_id_map:
            return _worker_id_map[tid]

        # Not seen this OS thread before; do we have capacity left?
        if len(_worker_id_map) < 3:
            new_id = len(_worker_id_map) + 1  # 1..3
            _worker_id_map[tid] = new_id
            return new_id
        else:
            # We already assigned 3 unique threads; use ID=3
            _worker_id_map[tid] = 3
            return 3

###########################
# 1. Entry Function
###########################
def run_downloader(
    xlsx_paths,
    output_folder,
    status_file,
    dev_mode=True,
    soft_limit=3,
    update_queue=None,
    max_success=10,
    chunk_size=1000
):
    """
    1) For each "chunk index", read chunk i from BOTH Excel files
    2) Combine them into one DataFrame, shuffle the rows
    3) Filter out already attempted
    4) Use concurrency to download them
    5) Move to next chunk index
    """
    logger = logging.getLogger("PDFDownloaderLogger")
    logger.info(f"Downloading PDFs from xlsx paths: {xlsx_paths}")
    os.makedirs(output_folder, exist_ok=True)

    df_status = load_or_create_status_file(status_file)
    success_count = 0
    fail_count = 0

    # We'll keep reading chunk i from each file until no more data
    # We'll assume both files might have different lengths
    # We'll break if both are done or dev_mode hits max successes

    # Step 1: Initialize chunk "readers" for each file
    from utils.xlsx_chunk_reader import read_xlsx_in_chunks
    chunk_readers = [
        read_xlsx_in_chunks(path, chunk_size=chunk_size)
        for path in xlsx_paths
    ]

    chunk_index = 0

    while True:
        if dev_mode and success_count >= max_success:
            logger.info("Already reached max successes, done.")
            break

        # Step 2: read chunk i from each file, combine
        combined_df = pd.DataFrame()
        for i, gen in enumerate(chunk_readers):
            try:
                df_chunk = next(gen)  # get next chunk from file i
                # optional: rename columns if needed
                combined_df = pd.concat([combined_df, df_chunk], ignore_index=True)
            except StopIteration:
                # means no more data in this file
                pass

        if combined_df.empty:
            logger.info("No more data from any file. Breaking loop.")
            break

        # Step 3: Shuffle combined data
        combined_df = combined_df.sample(frac=1.0).reset_index(drop=True)

        # Step 4: Filter out columns, fix links, skip attempted
        # e.g.:
        if BRNUM_COL not in combined_df.columns:
            logger.warning(f"Missing column {BRNUM_COL} in combined chunk. Skipping.")
            continue

        for link_col in [PRIMARY_LINK_COL, SECONDARY_LINK_COL]:
            if link_col in combined_df.columns:
                combined_df[link_col] = combined_df[link_col].astype(str).str.strip()

        # skip attempted
        combined_df = exclude_already_attempted(combined_df, df_status)
        if combined_df.empty:
            logger.debug("All rows already attempted, next chunk.")
            chunk_index += 1
            continue

        # Step 5: concurrency
        with ThreadPoolExecutor(
            max_workers=soft_limit, 
            thread_name_prefix="DLWorker"
        ) as executor:
            futures_map = {}
            for idx, row in combined_df.iterrows():
                brnum = row.get(BRNUM_COL)
                if not brnum:
                    continue
                primary_url = row.get(PRIMARY_LINK_COL, None)
                secondary_url = row.get(SECONDARY_LINK_COL, None)

                # We no longer call get_worker_id(). Let the pool's thread names do the job.
                future = executor.submit(
                    download_single_pdf,
                    brnum,
                    primary_url,
                    secondary_url,
                    output_folder,
                    update_queue
                )
                # We can store the brnum in futures_map if needed
                futures_map[future] = brnum

            for future in as_completed(futures_map):
                this_brnum = futures_map[future]
                try:
                    status, info = future.result()
                except Exception as e:
                    logger.exception(f"Unhandled error for BRnum={this_brnum}: {e}")
                    fail_count += 1
                    df_status = update_status(df_status, this_brnum, "Failure", str(e))
                    _push_counters(update_queue, success_count, fail_count)
                    continue

                if status == "Success":
                    success_count += 1
                else:
                    fail_count += 1
                df_status = update_status(df_status, this_brnum, status, info)
                _push_counters(update_queue, success_count, fail_count)

                if dev_mode and success_count >= max_success:
                    logger.info("Reached dev_mode max. Canceling remaining tasks.")
                    for f2 in futures_map:
                        if not f2.done():
                            f2.cancel()
                    break

        save_status_file(df_status, status_file)
        chunk_index += 1

        if dev_mode and success_count >= max_success:
            break

    logger.info("All done! Final status file updated.")
    save_status_file(df_status, status_file)
    logger.info("Exiting script.")


###########################
# 2. Download Single PDF
###########################
def download_single_pdf(
    brnum, primary_url, secondary_url, output_folder,
    update_queue=None
):
    """
    Tries primary link, if fail tries secondary, with multiple UI updates:
      - Attempting...
      - Downloading... (progress)
      - Success or failure reason
      - Idle
    Returns (status, info).
    """
    logger = logging.getLogger("PDFDownloaderLogger")

    # Figure out our thread ID from the thread name
    tname = threading.current_thread().name  # e.g. "DLWorker_0"
    worker_id = parse_thread_name_to_id(tname, max_workers=3)

    # 1) Attempt primary link if any
    if primary_url and primary_url.strip().lower().startswith(("http://", "https://")):
        # Update UI: "Attempting brnum (primary)"
        _push_thread_update(update_queue, worker_id,
                            f"Attempting {brnum} (primary)", 0)

        dl_status, dl_info = attempt_download(
            file_path=Path(output_folder) / f"{brnum}.pdf",
            url=primary_url,
            brnum=brnum,
            update_queue=update_queue
        )

        if dl_status == "Success":
            # If success, show 100% + "Success"
            _push_thread_update(update_queue, worker_id,
                                f"{brnum} => SUCCESS", 100)
            # Then set worker row back to Idle
            _push_thread_update(update_queue, worker_id,
                                "Idle", 0)
            return ("Success", "Primary link OK")
        else:
            # Show some short "failed primary link" status:
            logger.warning(f"Primary link failed for {brnum}, reason={dl_info}")
            _push_thread_update(update_queue, worker_id,
                                f"Primary fail {brnum}", 100)
            # short pause to let user see the "fail" status if desired
            # time.sleep(0.5)
    else:
        logger.warning(f"No valid primary URL for {brnum}")
        _push_thread_update(update_queue, worker_id,
                            f"{brnum}: No valid primary", 0)

    # 2) Attempt secondary link if present
    if secondary_url and secondary_url.strip().lower().startswith(("http://", "https://")):
        _push_thread_update(update_queue, worker_id,
                            f"Attempting {brnum} (secondary)", 0)

        dl_status, dl_info = attempt_download(
            file_path=Path(output_folder) / f"{brnum}.pdf",
            url=secondary_url,
            brnum=brnum,
            update_queue=update_queue
        )

        if dl_status == "Success":
            _push_thread_update(update_queue, worker_id,
                                f"{brnum} => SUCCESS (secondary)", 100)
            _push_thread_update(update_queue, worker_id,
                                "Idle", 0)
            return ("Success", f"Secondary link OK; primary failed: {dl_info}")
        else:
            logger.warning(f"Secondary link also failed for {brnum}, reason={dl_info}")
            _push_thread_update(update_queue, worker_id,
                                f"{brnum} => FAIL", 100)
            _push_thread_update(update_queue, worker_id,
                                "Idle", 0)
            return ("Failure", f"Both links failed. {dl_info}")
    else:
        _push_thread_update(update_queue, worker_id,
                            f"{brnum} => FAIL (no valid secondary)", 100)
        _push_thread_update(update_queue, worker_id, "Idle", 0)
        return ("Failure", "No valid link found.")



###########################
# 3. Attempt Download (All Checks)
###########################
def attempt_download(file_path, url, brnum, update_queue=None, thread_id="???"):
    """
    Attempts to download the PDF from `url` into `file_path` with robust checks:
      1) Valid URL format and protocol.
      2) Sufficient disk space.
      3) HEAD request for preliminary checks (DNS resolution, HTTP status, content length, type).
      4) GET request (streamed) for actual file content.
      5) Check first chunk for PDF signature before continuing.
      6) Send real-time progress updates while writing the file.
      7) Validate file integrity (size + PyPDF2 structure check).
    
    Returns:
      ("Success", "") if successful.
      ("Failure", "Reason for failure") otherwise.
    """

    logger = logging.getLogger("PDFDownloaderLogger")
    # figure out the OS thread's name
    tname = threading.current_thread().name  # e.g. "DLWorker_0"
    # parse to a stable ID 1..3
    worker_id = parse_thread_name_to_id(tname, max_workers=3)
    
    logger.info(f"[Thread {tname} => row {worker_id}] Attempting download of {brnum} from {url}")

    # 1) Basic URL validation
    if not isinstance(url, str):
        return ("Failure", f"URL has invalid type: {type(url).__name__}.")
    
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        return ("Failure", "Malformed or missing URL protocol (http/https).")

    # 2) Check disk space
    try:
        disk_usage = shutil.disk_usage(file_path.parent)
        free_space_mb = disk_usage.free / (1024 * 1024)
        if free_space_mb < 5:
            logger.warning(f"Low disk space ({free_space_mb:.2f} MB) for {file_path.parent}.")
            return ("Failure", "Insufficient disk space.")
    except Exception as e:
        logger.warning(f"Disk space check failed: {e}")
        return ("Failure", f"Could not determine disk space: {str(e)}")

    # 3) HEAD request: Check if the URL is valid and points to a file
    try:
        head_resp = requests.head(url, timeout=10, allow_redirects=True)
        head_resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        return ("Failure", f"HEAD request error: {e}")

    content_type = head_resp.headers.get("Content-Type", "").lower()
    if "text/html" in content_type:
        logger.warning(f"{brnum}: HEAD request suggests the link is an HTML page, not a PDF.")
        return ("Failure", "HEAD indicates HTML, not a PDF.")

    # 4) Get Content-Length (if available) to track download progress
    total_size = None
    if "Content-Length" in head_resp.headers:
        try:
            total_size = int(head_resp.headers["Content-Length"])
            if total_size < 1000:  # Less than ~1 KB? Suspicious.
                return ("Failure", f"File too small to be a valid PDF ({total_size} bytes).")
        except ValueError:
            total_size = None

    # 5) GET request to download file with streaming
    try:
        resp = requests.get(url, timeout=30, stream=True)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        return ("Failure", f"GET request error: {e}")

    # 6) Write to file while checking first chunk for PDF signature
    downloaded = 0
    chunk_size = 1024
    wrote_first_chunk = False

    try:
        with open(file_path, "wb") as f:
            for chunk_i, chunk in enumerate(resp.iter_content(chunk_size=chunk_size)):
                if not chunk:
                    continue
                # First chunk: Validate that this is a real PDF
                if not wrote_first_chunk:
                    wrote_first_chunk = True
                    if b"%PDF-" not in chunk[:20]:
                        logger.warning(f"{brnum}: No '%PDF-' found in first chunk. Deleting file.")
                        file_path.unlink(missing_ok=True)
                        return ("Failure", "No %PDF- signature (not a real PDF).")

                f.write(chunk)
                downloaded += len(chunk)

                # UI Progress update
                if update_queue and total_size:
                    percent = int(downloaded * 100 / total_size)
                    _push_thread_update(update_queue, worker_id,
                                        f"Downloading {brnum}", percent)

    except OSError as e:
        return ("Failure", f"File write error: {str(e)}")

    # 7) Validate downloaded file size
    if file_path.stat().st_size == 0:
        return ("Failure", "Downloaded file is zero bytes in size.")

    # 8) Verify the file structure using PyPDF2
    try:
        import PyPDF2
        with open(file_path, "rb") as pdf_file:
            reader = PyPDF2.PdfReader(pdf_file)
            _ = len(reader.pages)  # This triggers PDF parsing
    except Exception as e:
        file_path.unlink(missing_ok=True)
        logger.warning(f"{brnum}: PyPDF2 parse error: {e}")
        return ("Failure", f"PyPDF2 parse error: {e}")

    logger.info(f"Successfully downloaded {brnum} -> {file_path.name}")
    return ("Success", "")



###########################
# 4. Read XLSX with Safety Checks
###########################
def read_xlsx_safely(path):
    logger = logging.getLogger("PDFDownloaderLogger")
    if not os.path.isfile(path):
        logger.fatal(f"File not found: {path}")
        return pd.DataFrame()

    try:
        df = pd.read_excel(path)
    except Exception as e:
        logger.fatal(f"Failed to read xlsx: {path}. Error: {e}")
        return pd.DataFrame()

    # Must contain at least BRnum
    required = [BRNUM_COL]
    for col in required:
        if col not in df.columns:
            logger.warning(f"Missing required column '{col}' in {path}. Skipping.")
            return pd.DataFrame()

    # Convert link columns to strings (avoid "URL is not a string.")
    for link_col in [PRIMARY_LINK_COL, SECONDARY_LINK_COL]:
        if link_col in df.columns:
            df[link_col] = df[link_col].astype(str).str.strip()

    return df


###########################
# 5. Load/Create Status File
###########################
def load_or_create_status_file(status_file):
    """
    Reads or creates a status file with columns = [BRnum, Status, Info].
    Returns a pandas DataFrame.
    """
    logger = logging.getLogger("PDFDownloaderLogger")
    if not os.path.isfile(status_file):
        logger.info(f"Status file not found. Creating a new one: {status_file}")
        df = pd.DataFrame(columns=["BRnum", "Status", "Info"])
        return df
    else:
        try:
            df = pd.read_excel(status_file)
            # Ensure correct columns
            if not set(["BRnum", "Status", "Info"]).issubset(df.columns):
                logger.warn(f"Status file {status_file} missing required columns. Recreating.")
                df = pd.DataFrame(columns=["BRnum", "Status", "Info"])
            return df
        except Exception as e:
            logger.fatal(f"Failed to read status file {status_file}: {e}")
            return pd.DataFrame(columns=["BRnum", "Status", "Info"])

###########################
# 6. Exclude Already-Attempted
###########################
def exclude_already_attempted(full_df, df_status):
    """
    Removes any rows from full_df where BRnum is already 'Success' in df_status.
    """
    logger = logging.getLogger("PDFDownloaderLogger")
    attempted_ids = df_status[df_status["Status"].isin(["Success", "Failure"])]["BRnum"].unique()
    filtered = full_df[~full_df[BRNUM_COL].isin(attempted_ids)]
    count_removed = len(full_df) - len(filtered)
    logger.info(f"Skipping {count_removed} rows already attempted (Success/Failure).")
    return filtered

###########################
# 7. Update and Save Status
###########################
def update_status(df_status, brnum, new_status, info):
    """
    Updates the row for 'brnum' in df_status with new_status, info.
    Returns updated df_status.
    """
    
    logger = logging.getLogger("PDFDownloaderLogger")
    mask = (df_status["BRnum"] == brnum)
    if mask.any():
        logger.debug(f"Updating existing row for BRnum={brnum} => {new_status}, {info}")
        df_status.loc[mask, "Status"] = new_status
        df_status.loc[mask, "Info"] = info
    else:
        logger.debug(f"Appending new row for BRnum={brnum} => {new_status}, {info}")
        new_row = pd.DataFrame([{"BRnum": brnum, "Status": new_status, "Info": info}])
        df_status = pd.concat([df_status, new_row], ignore_index=True)

    return df_status

def save_status_file(df_status, status_file):
    """Saves the updated df_status to Excel."""
    logger = logging.getLogger("PDFDownloaderLogger")
    try:
        df_status.to_excel(status_file, index=False)
        logger.debug(f"Saved status file with {len(df_status)} rows: {status_file}")
    except Exception as e:
        logger.fatal(f"Failed to save status file {status_file}: {e}")

############################
# HELPER UI QUEUE FUNCTIONS
############################
def _push_thread_update(update_queue, worker_id, status_text, progress_val):
    """Pushes worker update to UI."""
    if update_queue:
        update_queue.put(("thread_update", worker_id, status_text, progress_val))

def _push_counters(update_queue, success_count, fail_count):
    """Pushes counter updates to UI."""
    if update_queue:
        update_queue.put(("counters", success_count, fail_count))

def parse_thread_name_to_id(thread_name, max_workers=3):
    """
    e.g.  'DLWorker_0' -> 1
          'DLWorker_1' -> 2
          'DLWorker_2' -> 3
    If the suffix > max_workers - 1, clamp to max_workers => same row #.
    """
    if not thread_name.startswith("DLWorker_"):
        # fallback: maybe it's a different environment
        return 1
    
    # extract the suffix after "DLWorker_"
    suffix_str = thread_name.split("_")[-1]
    try:
        suffix = int(suffix_str)
    except ValueError:
        return 1

    # suffix=0 => ID=1, suffix=1 => ID=2, ...
    worker_id = suffix + 1
    if worker_id > max_workers:
        worker_id = max_workers  # clamp
    return worker_id