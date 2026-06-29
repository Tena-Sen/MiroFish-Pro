import os
from dotenv import load_dotenv
load_dotenv(r"E:\MiroFish\.env", override=True)

zep_key = os.environ.get("ZEP_API_KEY")
print(f"Key: {zep_key[:30]}...")

from zep_cloud.client import Zep

client = Zep(api_key=zep_key)
print("Client created")

try:
    result = client.graph.create(graph_id="test_sdk_456")
    print(f"SUCCESS: {result}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {str(e)[:300]}")
