# downloader.py (Refactored)

import logging
import os
from plistlib import InvalidFileException
import pandas as pd
import requests
import shutil
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.xlsx_chunk_reader import read_xlsx_in_chunks

# ---------------------
# Constants
# ---------------------
PRIMARY_LINK_COL = "Pdf_URL"
SECONDARY_LINK_COL = "Report Html Address"
BRNUM_COL = "BRnum"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

# ---------------------
# Public Entry Function
# ---------------------
def run_downloader(
    xlsx_paths,
    output_folder,
    status_file,
    dev_mode=True,
    max_concurrent_workers=1,
    update_queue=None,
    max_success=10,
    chunk_size=1000
):
    """
    Main function to:
      1) Read chunks from multiple .xlsx files.
      2) Combine & shuffle data.
      3) Skip previously attempted entries.
      4) Concurrently download PDFs.
      5) Update a status file with results.
    """

    logger = logging.getLogger("PDFDownloaderLogger")
    logger.info(f"Downloading PDFs from xlsx paths: {xlsx_paths}")
    os.makedirs(output_folder, exist_ok=True)

    df_status = load_or_create_status_file(status_file)
    success_count = 0
    fail_count = 0

    # Prepare chunk readers for each .xlsx
    chunk_readers = [read_xlsx_in_chunks(path, chunk_size=chunk_size) for path in xlsx_paths]

    # Continuously read chunks, combine, and process until no more data or dev_mode max met
    while True:
        if dev_mode and success_count >= max_success:
            logger.info("Reached dev_mode success limit. Exiting.")
            break

        # Combine the next chunk from each file
        combined_df = pd.DataFrame()
        for gen in chunk_readers:
            try:
                chunk_df = next(gen)
                combined_df = pd.concat([combined_df, chunk_df], ignore_index=True)
            except StopIteration:
                pass

        if combined_df.empty:
            logger.info("No more chunk data. Stopping downloads.")
            break

        combined_df = combined_df.sample(frac=1.0).reset_index(drop=True)

        # Ensure needed columns exist; skip if missing
        if BRNUM_COL not in combined_df.columns:
            logger.warning(f"Missing column '{BRNUM_COL}' in chunk. Skipping chunk.")
            continue

        # Clean the link columns
        for link_col in [PRIMARY_LINK_COL, SECONDARY_LINK_COL]:
            if link_col in combined_df.columns:
                combined_df[link_col] = combined_df[link_col].astype(str).str.strip()

        # Filter out any BRnum previously attempted
        combined_df = exclude_already_attempted(combined_df, df_status)
        if combined_df.empty:
            logger.debug("All rows in this chunk were already attempted. Moving on.")
            continue

        # Concurrency for downloading each row
        with ThreadPoolExecutor(max_workers=max_concurrent_workers, thread_name_prefix="DLWorker") as executor:
            futures_map = {}
            for _, row in combined_df.iterrows():
                brnum = row.get(BRNUM_COL)
                if not brnum:
                    continue
                primary_url = row.get(PRIMARY_LINK_COL)
                secondary_url = row.get(SECONDARY_LINK_COL)
                future = executor.submit(
                    download_single_pdf,
                    brnum,
                    primary_url,
                    secondary_url,
                    output_folder,
                    update_queue,
                    max_concurrent_workers
                )
                futures_map[future] = brnum

            # Process results as they complete
            for future in as_completed(futures_map):
                this_brnum = futures_map[future]
                try:
                    status, info = future.result()
                except Exception as e:
                    logger.exception(f"Unhandled error for BRnum={this_brnum}: {e}")
                    fail_count += 1
                    df_status = update_status(df_status, this_brnum, "Failure", str(e))
                    _push_counters(update_queue, success_count, fail_count)
                    save_status_file(df_status, status_file)
                    continue

                if status == "Success":
                    success_count += 1
                else:
                    fail_count += 1

                df_status = update_status(df_status, this_brnum, status, info)
                _push_counters(update_queue, success_count, fail_count)
                save_status_file(df_status, status_file)

                # Cancel remaining tasks if dev_mode success limit reached
                if dev_mode and success_count >= max_success:
                    logger.info("Reached dev_mode max success in mid-chunk. Cancelling remaining tasks.")
                    for f_remaining in futures_map:
                        if not f_remaining.done():
                            f_remaining.cancel()
                    break

        save_status_file(df_status, status_file)

        if dev_mode and success_count >= max_success:
            break

    logger.info("All downloads complete. Final status file saved.")
    save_status_file(df_status, status_file)


