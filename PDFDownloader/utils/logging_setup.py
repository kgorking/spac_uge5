import logging
import os

# ---------------------------
# 1. Define Custom Log Levels
# ---------------------------
TRACE_LEVEL_NUM = 5  # below DEBUG (10)
logging.addLevelName(TRACE_LEVEL_NUM, "TRACE")

# For FATAL, let’s pick 60 (above CRITICAL which is 50)
FATAL_LEVEL_NUM = 60
logging.addLevelName(FATAL_LEVEL_NUM, "FATAL")

# ---------------------------
# 2. Create Custom Logger Methods
# ---------------------------
def trace(self, message, *args, **kwargs):
    """Log a message with severity 'TRACE'."""
    if self.isEnabledFor(TRACE_LEVEL_NUM):
        self._log(TRACE_LEVEL_NUM, message, args, **kwargs)

def fatal(self, message, *args, **kwargs):
    """Log a message with severity 'FATAL'."""
    if self.isEnabledFor(FATAL_LEVEL_NUM):
        self._log(FATAL_LEVEL_NUM, message, args, **kwargs)

logging.Logger.trace = trace
logging.Logger.fatal = fatal

# ---------------------------------------------------------
# 3. SingleLevelFilter to ensure each file logs only one level
# ---------------------------------------------------------
class SingleLevelFilter(logging.Filter):
    def __init__(self, level):
        super().__init__()
        self.level = level

    def filter(self, record):
        return (record.levelno == self.level)

# ---------------------------
# 4. Logger Setup Function
# ---------------------------
def setup_logger(log_dir="logs"):
    """
    Creates and configures a logger that writes:
      - trace.log   (only TRACE messages)
      - debug.log   (only DEBUG messages)
      - info.log    (only INFO messages)
      - warn.log    (only WARNING messages)
      - fatal.log   (only FATAL messages)
      - all.log     (all messages, all levels)

    :param log_dir: Directory where log files will be stored.
    :return: Configured logger instance.
    """

    # Create a named logger (avoid using root logger directly)
    logger = logging.getLogger("PDFDownloaderLogger")
    logger.setLevel(logging.DEBUG)  # Catch all logs from TRACE(5) to FATAL(60)

    # Ensure log directory exists
    os.makedirs(log_dir, exist_ok=True)

    # Common log format
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # -------------------
    # 4a. TRACE Handler
    # -------------------
    trace_handler = logging.FileHandler(os.path.join(log_dir, "trace.log"))
    trace_handler.setLevel(TRACE_LEVEL_NUM)
    trace_handler.addFilter(SingleLevelFilter(TRACE_LEVEL_NUM))
    trace_handler.setFormatter(formatter)
    logger.addHandler(trace_handler)

    # -------------------
    # 4b. DEBUG Handler
    # -------------------
    debug_handler = logging.FileHandler(os.path.join(log_dir, "debug.log"))
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.addFilter(SingleLevelFilter(logging.DEBUG))
    debug_handler.setFormatter(formatter)
    logger.addHandler(debug_handler)

    # -------------------
    # 4c. INFO Handler
    # -------------------
    info_handler = logging.FileHandler(os.path.join(log_dir, "info.log"))
    info_handler.setLevel(logging.INFO)
    info_handler.addFilter(SingleLevelFilter(logging.INFO))
    info_handler.setFormatter(formatter)
    logger.addHandler(info_handler)

    # -------------------
    # 4d. WARN Handler
    # -------------------
    warn_handler = logging.FileHandler(os.path.join(log_dir, "warn.log"))
    warn_handler.setLevel(logging.WARNING)
    warn_handler.addFilter(SingleLevelFilter(logging.WARNING))
    warn_handler.setFormatter(formatter)
    logger.addHandler(warn_handler)

    # -------------------
    # 4e. FATAL Handler
    # -------------------
    fatal_handler = logging.FileHandler(os.path.join(log_dir, "fatal.log"))
    fatal_handler.setLevel(FATAL_LEVEL_NUM)
    fatal_handler.addFilter(SingleLevelFilter(FATAL_LEVEL_NUM))
    fatal_handler.setFormatter(formatter)
    logger.addHandler(fatal_handler)

    # -------------------
    # 4f. Combined Handler (All Levels)
    # -------------------
    all_handler = logging.FileHandler(os.path.join(log_dir, "all.log"))
    all_handler.setLevel(logging.DEBUG)  # log everything
    all_handler.setFormatter(formatter)
    logger.addHandler(all_handler)

    return logger

# ---------------------------
# 5. Example Usage (Optional)
# ---------------------------
# if __name__ == "__main__":
#     # Quick test if run directly
#     log = setup_logger()
#     log.trace("This is a TRACE message.")
#     log.debug("This is a DEBUG message.")
#     log.info("This is an INFO message.")
#     log.warning("This is a WARN message.")
#     log.fatal("This is a FATAL message.")
