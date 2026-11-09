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

SPECIES_DNA_REGISTRY = {
    "friendly baby axolotl": {
        "category": "Freshwater & Sea Life",
        "dna": "adorable chubby baby axolotl, Bobbie Goods cozy line art style, exactly 6 rounded feathery external gills (3 on each side), wide gentle smiling mouth, smooth squishy body, tiny cute paws. STRICTLY NO mammal ears, NO wings, NO fur, NO horns",
        "habitat_keywords": "clear freshwater lagoon with floating lily pads, river stones, and gentle bubbles"
    },
    "cute baby capybara": {
        "category": "Kids Animals",
        "dna": "adorable chubby baby capybara, Bobbie Goods cozy line art style, blunt rounded snout, tiny rounded ears, chunky squishy oval body, webbed paws, sweet calm smile, no tail. STRICTLY NO climbing trees, NO swinging by tail, NO sharp teeth",
        "habitat_keywords": "warm grassy riverbank, sunny clover meadow, calm freshwater pond"
    },
    "chubby red panda explorer": {
        "category": "Woodland Wildlife",
        "dna": "cute chubby baby red panda, Bobbie Goods cozy line art style, fluffy rounded cheeks, thick bushy striped tail, small paws, sweet friendly smile. STRICTLY NO scales, NO fins, NO wings",
        "habitat_keywords": "soft mossy logs, sunny bamboo glade, mountain wildflowers"
    },
    "playful sea otter pup": {
        "category": "Freshwater & Sea Life",
        "dna": "cute baby sea otter, Bobbie Goods cozy line art style, round chubby head, whisker dots, sleek rounded body, floating happily on back in water hugging a smooth river pebble. STRICTLY NO wings, NO dog ears",
        "habitat_keywords": "calm coastal bay, gentle floating kelp, sunny water ripples"
    },
    "little construction excavator": {
        "category": "Kids Vehicles",
        "dna": "cute smiling cartoon construction excavator, Bobbie Goods cozy vehicle style, friendly cartoon eyes on cab, rounded scoop bucket, chunky rolling crawler tracks. STRICTLY NO realistic sharp machinery",
        "habitat_keywords": "friendly sandbox construction site, smooth dirt ramps, safety cones"
    },
    "friendly baby dragon": {
        "category": "Fantasy & Fairytale",
        "dna": "adorable chubby baby dragon, Bobbie Goods cozy style, soft rounded belly, tiny rounded wings, smooth head with two small rounded horn nubs, sweet joyful face. STRICTLY NO scary fangs, NO fire",
        "habitat_keywords": "magical wildflower meadow, gentle rolling hills, rainbow clouds"
    }
}

