import os
import httpx
from dotenv import load_dotenv

load_dotenv(r"E:\MiroFish\.env", override=True)

zep_key = os.environ.get("ZEP_API_KEY")
zep_proxy = os.environ.get("ZEP_PROXY")

print(f"ZEP_PROXY: {zep_proxy}")
print(f"Key: {zep_key[:25]}...")

if zep_proxy:
    print(f"Testing with proxy {zep_proxy}...")
    client = httpx.Client(proxy=zep_proxy)
    resp = client.get(
        "https://api.getzep.com/api/v2/graph/entities?limit=1",
        headers={"Authorization": f"Bearer {zep_key}"},
        timeout=15
    )
    print(f"Status: {resp.status_code}")
    print(f"Body: {resp.text[:300]}")
else:
    print("No proxy set!")
