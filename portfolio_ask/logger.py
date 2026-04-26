import logging
import sys
from pathlib import Path

def setup_logger():
    """
    Configures logging to write to 'portfolio.log' in the project root.
    This allows monitoring the agent's background reasoning and tool calls
    from another terminal using 'tail -f portfolio.log'.
    """
    log_file = Path("portfolio.log")
    
    # Create logger
    logger = logging.getLogger("portfolio_ask")
    logger.setLevel(logging.DEBUG)
    
    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S"
    )
    
    # File Handler
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Also capture LangChain internal logs
    lc_logger = logging.getLogger("langchain")
    lc_logger.setLevel(logging.INFO)
    lc_logger.addHandler(file_handler)
    
    return logger

# Global instance
logger = logging.getLogger("portfolio_ask")
