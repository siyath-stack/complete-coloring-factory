import os
import json
import re
import requests
from datetime import datetime

ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")
TEXT_MODEL = "@cf/meta/llama-3.1-8b-instruct"
API_URL = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/{TEXT_MODEL}"

HISTORY_FILE = "used_topics.json"

FALLBACK_VIRAL_TOPICS = [
    "cute baby capybara",
    "friendly baby axolotl",
    "chubby red panda explorer",
    "kawaii baby highland cow",
    "playful sea otter pup",
    "curious baby hedgehog",
    "little woodland fox cub",
    "happy baby alpaca",
    "cheerful baby penguin",
    "adventurous baby koala"
]

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def query_trending_topics():
    if not ACCOUNT_ID or not API_TOKEN:
        print("Missing Cloudflare credentials. Using fallback list.")
        return FALLBACK_VIRAL_TOPICS

    prompt = (
        "You are an expert children's coloring book editor specializing in Amazon KDP, Etsy, and TikTok trends. "
        "Generate a list of 8 trending, highly engaging cute animal or fantasy character subjects for kids coloring books "
        "(e.g., 'cute baby axolotl', 'playful baby red panda', 'kawaii baby capybara', 'chubby baby otter'). "
        "Return ONLY a clean JSON array of strings, for example: [\"cute baby capybara\", \"playful axolotl\"]. "
        "Do not include any explanation or markdown formatting."
    )

    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    try:
        response = requests.post(API_URL, headers=headers, json={"prompt": prompt}, timeout=25)
        response.raise_for_status()
        res_json = response.json()
        raw_text = res_json.get("result", {}).get("response", "")

        match = re.search(r'\\[.*\\]', raw_text, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            cleaned = [str(x).strip().lower() for x in parsed if isinstance(x, str)]
            if cleaned:
                return cleaned
    except Exception as e:
        print(f"Warning: Cloudflare text API fallback triggered: {e}")

    return FALLBACK_VIRAL_TOPICS

def select_and_save_daily_topic():
    history = load_history()
    candidates = query_trending_topics()

    selected = None
    for item in candidates:
        norm = item.strip().lower()
        if norm and norm not in history:
            selected = norm
            break

    if not selected:
        for fb in FALLBACK_VIRAL_TOPICS:
            if fb not in history:
                selected = fb
                break

    if not selected:
        selected = f"happy animal adventure day {datetime.now().timetuple().tm_yday}"

    history.append(selected)
    save_history(history)

    with open("today_theme.txt", "w", encoding="utf-8") as f:
        f.write(selected)

    print("=== Research Trend Completed ===")
    print(f"Chosen Viral Topic: '{selected}'")
    print(f"Total Unique Topics Recorded: {len(history)}")

if __name__ == "__main__":
    select_and_save_daily_topic()
