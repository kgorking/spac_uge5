# main.py (Refactored)
import threading
from queue import Queue

import logging
from ui.app import DownloadApp
from pdf_downloader.downloader import run_downloader
from utils.logging_setup import setup_logger


def run_downloader_in_thread(dev_mode_toggle, update_queue):
    """
    Helper function to start the downloader in a separate thread.
    """
    def downloader_thread():
        # Run the actual downloader logic
        run_downloader(
            #xlsx_paths=["data/GRI_2017_2020 (1).xlsx", "data/Metadata2006_2016.xlsx"],
            xlsx_paths=["data/Metadata2006_2016.xlsx"],
            output_folder="data/PDFs",
            status_file="data/DownloadedStatus.xlsx",
            dev_mode=dev_mode_toggle,
            max_concurrent_workers=3,
            update_queue=update_queue,
            max_success=10
        )

    thread = threading.Thread(target=downloader_thread, daemon=True)
    thread.start()
    return thread


def main():
    """
    Main entry point for the PDF Download program with UI.
    """
    dev_mode_toggle = True  # Toggle for development mode

    # 1. Setup logging
    logger = setup_logger(log_dir="logs")
    logger.info("=== Starting the PDF Download program (with UI) ===")

    # 2. Create a queue for UI updates
    update_queue = Queue()

    # 3. Create the Tkinter app for downloads
    app = DownloadApp(
        update_queue=update_queue,
        max_workers=3,
        max_success=10,
        dev_mode=dev_mode_toggle
    )

    # 4. Start the downloader in a separate thread
    downloader_t = run_downloader_in_thread(dev_mode_toggle, update_queue)

    # 5. Run the UI main loop (blocks until window closes)
    app.mainloop()

    logger.info("=== UI closed. Waiting for downloader thread to finish ===")
    downloader_t.join()  # Ensure downloader finishes
    logger.info("=== PDF Download program completed ===")


if __name__ == "__main__":
    main()
