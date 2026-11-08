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
DAILY_PLAN_FILE = "daily_book_plan.json"

FALLBACK_TOPICS = [
    {"subject": "cute baby capybara", "category": "Kids Animals", "habitat": "warm riverbank, grassy meadow, and clear freshwater pond"},
    {"subject": "friendly baby axolotl", "category": "Ocean & Sea Life", "habitat": "crystal clear underwater coral reef and freshwater lagoon"},
    {"subject": "chubby red panda explorer", "category": "Woodland Wildlife", "habitat": "bamboo forest, mossy logs, and misty mountain glades"},
    {"subject": "playful sea otter pup", "category": "Ocean & Sea Life", "habitat": "kelp forest, floating riverbanks, and sunny seaside rocks"},
    {"subject": "little construction excavator", "category": "Kids Vehicles", "habitat": "friendly sand building site, smooth ramps, and gravel piles"},
    {"subject": "friendly baby dragon", "category": "Fantasy & Fairytale", "habitat": "magical wildflower meadow, gentle rolling hills, and stone bridges"}
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

def query_cloudflare_text(prompt, max_retries=3):
    if not ACCOUNT_ID or not API_TOKEN:
        return ""
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    for attempt in range(max_retries):
        try:
            res = requests.post(API_URL, headers=headers, json={"prompt": prompt}, timeout=40)
            res.raise_for_status()
            data = res.json()
            return data.get("result", {}).get("response", "")
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"[Warning] Text AI API: {e}")
            pass
    return ""

def discover_trending_subject():
    """Identifies viral children's coloring book character niches (Amazon KDP / Etsy)."""
    prompt = (
        "You are an expert children's coloring book editor analyzing Amazon KDP and Etsy trends. "
        "Suggest 8 trending, adorable character subjects across Kids Animals, Vehicles, and Fantasy "
        "(e.g., 'cute baby capybara', 'happy baby otter', 'friendly baby excavator', 'playful baby axolotl'). "
        "Return ONLY a clean JSON array of strings: [\"topic 1\", \"topic 2\", ...]. No markdown, no commentary."
    )
    raw = query_cloudflare_text(prompt)
    try:
        match = re.search(r'\\[.*\\]', raw, re.DOTALL)
        if match:
            candidates = json.loads(match.group(0))
            return [str(c).strip().lower() for c in candidates if isinstance(c, str)]
    except Exception:
        pass
    return [t["subject"] for t in FALLBACK_TOPICS]

