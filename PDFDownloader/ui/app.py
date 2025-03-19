# ui/app.py

import tkinter as tk
from tkinter import ttk
import logging
from queue import Queue


class DownloadApp(tk.Tk):
    """
    Tkinter GUI with:
      - success/fail counters
      - a row for each worker thread ID
      - progress bars + status text
    Black background, white text.
    """

    def __init__(self, update_queue, max_workers=3, max_success=10):
        super().__init__()
        self.logger = logging.getLogger("DownloadApp")

        # Keep references to incoming arguments
        self.update_queue = update_queue
        self.max_workers = max_workers
        self.max_success = max_success
        self._stopped = False

        self.title("PDF Downloader - UI")
        self.geometry("700x400")
        self.configure(bg="black")

        # A place for the success/fail counters
        self.current_success = 0
        self.current_fail = 0

        top_frame = tk.Frame(self, bg="black")
        top_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        self.success_label = tk.Label(
            top_frame, text=f"Successes: 0/{self.max_success}",
            fg="white", bg="black", font=("Arial", 14)
        )
        self.success_label.pack(side=tk.LEFT, padx=10)

        self.fail_label = tk.Label(
            top_frame, text="Failures: 0",
            fg="white", bg="black", font=("Arial", 14)
        )
        self.fail_label.pack(side=tk.LEFT, padx=10)

        # The frame that holds worker rows
        self.threads_frame = tk.Frame(self, bg="black")
        self.threads_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # We store { worker_id: {label, progress_var} }
        self.worker_rows = {}
        # Pre-create rows for each concurrency worker
        for w_id in range(1, self.max_workers + 1):
            self._create_worker_row(w_id)

        # Start polling the queue
        self.after(200, self.process_queue)

    def process_queue(self):
        """
        Poll for new messages from the queue and update the UI.
        Types of messages:
          ("new_thread", thread_id)
          ("thread_update", thread_id, status_text, progress_val)
          ("counters", success_count, fail_count)
          ("quit_ui", )
        """

        # If user already closed, don't process queue
        if self._stopped:
            self.logger.debug("UI is stopped; skipping process_queue.")
            return

        try:
            while True:
                msg = self.update_queue.get_nowait()
                mtype = msg[0]

                if mtype == "thread_update":
                    _, worker_id, status_text, progress_val = msg
                    self.logger.debug(f"Thread {worker_id} update: {status_text}, {progress_val}%")
                    self._update_thread(worker_id, status_text, progress_val)

                elif mtype == "counters":
                    _, success, fail = msg
                    self.logger.debug(f"Update counters: success={success}, fail={fail}")
                    self._update_counters(success, fail)

                elif mtype == "quit_ui":
                    self.logger.info("Received quit_ui message; closing window.")
                    self._on_close()

                else:
                    self.logger.warning(f"Unknown message type: {mtype}")

        except Exception as e:
            # queue.Empty or unexpected error
            import queue
            if not isinstance(e, queue.Empty):
                self.logger.exception(f"Error processing queue: {e}")

        # Schedule the next poll if we're still running
        if not self._stopped:
            self.after(200, self.process_queue)

    def _on_close(self):
        """
        Called when the user attempts to close the window.
        We set a stopped flag, then destroy the Tk window.
        """
        self.logger.info("User requested UI close.")
        self._stopped = True
        self.destroy()  # closes the Tk window

    def _create_worker_row(self, worker_id):
        """Creates fixed UI rows (Thread #1, #2, #3)."""
        frame = tk.Frame(self.threads_frame, bg="black")
        frame.pack(fill=tk.X, pady=2)

        label = tk.Label(frame, text=f"Thread #{worker_id}: Idle",
                         fg="white", bg="black", font=("Arial", 10))
        label.pack(side=tk.LEFT, padx=5)

        prog_var = tk.IntVar(value=0)
        prog_bar = ttk.Progressbar(
            frame, orient="horizontal", length=200,
            mode="determinate", maximum=100, variable=prog_var
        )
        prog_bar.pack(side=tk.LEFT, padx=10)

        self.worker_rows[worker_id] = {
            "label": label,
            "progress_var": prog_var
        }

    def _update_thread(self, worker_id, status_text, progress):
        """Updates worker row status and progress."""
        if worker_id in self.worker_rows:
            row = self.worker_rows[worker_id]
            row["label"].config(text=f"Thread #{worker_id}: {status_text}")
            row["progress_var"].set(progress)

    def _update_counters(self, success, fail):
        """Updates the success/fail counters."""
        self.success_label.config(text=f"Successes: {success}/{self.max_success}")
        self.fail_label.config(text=f"Failures: {fail}")
