from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv(r"E:\MiroFish\.env")
client = OpenAI(
    base_url=os.getenv("LLM_BASE_URL"),
    api_key=os.getenv("LLM_API_KEY")
)
try:
    r = client.chat.completions.create(
        model="mimo-v2.5-pro",
        messages=[{"role": "user", "content": "say hi"}],
        max_tokens=5
    )
    print("SUCCESS:", r.choices[0].message.content)
except Exception as e:
    print("ERROR:", type(e).__name__, str(e))
