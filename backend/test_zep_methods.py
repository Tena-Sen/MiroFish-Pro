import os
import httpx
from dotenv import load_dotenv
load_dotenv(r"E:\MiroFish\.env", override=True)

zep_key = os.environ.get("ZEP_API_KEY")

client = httpx.Client(timeout=15)
url = "https://api.getzep.com/api/v2/graph/entities?limit=1"

# Test different auth methods
methods = [
    {"Authorization": f"Bearer {zep_key}"},
    {"X-API-Key": zep_key},
    {"api-key": zep_key},
    {"Authorization": f"Token {zep_key}"},
]

for i, headers in enumerate(methods):
    print(f"\nMethod {i+1}: {list(headers.keys())[0]}")
    try:
        resp = client.get(url, headers=headers)
        print(f"  Status: {resp.status_code}, Body: {resp.text[:100]}")
    except Exception as e:
        print(f"  Error: {e}")

# Also try query parameter
print(f"\nMethod 5: Query parameter")
try:
    resp = client.get(f"{url}&api_key={zep_key}")
    print(f"  Status: {resp.status_code}, Body: {resp.text[:100]}")
except Exception as e:
    print(f"  Error: {e}")
