#!/usr/bin/env python3
"""
Script to run the E-ink Composer Web UI with FastAPI.
"""

import os
import sys
from pathlib import Path

# Add SDK to path if needed
sdk_path = Path(__file__).parent.parent.parent.parent.parent
if str(sdk_path) not in sys.path:
    sys.path.insert(0, str(sdk_path))

if __name__ == "__main__":
    # Create required directories
    os.makedirs("templates", exist_ok=True)
    os.makedirs("static", exist_ok=True)

    print("Starting E-ink Composer Web UI (FastAPI)...")
    print("Access at: http://localhost:5000")
    print("\nPress Ctrl+C to stop the server")

    # Run the FastAPI app with uvicorn
    import uvicorn

    uvicorn.run(
        "distiller_cm5_sdk.hardware.eink.composer.web_app:app",
        host="0.0.0.0",
        port=5000,
        reload=False,
        log_level="info",
    )
