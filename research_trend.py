import os
import json
import requests
from datetime import datetime

ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")
TEXT_MODEL = "@cf/meta/llama-3.1-8b-instruct"
API_URL = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/{TEXT_MODEL}"

HISTORY_FILE = "used_topics.json"

# Load or initialize topic history
if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        used_topics = json.load(f)
else:
    used_topics = []

def get_viral_theme_candidate():
    """Asks Cloudflare AI to suggest high-demand children's coloring book topics."""
    prompt = (
        "You are an expert children's coloring book publisher analyzing Amazon KDP and TikTok trends. "
        "Suggest 5 trending, highly engaging children's coloring book character topics "
        "(e.g., 'baby capybara in cute outfits', 'friendly baby axolotl', 'chubby red panda explorer', "
        "'kawaii baby highland cow', 'magical baby sea otter'). "
        "Return ONLY a raw JSON array of 5 strings, nothing else. Example: [\"topic 1\", \"topic 2\", ...]"
    )
    
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    response = requests.post(API_URL, headers=headers, json={"prompt": prompt}, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    result_text = data.get("result", {}).get("response", "")
    
    # Extract JSON list
    try:
        import re
        match = re.search(r'\\[.*?\\]', result_text, re.DOTALL)
        if match:
            candidates = json.loads(match.group(0))
            return [c.strip().lower() for c in candidates if isinstance(c, str)]
    except Exception:
        pass
        
    return ["friendly baby axolotl", "baby highland cow", "chubby red panda", "baby capybara"]

def select_unique_daily_theme():
    candidates = get_viral_theme_candidate()
    
    # Pick the first candidate that hasn't been used yet
    chosen_topic = None
    for cand in candidates:
        if cand not in used_topics:
            chosen_topic = cand
            break
            
    # Fallback if all candidates were used
    if not chosen_topic:
        chosen_topic = f"{candidates[0]} adventure {datetime.now().strftime('%B')}"

    # Log to history
    used_topics.append(chosen_topic)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(used_topics, f, indent=2)
        
    # Write today's active topic for generate_book.py to read
    with open("today_theme.txt", "w", encoding="utf-8") as f:
        f.write(chosen_topic)
        
    print(f"✅ Selected Unique Trending Topic for Today: '{chosen_topic}'")
    print(f"📊 Total Unique Books in History: {len(used_topics)}")

if __name__ == "__main__":
    select_unique_daily_theme()
