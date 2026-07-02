"""Launch TestForge with full lifespan, logging to file."""
import sys, os
sys.path.insert(0, r"C:\Users\LENOVO\Desktop\TestForge -  07011951 - hermes")
os.environ["TESTFORGE_DEBUG"] = "true"
os.environ["TESTFORGE_LOG_LEVEL"] = "DEBUG"

import logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(r"C:\Users\LENOVO\Desktop\TestForge -  07011951 - hermes\server_startup.log"),
        logging.StreamHandler(sys.stderr),
    ],
)

from backend.main import app
import uvicorn
uvicorn.run(app, host="127.0.0.1", port=9876, log_level="debug")
