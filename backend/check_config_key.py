import os
import sys

# Add the backend directory to path
sys.path.insert(0, r"E:\MiroFish\backend")

# Import config
from app.config import Config

print(f"Config.ZEP_API_KEY: {Config.ZEP_API_KEY}")
print(f"Length: {len(Config.ZEP_API_KEY)}")
print(f"Starts with: {Config.ZEP_API_KEY[:30]}")

# Compare with .env file
with open(r"E:\MiroFish\.env", "r", encoding="utf-8") as f:
    for line in f:
        if line.startswith("ZEP_API_KEY"):
            env_key = line.strip().split("=", 1)[1]
            print(f"\n.env key: {env_key[:30]}")
            print(f"Match: {Config.ZEP_API_KEY == env_key}")