# ---------------------
# Download Single PDF
# ---------------------
def download_single_pdf(
    brnum, primary_url, secondary_url, output_folder,
    update_queue=None,
    max_workers=3
):
    """
    Tries a primary PDF link; if that fails, tries secondary.
    Returns (status, info).
    """

    logger = logging.getLogger("PDFDownloaderLogger")
    tname = threading.current_thread().name
    worker_id = parse_thread_name_to_id(tname, max_workers=max_workers)

    # 1) Attempt primary URL
    primary_status, primary_info = None, None
    if primary_url:
        if not primary_url.lower().startswith(("http://", "https://")):
            primary_url = 'http://' + primary_url

        _push_thread_update(update_queue, worker_id, f"Attempting {brnum} (primary)", 0)
        pstat, pinfo = attempt_download(
            file_path=Path(output_folder) / f"{brnum}.pdf",
            url=primary_url,
            brnum=brnum,
            update_queue=update_queue
        )
        if pstat == "Success":
            _push_thread_update(update_queue, worker_id, f"{brnum} => SUCCESS", 100)
            _push_thread_update(update_queue, worker_id, "Idle", 0)
            return ("Success", "Primary link OK")
        else:
            primary_status, primary_info = pstat, pinfo
            logger.warning(f"Primary link failed for {brnum}, reason={pinfo}")
            _push_thread_update(update_queue, worker_id, f"Primary fail {brnum}", 100)
    else:
        logger.warning(f"No valid primary URL for {brnum}")
        _push_thread_update(update_queue, worker_id, f"{brnum}: No valid primary", 0)
        primary_status, primary_info = "Failure", "No valid or malformed primary link"

    # 2) Attempt secondary URL
    secondary_status, secondary_info = None, None
    if secondary_url:
        if not secondary_url.lower().startswith(("http://", "https://")):
            secondary_url = 'http://' + secondary_url
        _push_thread_update(update_queue, worker_id, f"Attempting {brnum} (secondary)", 0)
        sstat, sinfo = attempt_download(
            file_path=Path(output_folder) / f"{brnum}.pdf",
            url=secondary_url,
            brnum=brnum,
            update_queue=update_queue
        )
        if sstat == "Success":
            _push_thread_update(update_queue, worker_id, f"{brnum} => SUCCESS (secondary)", 100)
            _push_thread_update(update_queue, worker_id, "Idle", 0)
            return ("Success", f"Secondary link OK; primary failed: {primary_info}")
        else:
            secondary_status, secondary_info = sstat, sinfo
            logger.warning(f"Secondary link failed for {brnum}, reason={sinfo}")
            _push_thread_update(update_queue, worker_id, f"{brnum} => FAIL", 100)
            _push_thread_update(update_queue, worker_id, "Idle", 0)
    else:
        _push_thread_update(update_queue, worker_id, f"{brnum} => FAIL (no valid secondary)", 100)
        _push_thread_update(update_queue, worker_id, "Idle", 0)

    # 3) Combine final results if both failed
    final_status, final_info = combine_failure_info(
        brnum=brnum,
        primary_status=primary_status,
        primary_info=primary_info,
        secondary_status=secondary_status,
        secondary_info=secondary_info
    )
    return (final_status, final_info)


