import logging
import sys
from pathlib import Path

class EmojiFormatter(logging.Formatter):
    """Custom formatter to add emojis and better visuals to the background logs."""
    
    LEVEL_EMOJIS = {
        logging.DEBUG: "🔍",
        logging.INFO: "✨",
        logging.WARNING: "⚠️",
        logging.ERROR: "🚨",
        logging.CRITICAL: "🔥",
    }

    def format(self, record):
        emoji = self.LEVEL_EMOJIS.get(record.levelno, "•")
        record.emoji = emoji
        # Add a visual separator for multi-line messages
        if "\n" in record.msg:
            record.msg = record.msg.replace("\n", "\n" + " " * 28 + "│ ")
        return super().format(record)

def setup_logger():
    """
    Configures logging to write to 'portfolio.log' in the project root.
    Enhanced with emojis and clearer formatting for monitoring via 'tail -f'.
    """
    log_file = Path("portfolio.log")
    
    # Create logger
    logger = logging.getLogger("portfolio_ask")
    logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers if any (to avoid duplicates on rebuilds)
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # Formatter
    # [HH:M:S] 🔍 DEBUG    | name | message
    fmt = "%(emoji)s [%(asctime)s] %(levelname)-8s │ %(name)-15s │ %(message)s"
    formatter = EmojiFormatter(fmt, datefmt="%H:%M:%S")
    
    # File Handler
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Also capture LangChain internal logs
    lc_logger = logging.getLogger("langchain")
    lc_logger.setLevel(logging.INFO)
    
    if lc_logger.hasHandlers():
        lc_logger.handlers.clear()
    lc_logger.addHandler(file_handler)
    
    # Print a startup line in the log
    logger.info("=" * 60)
    logger.info("NEW SESSION STARTED")
    logger.info("=" * 60)
    
    return logger

# Global instance
logger = logging.getLogger("portfolio_ask")