def generate_scenes_for_subject(subject):
    """Generates 30 habitat-accurate, behavior-appropriate scenes for this exact character."""
    prompt = (
        f"You are writing a 30-page children's coloring book featuring: '{subject}'. "
        "Write 30 distinct, charming, age-appropriate scenes (pages 1 to 30) for toddlers and young kids. "
        "STRICT ANATOMICAL AND HABITAT RULES: "
        "1. Scenes MUST match this character's natural physical anatomy and setting (e.g., capybaras/otters in water and meadows, "
        "excavators on friendly construction sand piles, monkeys in trees). DO NOT give tails or tree-climbing to non-climbing animals. "
        "2. Add playful kid-friendly moments: splashing water, smelling flowers, holding balloons, eating snacks, gazing at the moon. "
        "3. Pair every action with a simple 1-line interactive coloring prompt for a toddler (e.g., 'Can you count the 3 floating bubbles?'). "
        "Return ONLY a JSON array of 30 objects: [{\"action\": \"...\", \"micro_prompt\": \"...\"}]. No markdown or preamble."
    )
    raw = query_cloudflare_text(prompt)
    try:
        match = re.search(r'\\[.*\\]', raw, re.DOTALL)
        if match:
            scenes = json.loads(match.group(0))
            if len(scenes) >= 25:
                return scenes[:30]
    except Exception:
        pass

    # Reliable fallback scenes with diverse actions
    return [
        {"action": "waving hello with a cheerful warm smile standing in a sunny meadow", "micro_prompt": "Can you wave hello and color my big smile?"},
        {"action": "happily splashing in a calm clear water pond with tiny water ripples", "micro_prompt": "Color the splashing water ripples bright blue!"},
        {"action": "peacefully balancing a sweet little blossom flower on head", "micro_prompt": "Find the tiny flower! What color will you make it?"},
        {"action": "sitting on a grassy riverbank eating fresh sweet green clover", "micro_prompt": "Color the clover leaves bright green!"},
        {"action": "perched beside a calm pond chatting with a friendly smiling duckling", "micro_prompt": "Can you color the baby duckling sunny yellow?"},
        {"action": "wearing a cute wide-brimmed sun hat decorated with a ribbon", "micro_prompt": "Make the explorer hat colorful!"},
        {"action": "blowing giant round iridescent soap bubbles into the sunny sky", "micro_prompt": "Count the 3 giant floating bubbles: 1, 2, 3!"},
        {"action": "curiously watching a friendly smiling butterfly land on a leaf", "micro_prompt": "Color both wings of the cute butterfly!"},
        {"action": "gently floating in warm water with eyes closed in pure joy", "micro_prompt": "So relaxing! Color the gentle water waves!"},
        {"action": "building a neat stack of smooth rounded river stones", "micro_prompt": "Count the rounded stones in the stack!"},
        {"action": "holding a small cluster of colorful balloons tied to wrist", "micro_prompt": "Make each balloon a different rainbow color!"},
        {"action": "sitting side by side with a gentle smiling baby turtle", "micro_prompt": "Color the cute pattern on the turtle shell!"},
        {"action": "wearing a playful paper party hat surrounded by floating confetti", "micro_prompt": "Party time! Color all the party confetti!"},
        {"action": "peeking playfully from behind a friendly broad river lily leaf", "micro_prompt": "Play peekaboo! What color will you make the leaf?"},
        {"action": "splashing playfully with feet in warm mud puddle with rain boots", "micro_prompt": "Splish splash! Color the cute little boots!"},
        {"action": "snuggling cozy beside its mother on soft mossy grass", "micro_prompt": "Give baby and mommy a warm, cozy color!"},
        {"action": "sipping sweet juice through a fun striped straw from a round fruit cup", "micro_prompt": "Color the stripes on the straw: red and blue!"},
        {"action": "carrying a little woven basket filled with sweet ripe berries", "micro_prompt": "Color the sweet strawberries bright red!"},
        {"action": "curiously inspecting a friendly little ladybug on a dandelion", "micro_prompt": "Find the tiny spots on the ladybug!"},
        {"action": "making a funny silly face in the reflection of a calm water puddle", "micro_prompt": "Smile! Color the funny puddle reflection!"},
        {"action": "proudly wearing a junior nature explorer medal ribbon", "micro_prompt": "Color the star badge shiny gold!"},
        {"action": "happily sharing a sweet melon slice with a friendly little songbird", "micro_prompt": "Good friends share! Color the sweet fruit!"},
        {"action": "rolling a giant smooth polished river stone like a toy ball", "micro_prompt": "Color the shiny smooth river stone!"},
        {"action": "dancing happily with cute musical notes floating in the air", "micro_prompt": "Color the musical notes your favorite color!"},
        {"action": "flying a colorful diamond-shaped kite high against puffy clouds", "micro_prompt": "Count the puffy clouds in the sky!"},
        {"action": "curled up cozy on a soft blanket of warm moss", "micro_prompt": "So cozy! Color the soft grass blanket!"},
        {"action": "taking a joyful victory bow with paws outstretched in excitement", "micro_prompt": "Ta-da! You're doing an amazing job coloring!"},
        {"action": "sitting peacefully on a riverbank gazing at a smiling crescent moon", "micro_prompt": "Count the 4 twinkling stars in the sky!"},
        {"action": "curled up fast asleep with a little leaf blanket under starry night sky", "micro_prompt": "Sweet dreams! Color the peaceful night scene!"},
        {"action": "smiling peacefully fast asleep with happy dreaming bubbles", "micro_prompt": "Great job! You finished every coloring page!"}
    ]

def plan_daily_book():
    history = load_history()
    candidates = discover_trending_subject()

    chosen_subject = None
    for cand in candidates:
        if cand and cand not in history:
            chosen_subject = cand
            break

    if not chosen_subject:
        for fb in FALLBACK_TOPICS:
            if fb["subject"] not in history:
                chosen_subject = fb["subject"]
                break

    if not chosen_subject:
        chosen_subject = f"happy animal adventure {datetime.now().strftime('%m%d')}"

    print(f"✅ Selected Unique Trending Topic: '{chosen_subject}'")
    scenes = generate_scenes_for_subject(chosen_subject)

    daily_plan = {
        "subject": chosen_subject,
        "category": "Trending Kids Characters",
        "character_dna": f"adorable kawaii {chosen_subject}, chubby cheeks, large expressive cartoon eyes with dual highlights, rounded body, simplified anatomy, smiling friendly face",
        "scenes": scenes
    }

    with open(DAILY_PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(daily_plan, f, indent=2)

    history.append(chosen_subject)
    save_history(history)
    print(f"Saved daily plan with {len(scenes)} scenes to '{DAILY_PLAN_FILE}'. Total history: {len(history)}")

if __name__ == "__main__":
    plan_daily_book()