FALLBACK_TOPICS = list(SPECIES_DNA_REGISTRY.keys())

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
    prompt = (
        "You are an expert children's coloring book editor analyzing Bobbie Goods and Amazon KDP trends. "
        "Suggest 8 trending, adorable character subjects across Kids Animals, Vehicles, and Fantasy "
        "(e.g., 'friendly baby axolotl', 'cute baby capybara', 'chubby red panda explorer', 'playful sea otter pup'). "
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
    return FALLBACK_TOPICS

def generate_scenes_for_subject(subject, dna_info):
    habitat_context = dna_info.get("habitat_keywords", "natural habitat")
    prompt = (
        f"You are writing a 30-page cozy children's coloring book featuring: '{subject}' in a Bobbie Goods cute cozy style. "
        f"Natural habitat context: {habitat_context}. "
        "Write 30 distinct, charming, age-appropriate coloring scenes (pages 1 to 30) for toddlers and kids. "
        "STRICT HABITAT AND ANATOMY RULES: "
        "1. Scenes MUST match this character's natural physical anatomy and setting (aquatic animals stay in ponds/lagoons, "
        "capybaras on riverbanks/meadows). NEVER put fully aquatic creatures on dry land. "
        "2. Add playful cozy moments: floating with bubbles, smelling blossoms, drinking boba juice, baking cookies, hugging teddy bears, looking at the crescent moon. "
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

    return [
        {"action": f"waving hello with a sweet warm smile in {habitat_context}", "micro_prompt": "Can you wave hello and color my big smile?"},
        {"action": "happily floating with tiny water ripples and bubbles", "micro_prompt": "Color the gentle splashing water ripples bright blue!"},
        {"action": "peacefully balancing a sweet little blossom flower on head", "micro_prompt": "Find the tiny flower! What color will you make it?"},
        {"action": "resting peacefully beside smooth rounded river pebbles", "micro_prompt": "Count the smooth river stones: 1, 2, 3!"},
        {"action": "chatting with a friendly smiling baby fish companion", "micro_prompt": "Color the little fish friend sunny yellow!"},
        {"action": "wearing a cozy wide-brimmed sun hat decorated with ribbon", "micro_prompt": "Make the explorer hat colorful!"},
        {"action": "blowing giant round translucent bubbles into the clear water", "micro_prompt": "Count the 3 giant floating bubbles: 1, 2, 3!"},
        {"action": "curiously watching a friendly smiling butterfly fluttering past", "micro_prompt": "Color both wings of the cute butterfly!"},
        {"action": "gently floating with eyes closed in peaceful relaxation", "micro_prompt": "So relaxing! Color the gentle water waves!"},
        {"action": "building a neat stack of smooth rounded river stones", "micro_prompt": "Count the rounded stones in the stack!"},
        {"action": "holding a small cluster of floating balloons", "micro_prompt": "Make each balloon a different rainbow color!"},
        {"action": "sitting side by side with a gentle smiling baby turtle", "micro_prompt": "Color the cute pattern on the turtle shell!"},
        {"action": "wearing a playful party hat surrounded by floating confetti", "micro_prompt": "Party time! Color all the party confetti!"},
        {"action": "peeking playfully from behind a friendly broad river lily pad", "micro_prompt": "Play peekaboo! What color will you make the leaf?"},
        {"action": "splashing playfully creating cheerful water droplets", "micro_prompt": "Splish splash! Color the cute water droplets!"},
        {"action": "snuggling cozy beside its mother on soft mossy ground", "micro_prompt": "Give baby and mommy a warm, cozy color!"},
        {"action": "sipping sweet juice through a fun striped straw from a round fruit cup", "micro_prompt": "Color the stripes on the straw: red and blue!"},
        {"action": "carrying a little woven basket filled with sweet ripe berries", "micro_prompt": "Color the sweet strawberries bright red!"},
        {"action": "curiously inspecting a friendly little snail on a water plant", "micro_prompt": "Find the tiny swirl on the snail shell!"},
        {"action": "making a funny silly face in the reflection of a calm water pool", "micro_prompt": "Smile! Color the funny water reflection!"},
        {"action": "proudly wearing a junior nature explorer medal ribbon", "micro_prompt": "Color the star badge shiny gold!"},
        {"action": "happily sharing a sweet melon slice with a friendly little songbird", "micro_prompt": "Good friends share! Color the sweet fruit!"},
        {"action": "rolling a giant smooth polished river stone like a toy ball", "micro_prompt": "Color the shiny smooth river stone!"},
        {"action": "dancing happily with cute musical notes floating in the water", "micro_prompt": "Color the musical notes your favorite color!"},
        {"action": "watching a colorful diamond-shaped kite in the bright sky above", "micro_prompt": "Color the kite with bright rainbow patterns!"},
        {"action": "curled up cozy on a soft blanket of gentle green moss", "micro_prompt": "So cozy! Color the soft water moss blanket!"},
        {"action": "taking a joyful victory bow with paws outstretched in excitement", "micro_prompt": "Ta-da! You're doing an amazing job coloring!"},
        {"action": "gazing at a smiling crescent moon and twinkling night stars", "micro_prompt": "Count the 4 twinkling stars in the sky!"},
        {"action": "curled up fast asleep with a little leaf blanket under starry sky", "micro_prompt": "Sweet dreams! Color the peaceful night scene!"},
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
            if fb not in history:
                chosen_subject = fb
                break

    if not chosen_subject:
        chosen_subject = f"friendly baby axolotl {datetime.now().strftime('%m%d')}"

    print(f"Selected Unique Trending Topic: '{chosen_subject}'")

    matched_dna = None
    for k, v in SPECIES_DNA_REGISTRY.items():
        if k in chosen_subject or chosen_subject in k:
            matched_dna = v
            break

    if not matched_dna:
        matched_dna = {
            "category": "Cozy Kids Characters",
            "dna": f"adorable chubby {chosen_subject}, Bobbie Goods cozy line art style, chunky squishy proportions, large expressive eyes, simplified smooth anatomy, friendly happy face",
            "habitat_keywords": "pleasant cozy setting, sunny day"
        }

    scenes = generate_scenes_for_subject(chosen_subject, matched_dna)

    daily_plan = {
        "subject": chosen_subject,
        "category": matched_dna.get("category", "Cozy Kids Characters"),
        "character_dna": matched_dna["dna"],
        "habitat_keywords": matched_dna.get("habitat_keywords", ""),
        "scenes": scenes
    }

    with open(DAILY_PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(daily_plan, f, indent=2)

    history.append(chosen_subject)
    save_history(history)
    print(f"Saved daily plan with {len(scenes)} scenes to '{DAILY_PLAN_FILE}'. Total history: {len(history)}")

if __name__ == "__main__":
    plan_daily_book()
