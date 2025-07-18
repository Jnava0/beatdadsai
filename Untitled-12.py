# File: backend/logging_config.py
# Author: Gemini
# Date: July 17, 2024
# Description: Centralized logging configuration for the MINI S backend.
# This setup ensures all parts of the application log to both the console
# and a rotating file, providing a persistent record of system events.

import logging
from logging.handlers import RotatingFileHandler
import sys

# --- Configuration Constants ---
LOG_FILE = "minis_backend.log"
MAX_LOG_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3  # Number of old log files to keep

def setup_logging():
    """
    Configures the root logger for the entire application.
    
    This function sets up two handlers:
    1. A StreamHandler to output logs to the console (stdout).
    2. A RotatingFileHandler to write logs to a file, with automatic
       rotation based on size to prevent log files from growing indefinitely.
    """
    # Get the root logger. All loggers created in other modules will inherit this config.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO) # Set the minimum level of logs to capture.

    # Prevent adding duplicate handlers if this function is called more than once.
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # --- Create a Formatter ---
    # The formatter defines the structure of our log messages.
    # It includes timestamp, log level, module name, and the message itself.
    log_format = logging.Formatter(
        '%(asctime)s - %(levelname)-8s - %(name)-15s - %(message)s'
    )

    # --- Console Handler ---
    # This handler prints logs to the standard output, which is useful for
    # real-time monitoring during development.
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)

    # --- Rotating File Handler ---
    # This handler writes logs to a file. It automatically creates a new file
    # when the current one reaches MAX_LOG_SIZE_BYTES, keeping a backup history.
    try:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=MAX_LOG_SIZE_BYTES,
            backupCount=BACKUP_COUNT
        )
        file_handler.setFormatter(log_format)
        root_logger.addHandler(file_handler)
    except Exception as e:
        # If file logging fails (e.g., due to permissions), log an error to the console.
        logging.error(f"Failed to set up file logger: {e}")

    logging.info("Logging configured successfully. Outputting to console and %s.", LOG_FILE)

# --- Example Usage (for direct testing of this module) ---
if __name__ == '__main__':
    print("--- Testing Logging Configuration ---")
    setup_logging()
    
    # Get a logger specific to this module for context.
    test_logger = logging.getLogger(__name__)
    
    test_logger.debug("This is a debug message. It should NOT appear unless log level is set to DEBUG.")
    test_logger.info("This is an info message.")
    test_logger.warning("This is a warning message.")
    test_logger.error("This is an error message.")
    test_logger.critical("This is a critical message.")
    
    print(f"\nLog messages have been written to the console and to '{LOG_FILE}'.")
    print("Check the contents of the file to verify.")