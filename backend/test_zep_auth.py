import os
import httpx
from dotenv import load_dotenv
load_dotenv(r"E:\MiroFish\.env", override=True)

zep_key = os.environ.get("ZEP_API_KEY")

# Try direct API call with verbose logging
client = httpx.Client(timeout=15)

# Test different endpoints
endpoints = [
    "https://api.getzep.com/api/v2/graph/entities?limit=1",
    "https://api.getzep.com/api/v2/graph",
    "https://api.getzep.com/api/v1/graph",
]

for url in endpoints:
    print(f"\nTesting: {url}")
    try:
        resp = client.get(url, headers={
            "Authorization": f"Bearer {zep_key}",
            "Accept": "application/json"
        })
        print(f"  Status: {resp.status_code}")
        print(f"  Headers: {dict(resp.headers)}")
        print(f"  Body: {resp.text[:200]}")
    except Exception as e:
        print(f"  Error: {e}")
