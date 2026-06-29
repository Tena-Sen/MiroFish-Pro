import os
from dotenv import load_dotenv
load_dotenv(r"E:\MiroFish\.env", override=True)

zep_key = os.environ.get("ZEP_API_KEY")

from zep_cloud.client import Zep

client = Zep(api_key=zep_key)
print("Client created OK")

try:
    # Try creating a graph with graph_id
    result = client.graph.create(graph_id="test_graph_123")
    print(f"Success: {result}")
except Exception as e:
    print(f"Error type: {type(e).__name__}")
    print(f"Error: {str(e)[:500]}")
