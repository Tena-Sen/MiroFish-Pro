import os
from dotenv import load_dotenv
load_dotenv(r"E:\MiroFish\.env", override=True)

zep_key = os.environ.get("ZEP_API_KEY")
print(f"Backend key: {zep_key}")
print(f"Length: {len(zep_key)}")

# Test with this key
from zep_cloud.client import Zep
client = Zep(api_key=zep_key)

try:
    result = client.graph.create(graph_id="test_verify_123")
    print(f"SUCCESS: {result}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {str(e)[:200]}")