# ---------------------
# Attempt Single Download
# ---------------------
def attempt_download(file_path, url, brnum, update_queue=None, thread_id="???"):
    """
    Download the PDF from `url` to `file_path` with checks:
      - Malformed URL
      - Sufficient disk space
      - HEAD request (warn if fail)
      - GET request (streamed)
      - Check PDF signature
      - Validate file with PyPDF2
    Returns ("Success", "") or ("Failure", reason).
    """

    logger = logging.getLogger("PDFDownloaderLogger")
    tname = threading.current_thread().name
    worker_id = parse_thread_name_to_id(tname, max_workers=3)

    # Basic sanity check on URL
    if not isinstance(url, str):
        return ("Failure", f"URL has invalid type: {type(url).__name__}.")

    import re
    url = re.sub(r"[\u200B-\u200F\uFEFF]", "", url.strip())  # remove zero-width chars

    # Check disk space
    try:
        disk_usage = shutil.disk_usage(file_path.parent)
        free_space_mb = disk_usage.free / (1024 * 1024)
        if free_space_mb < 5:
            logger.warning(f"[BR{brnum}] Low disk space ({free_space_mb:.2f} MB).")
            return ("Failure", "Insufficient disk space.")
    except Exception as e:
        logger.warning(f"[BR{brnum}] Could not check disk space: {e}")
        return ("Failure", f"Disk space check error: {e}")

    # HEAD request (non-fatal if fails)
    head_ok = False
    head_resp = None
    try:
        head_resp = requests.head(url, timeout=30, allow_redirects=True, verify=False, headers=HEADERS)
        head_resp.raise_for_status()
        head_ok = True
    except requests.exceptions.RequestException as e:
        logger.warning(f"[BR{brnum}] HEAD request warning (non-fatal): {e}")

    if head_ok and head_resp is not None:
        content_type = head_resp.headers.get("Content-Type", "").lower()
        if "text/html" in content_type:
            logger.warning(f"[BR{brnum}] HEAD suggests HTML. Will still attempt GET.")
        if "Content-Length" in head_resp.headers:
            try:
                total_size = int(head_resp.headers["Content-Length"])
                if total_size < 1000:
                    logger.warning(f"[BR{brnum}] HEAD indicates a very small file.")
            except ValueError:
                pass
    else:
        logger.warning(f"[BR{brnum}] HEAD check skipped. Proceeding with GET.")

    # GET request (streamed)
    try:
        resp = requests.get(url, timeout=60, stream=True, verify=False, headers=HEADERS)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        return ("Failure", f"GET request error: {e}")

    # Write to file, checking PDF signature in the first chunk
    downloaded = 0
    chunk_size = 1024
    wrote_first_chunk = False

    try:
        with open(file_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if not chunk:
                    continue
                if not wrote_first_chunk:
                    wrote_first_chunk = True
                    if b"%PDF-" not in chunk[:20]:
                        logger.warning(f"[BR{brnum}] First chunk missing %PDF- signature.")
                        raise InvalidFileException("No %PDF- signature in the initial data.")
                f.write(chunk)
                downloaded += len(chunk)

                # Update UI progress if we got Content-Length from HEAD
                if head_ok and head_resp and "Content-Length" in head_resp.headers:
                    try:
                        total_size = int(head_resp.headers["Content-Length"])
                        if total_size > 0:
                            percent = int(downloaded * 100 / total_size)
                            _push_thread_update(update_queue, worker_id, f"Downloading {brnum}", percent)
                    except ValueError:
                        logger.warning(f"[BR{brnum}] Invalid Content-Length in HEAD response.")

    except OSError as e:
        return ("Failure", f"File write error: {e}")
    except InvalidFileException as e:
        file_path.unlink(missing_ok=True)
        return ("Failure", str(e))


    # Check file size
    if file_path.stat().st_size == 0:
        file_path.unlink(missing_ok=True)
        return ("Failure", "Downloaded file is zero bytes.")

    # Validate PDF structure with PyPDF2
    try:
        import PyPDF2
        with open(file_path, "rb") as pdf_file:
            reader = PyPDF2.PdfReader(pdf_file)
            _ = len(reader.pages)  # triggers PDF parsing
    except Exception as e:
        file_path.unlink(missing_ok=True)
        logger.warning(f"[BR{brnum}] PyPDF2 parse error: {e}")
        return ("Failure", f"PyPDF2 parse error: {e}")

    logger.info(f"[BR{brnum}] Successfully downloaded -> {file_path.name}")
    return ("Success", "")


# ---------------------
# Failure Info Combining
# ---------------------
def combine_failure_info(
    brnum,
    primary_status,
    primary_info,
    secondary_status=None,
    secondary_info=None
):
    """
    If both primary & secondary fail, merges both error messages.
    Returns (final_status, final_info).
    """

    logger = logging.getLogger("PDFDownloaderLogger")
    logger.debug(
        f"combine_failure_info(BR={brnum}): "
        f"primary=({primary_status}, {primary_info}), "
        f"secondary=({secondary_status}, {secondary_info})"
    )

    # 1) Primary success
    if primary_status == "Success":
        return ("Success", "Primary link OK")

    # 2) Primary fail, secondary success
    if primary_status == "Failure" and secondary_status == "Success":
        return ("Success", f"Secondary link OK (Primary failed: {primary_info})")

    # 3) Primary fail, no secondary attempt
    if secondary_status is None:
        return ("Failure", primary_info)

    # 4) Both fail
    if primary_status == "Failure" and secondary_status == "Failure":
        combined = f"Both links failed. Primary=({primary_info}); Secondary=({secondary_info})"
        return ("Failure", combined)

    return ("Failure", "No valid link found.")


# ---------------------
# Status Management
# ---------------------
def load_or_create_status_file(status_file):
    """
    Reads or creates a status file (BRnum, Status, Info).
    Returns a pandas DataFrame.
    """

    logger = logging.getLogger("PDFDownloaderLogger")
    if not os.path.isfile(status_file):
        logger.info(f"Status file not found. Creating: {status_file}")
        return pd.DataFrame(columns=["BRnum", "Status", "Info"])

    try:
        df = pd.read_excel(status_file)
        required_cols = {"BRnum", "Status", "Info"}
        if not required_cols.issubset(df.columns):
            logger.warning(f"Status file missing columns. Recreating.")
            return pd.DataFrame(columns=["BRnum", "Status", "Info"])
        return df
    except Exception as e:
        logger.fatal(f"Failed to read status file {status_file}: {e}")
        return pd.DataFrame(columns=["BRnum", "Status", "Info"])


def exclude_already_attempted(full_df, df_status):
    """
    Removes rows where BRnum is already 'Success' or 'Failure' in df_status.
    Returns filtered DataFrame.
    """

    logger = logging.getLogger("PDFDownloaderLogger")
    attempted = df_status[df_status["Status"].isin(["Success", "Failure"])]["BRnum"].unique()
    filtered_df = full_df[~full_df[BRNUM_COL].isin(attempted)]
    removed_count = len(full_df) - len(filtered_df)
    logger.info(f"Skipping {removed_count} rows already attempted.")
    return filtered_df


def update_status(df_status, brnum, new_status, info):
    """
    Updates or appends a row for BRnum with (Status, Info).
    Returns updated df_status.
    """

    logger = logging.getLogger("PDFDownloaderLogger")
    mask = (df_status["BRnum"] == brnum)
    if mask.any():
        logger.debug(f"Updating existing row: BRnum={brnum}, {new_status}, {info}")
        df_status.loc[mask, "Status"] = new_status
        df_status.loc[mask, "Info"] = info
    else:
        logger.debug(f"Appending new row: BRnum={brnum}, {new_status}, {info}")
        new_row = pd.DataFrame([{"BRnum": brnum, "Status": new_status, "Info": info}])
        df_status = pd.concat([df_status, new_row], ignore_index=True)
    return df_status


def save_status_file(df_status, status_file):
    """
    Saves the DataFrame to an Excel status file.
    """

    logger = logging.getLogger("PDFDownloaderLogger")
    try:
        df_status.to_excel(status_file, index=False)
        logger.debug(f"Saved status file with {len(df_status)} rows to: {status_file}")
    except Exception as e:
        logger.fatal(f"Failed to save status file {status_file}: {e}")


# ---------------------
# UI Update Helpers
# ---------------------
def _push_thread_update(update_queue, worker_id, status_text, progress_val):
    """
    Pushes a worker's status update to the UI queue if available.
    """
    if update_queue:
        update_queue.put(("thread_update", worker_id, status_text, progress_val))


def _push_counters(update_queue, success_count, fail_count):
    """
    Pushes updated counters to the UI queue if available.
    """
    if update_queue:
        update_queue.put(("counters", success_count, fail_count))


def parse_thread_name_to_id(thread_name, max_workers=3):
    """
    Extracts an integer worker ID from a name like 'DLWorker_0', clamped to max_workers.
    Returns 1 if parsing fails.
    """

    if not thread_name.startswith("DLWorker_"):
        return 1
    try:
        suffix = int(thread_name.split("_")[-1])
    except ValueError:
        return 1

    worker_id = suffix + 1
    if worker_id > max_workers:
        worker_id = max_workers
    return worker_id
