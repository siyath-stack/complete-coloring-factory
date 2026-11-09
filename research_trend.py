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

# Strict anatomical and habitat anchors for key coloring book subjects
SPECIES_DNA_REGISTRY = {
    "friendly baby axolotl": {
        "category": "Freshwater & Sea Life",
        "dna": "adorable baby aquatic axolotl, Mexican walking fish, exactly 6 pink feathery external gills (3 on each side of head), wide smiling amphibian face, smooth skin, tiny front and back legs with cute digits, swimming in clear freshwater. STRICTLY NO mammalian ears, NO fur, NO dog snout, NO bird wings, NO feathers on body, NO horns, NO dry land",
        "habitat_keywords": "clear freshwater lagoon, smooth river stones, gentle floating bubbles, underwater water-lily pads"
    },
    "cute baby capybara": {
        "category": "Kids Animals",
        "dna": "adorable baby capybara, blunt square snout, small rounded ears high on head, webbed paws, semi-aquatic rodent, chunky oval body, no tail, gentle calm smiling expression. STRICTLY NO tree climbing, NO swinging by tail, NO monkey paws, NO buck teeth",
        "habitat_keywords": "warm riverbank, sunny grassy meadow, calm freshwater pond, floating lotus flowers"
    },
    "chubby red panda explorer": {
        "category": "Woodland Wildlife",
        "dna": "cute chubby baby red panda, white markings on muzzle and eyebrow spots, rounded fluffy ears, thick ringed bushy tail, small paws with soft pads, joyful playful expression. STRICTLY NO scales, NO fins, NO wings",
        "habitat_keywords": "mossy forest logs, green bamboo stalks, sunny mountain meadow, wildflowers"
    },
    "playful sea otter pup": {
        "category": "Freshwater & Sea Life",
        "dna": "cute baby sea otter, small rounded ears, whisker pads, sleek aquatic body, floating happily on back in water, holding paws over chest. STRICTLY NO dry desert, NO bird wings, NO dog ears",
        "habitat_keywords": "calm coastal waters, kelp canopy, smooth river pebbles, sunny seaside rocks"
    },
    "little construction excavator": {
        "category": "Kids Vehicles",
        "dna": "cute smiling cartoon construction excavator, friendly eyes on vehicle cab, sturdy digging boom arm, large front scoop bucket, rugged continuous crawler tracks. STRICTLY NO animal parts, NO fur",
        "habitat_keywords": "friendly sandbox construction site, smooth gravel ramps, safety cones, soft dirt mounds"
    },
    "friendly baby dragon": {
        "category": "Fantasy & Fairytale",
        "dna": "adorable baby fairytale dragon, chubby round belly, tiny rounded wings, soft smiling muzzle, two small rounded horn nubs, cute playful cartoon eyes. STRICTLY NO scary fangs, NO fire destruction, NO sharp spines",
        "habitat_keywords": "magical wildflower valley, gentle rolling hills, rainbow clouds, ancient stone bridges"
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
        "You are an expert children's coloring book editor analyzing Amazon KDP and Etsy trends. "
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
        f"You are writing a 30-page children's coloring book featuring: '{subject}'. "
        f"Natural habitat and context: {habitat_context}. "
        "Write 30 distinct, charming, age-appropriate coloring scenes (pages 1 to 30) for toddlers and young kids. "
        "STRICT HABITAT AND ANATOMY RULES: "
        "1. Scenes MUST match this character's natural physical anatomy and setting (e.g., axolotls/otters MUST stay in water ponds/lagoons, "
        "capybaras on riverbanks/meadows, excavators on friendly construction sand piles). NEVER put fully aquatic creatures on dry land. "
        "2. Add playful kid-friendly moments: floating with bubbles, smelling floating blossoms, wearing tiny party hats, waving hello, looking at the moon. "
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

    # Generic aquatic/ground resilient fallback scenes
    return [
        {"action": f"waving hello with a cheerful warm smile in {habitat_context}", "micro_prompt": "Can you wave hello and color my big smile?"},
        {"action": "happily swimming and splashing with tiny water ripples", "micro_prompt": "Color the gentle splashing water ripples bright blue!"},
        {"action": "peacefully balancing a sweet little blossom flower on head", "micro_prompt": "Find the tiny flower! What color will you make it?"},
        {"action": "resting peacefully beside smooth rounded river pebbles", "micro_prompt": "Count the smooth river stones: 1, 2, 3!"},
        {"action": "chatting with a friendly smiling baby fish companion", "micro_prompt": "Color the little fish friend sunny yellow!"},
        {"action": "wearing a cute wide-brimmed sun hat decorated with ribbon", "micro_prompt": "Make the explorer hat colorful!"},
        {"action": "blowing giant round translucent bubbles into the clear water", "micro_prompt": "Count the 3 giant floating bubbles: 1, 2, 3!"},
        {"action": "curiously watching a friendly smiling butterfly fluttering past", "micro_prompt": "Color both wings of the cute butterfly!"},
        {"action": "gently floating with eyes closed in peaceful relaxation", "micro_prompt": "So relaxing! Color the gentle water waves!"},
        {"action": "building a neat stack of smooth rounded river stones", "micro_prompt": "Count the rounded stones in the stack!"},
        {"action": "holding a small cluster of floating water balloons", "micro_prompt": "Make each balloon a different rainbow color!"},
        {"action": "sitting side by side with a gentle smiling baby turtle", "micro_prompt": "Color the cute pattern on the turtle shell!"},
        {"action": "wearing a playful paper party hat surrounded by floating confetti", "micro_prompt": "Party time! Color all the party confetti!"},
        {"action": "peeking playfully from behind a friendly broad freshwater water-lily pad", "micro_prompt": "Play peekaboo! What color will you make the leaf?"},
        {"action": "splashing playfully with feet creating cheerful water droplets", "micro_prompt": "Splish splash! Color the cute water droplets!"},
        {"action": "snuggling cozy beside its mother on soft mossy riverbed", "micro_prompt": "Give baby and mommy a warm, cozy color!"},
        {"action": "sipping sweet juice through a fun striped straw from a round fruit cup", "micro_prompt": "Color the stripes on the straw: red and blue!"},
        {"action": "carrying a little woven basket filled with sweet ripe berries", "micro_prompt": "Color the sweet strawberries bright red!"},
        {"action": "curiously inspecting a friendly little snail on a freshwater plant", "micro_prompt": "Find the tiny swirl on the snail shell!"},
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

    # Resolve DNA info
    matched_dna = None
    for k, v in SPECIES_DNA_REGISTRY.items():
        if k in chosen_subject or chosen_subject in k:
            matched_dna = v
            break

    if not matched_dna:
        matched_dna = {
            "category": "Kids Characters",
            "dna": f"adorable kawaii {chosen_subject}, chubby cheeks, large expressive cartoon eyes with dual highlights, rounded body, simplified anatomy, smiling friendly face",
            "habitat_keywords": "pleasant natural habitat, gentle landscape, sunny day"
        }

    scenes = generate_scenes_for_subject(chosen_subject, matched_dna)

    daily_plan = {
        "subject": chosen_subject,
        "category": matched_dna.get("category", "Kids Characters"),
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
