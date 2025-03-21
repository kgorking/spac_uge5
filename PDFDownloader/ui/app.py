# app.py (Refactored)

import tkinter as tk
from tkinter import ttk
import logging
from queue import Queue


class DownloadApp(tk.Tk):
    """
    Tkinter GUI featuring:
      - Success/fail counters
      - A row for each worker (thread) with progress bars & status text
      - Black background and white text
    """

    def __init__(self, update_queue, max_workers=3, max_success=10, dev_mode=True):
        super().__init__()
        self.logger = logging.getLogger("DownloadApp")

        # Store incoming arguments
        self.update_queue = update_queue
        self.max_workers = max_workers
        self.max_success = max_success
        self.dev_mode = dev_mode
        self._stopped = False

        # Basic window settings
        self.title("PDF Downloader - UI")
        self.geometry("700x400")
        self.configure(bg="black")

        # Counters for successes and failures
        self.current_success = 0
        self.current_fail = 0

        # Top frame holding success/fail labels
        top_frame = tk.Frame(self, bg="black")
        top_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        if dev_mode:
            self.success_label = tk.Label(
                top_frame,
                text=f"Successes: 0/{self.max_success}",
                fg="white",
                bg="black",
                font=("Arial", 14)
            )
        else:
            self.success_label = tk.Label(
                top_frame,
                text="Successes: 0",
                fg="white",
                bg="black",
                font=("Arial", 14)
            )
        self.success_label.pack(side=tk.LEFT, padx=10)

        self.fail_label = tk.Label(
            top_frame,
            text="Failures: 0",
            fg="white",
            bg="black",
            font=("Arial", 14)
        )
        self.fail_label.pack(side=tk.LEFT, padx=10)

        # Frame for worker rows
        self.threads_frame = tk.Frame(self, bg="black")
        self.threads_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Dictionary to store UI elements for each worker
        # Example: { 1: {"label": <tk.Label>, "progress_var": <IntVar>}, ... }
        self.worker_rows = {}

        # Create rows for each potential worker
        for w_id in range(1, self.max_workers + 1):
            self._create_worker_row(w_id)

        # Start checking the queue periodically
        self.after(200, self.process_queue)

    def _create_worker_row(self, worker_id):
        """
        Create a row in the UI for a given worker ID, with a label and progress bar.
        """
        frame = tk.Frame(self.threads_frame, bg="black")
        frame.pack(fill=tk.X, pady=2)

        label = tk.Label(
            frame,
            text=f"Thread #{worker_id}: Idle",
            fg="white",
            bg="black",
            font=("Arial", 10)
        )
        label.pack(side=tk.LEFT, padx=5)

        prog_var = tk.IntVar(value=0)
        prog_bar = ttk.Progressbar(
            frame,
            orient="horizontal",
            length=200,
            mode="determinate",
            maximum=100,
            variable=prog_var
        )
        prog_bar.pack(side=tk.LEFT, padx=10)

        self.worker_rows[worker_id] = {
            "label": label,
            "progress_var": prog_var
        }

    def _update_thread(self, worker_id, status_text, progress):
        """
        Update the status label and progress bar for a given worker.
        """
        if worker_id in self.worker_rows:
            row = self.worker_rows[worker_id]
            row["label"].config(text=f"Thread #{worker_id}: {status_text}")
            row["progress_var"].set(progress)

    def _update_counters(self, success, fail):
        """
        Update the success/fail labels with the latest counts.
        """
        if self.dev_mode:
            self.success_label.config(text=f"Successes: {success}/{self.max_success}")
        else:
            self.success_label.config(text=f"Successes: {success}")

        self.fail_label.config(text=f"Failures: {fail}")

    def process_queue(self):
        """
        Periodically checks the update_queue for new messages and updates the UI.
        Message formats can be:
            ("thread_update", worker_id, status_text, progress_val)
            ("counters", success_count, fail_count)
            ("quit_ui", )
        """
        if self._stopped:
            self.logger.debug("UI is stopped; no further queue processing.")
            return

        try:
            while True:
                msg = self.update_queue.get_nowait()
                mtype = msg[0]

                if mtype == "thread_update":
                    # Example: ("thread_update", worker_id, status, progress)
                    _, worker_id, status_text, progress_val = msg
                    self.logger.debug(f"Thread {worker_id} update: {status_text}, {progress_val}%")
                    self._update_thread(worker_id, status_text, progress_val)

                elif mtype == "counters":
                    # Example: ("counters", success_count, fail_count)
                    _, success, fail = msg
                    self.logger.debug(f"Counter update: success={success}, fail={fail}")
                    self._update_counters(success, fail)

                elif mtype == "quit_ui":
                    # Example: ("quit_ui", )
                    self.logger.info("Quit request received; closing the UI.")
                    self._on_close()

                else:
                    self.logger.warning(f"Unknown message type: {mtype}")

        except Exception as e:
            import queue
            if not isinstance(e, queue.Empty):
                self.logger.exception(f"Error processing queue: {e}")

        if not self._stopped:
            self.after(200, self.process_queue)

    def _on_close(self):
        """
        Invoked when the user requests to close the window.
        Sets a stopped flag and destroys the window.
        """
        self.logger.info("UI close requested by user.")
        self._stopped = True
        self.destroy()
