import asyncio
import os
import sys
from app.core import main_entry

if __name__ == "__main__":
    # Base path is current dir
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    # Legacy path assuming we are inside 'gatekeeper_ng' and legacy 'monitor' is in parent
    # Parent of base_path
    parent_dir = os.path.dirname(base_path)
    legacy_path = parent_dir 
    
    print(f"Starting Gatekeeper NG from {base_path}")
    print(f"Looking for legacy config in {legacy_path}")
    
    try:
        asyncio.run(main_entry(base_path, legacy_path))
    except KeyboardInterrupt:
        pass
