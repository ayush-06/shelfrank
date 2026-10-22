# Prints OpenRouter credit status (limit, usage, credits). Never prints the key.
import os, json, urllib.request
from dotenv import load_dotenv
load_dotenv(".env")
k = os.environ["OPENROUTER_API_KEY"]
for url in ["https://openrouter.ai/api/v1/key", "https://openrouter.ai/api/v1/credits"]:
    try:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {k}"})
        d = json.load(urllib.request.urlopen(req, timeout=20)).get("data", {})
        safe = {x: d.get(x) for x in ["limit", "usage", "limit_remaining", "is_free_tier", "total_credits", "total_usage"] if x in d}
        print(url.rsplit("/",1)[1], safe)
    except Exception as e:
        print(url.rsplit("/",1)[1], "error", type(e).__name__, getattr(e, "code", ""))
