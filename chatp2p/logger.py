import logging
import sys

def setup_logging():
    if logging.getLogger().hasHandlers():
        logging.getLogger().handlers.clear()
    
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d %(levelname)s [%(threadName)s] %(name)s: %(message)s", 
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    