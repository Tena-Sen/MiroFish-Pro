import os
import httpx
from dotenv import load_dotenv
load_dotenv(r"E:\MiroFish\.env", override=True)

zep_key = os.environ.get("ZEP_API_KEY")

# Test with raw HTTP
client = httpx.Client(timeout=15)

# Test 1: Direct API call
print("Test 1: Direct API call")
resp = client.get(
    "https://api.getzep.com/api/v2/graph/entities?limit=1",
    headers={"Authorization": f"Bearer {zep_key}"}
)
print(f"Status: {resp.status_code}")
print(f"Headers: {dict(resp.headers)}")
print(f"Body: {resp.text[:200]}")

# Test 2: Create graph
print("\nTest 2: Create graph")
resp = client.post(
    "https://api.getzep.com/api/v2/graph",
    headers={
        "Authorization": f"Bearer {zep_key}",
        "Content-Type": "application/json"
    },
    json={"graph_id": "test_raw_123", "name": "Test Graph"}
)
print(f"Status: {resp.status_code}")
print(f"Body: {resp.text[:200]}")
