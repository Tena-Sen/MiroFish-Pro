import os
from dotenv import load_dotenv
load_dotenv(r"E:\MiroFish\.env", override=True)

zep_key = os.environ.get("ZEP_API_KEY")

from zep_cloud.client import Zep

# Check default base URL
client = Zep(api_key=zep_key)

# Try to find the base URL
if hasattr(client, '_client'):
    inner = client._client
    print(f"Inner client type: {type(inner)}")
    if hasattr(inner, '_base_url'):
        print(f"Base URL: {inner._base_url}")
    elif hasattr(inner, 'base_url'):
        print(f"Base URL: {inner.base_url}")
    elif hasattr(inner, '_base_url_raw'):
        print(f"Base URL raw: {inner._base_url_raw}")

# Try calling the API
try:
    result = client.graph.list_graphs()
    print(f"Success! Result: {result}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {str(e)[:200]}")
