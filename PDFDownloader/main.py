# main.py

import logging
import threading
from queue import Queue

from ui.app import DownloadApp
from pdf_downloader.downloader import run_downloader
from utils.logging_setup import setup_logger


def main():
    # 1. Setup logging
    logger = setup_logger(log_dir="logs")
    logger.info("=== Starting the PDF Download program (with UI) ===")

    # 2. Create a queue for UI updates
    update_queue = Queue()

    # 3. Create the Tkinter app
    #    'update_queue' is the first argument, the rest are keyword arguments
    app = DownloadApp(update_queue, max_workers=3, max_success=10)

    # 4. Start your downloader in a separate thread
    def downloader_thread():
        run_downloader(
            xlsx_paths=["data/GRI_2017_2020 (1).xlsx", "data/Metadata2006_2016.xlsx"],
            output_folder="data/PDFs",
            status_file="data/DownloadedStatus.xlsx",
            dev_mode=True,
            soft_limit=3,
            update_queue=update_queue,
            max_success=10
        )

    t = threading.Thread(target=downloader_thread, daemon=True)
    t.start()

    # 5. Run the UI main loop (blocks until window closes)
    app.mainloop()

    logger.info("=== UI closed. Waiting for downloader thread to finish ===")
    t.join()  # ensure everything is done

    logger.info("=== PDF Download program completed ===")


if __name__ == "__main__":
    main()
