import argparse
import os

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run sh4r3d")
    parser.add_argument("--beta", action="store_true", help="Enable beta token gate")
    args = parser.parse_args()
    if args.beta:
        os.environ["BETA_MODE"] = "true"

import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
