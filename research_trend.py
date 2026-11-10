import os
import json
import time
import random
from pydantic import BaseModel, Field

# Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
HISTORY_FILE = "used_topics.json"
DAILY_PLAN_FILE = "daily_book_plan.json"

# ---------------------------------------------------------------------------
# STRUCTURED PYDANTIC OUTPUT SCHEMA
# ---------------------------------------------------------------------------
class ScenePlan(BaseModel):
    action: str = Field(description="Visual action in simple Monkey.pdf line art style with 1 simple prop and zero background clutter")
    micro_prompt: str = Field(description="A 1-line interactive coloring/counting prompt for kids matching the exact action (e.g. 'Count the 3 floating bubbles!')")

class DailyBookPlan(BaseModel):
    subject: str = Field(description="Unique character subject name and species (e.g. 'cheerful baby sea otter')")
    category: str = Field(description="Niche category (e.g. 'Freshwater Lagoon Explorers')")
    target_age: str = Field(description="Target age bracket (e.g. 'Ages 2-5 Toddler Bold & Easy')")
    character_dna: str = Field(description="Strict anatomical definition anchor enforcing species accuracy (e.g. 'adorable chubby baby sea otter, round squishy belly, small ears, simple whiskers, no human features, 2D vector line art')")
    habitat_rules: str = Field(description="Habitat and background constraints")
    scenes: list[ScenePlan] = Field(description="Exactly 30 sequential scenes telling a morning-to-night story arc")

# ---------------------------------------------------------------------------
# TOPIC HISTORY TRACKING
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# FALLBACK PLAN GENERATOR (Guarantees zero pipeline crashes on API 503 spikes)
# ---------------------------------------------------------------------------
def generate_fallback_plan(history):
    print("[Notice] Gemini API unavailable due to 503 capacity spikes. Activating zero-downtime architecture plan...")
    
    fallback_templates = [
        {
            "subject": "Barnaby the Baby Capybara",
            "category": "Cozy Riverbank Explorers",
            "target_age": "Ages 2-5 Toddler Bold & Easy",
            "character_dna": "adorable chubby baby capybara pup, round squishy body, tiny rounded ears, blunt snout, short legs, no tail, 2D vector line art",
            "habitat_rules": "Cozy grassy riverbank with gentle water ripples and simple flowers",
            "base_prop": "orange"
        },
        {
            "subject": "Hamish the Fluffy Highland Calf",
            "category": "Meadow Sunshine Adventures",
            "target_age": "Ages 2-5 Toddler Bold & Easy",
            "character_dna": "adorable chubby baby highland cow calf, round fluffy body, tiny nubs for horns, big round snout, short legs, 2D vector line art",
            "habitat_rules": "Sunny open meadow with simple daisy flowers and rolling hills",
            "base_prop": "sunflower"
        },
        {
            "subject": "Pip the Playful Sea Otter Pup",
            "category": "Lagoon Bubble Party",
            "target_age": "Ages 2-5 Toddler Bold & Easy",
            "character_dna": "adorable chubby baby sea otter pup, floating on back, round belly, small rounded ears, simple whisker dots, 2D vector line art",
            "habitat_rules": "Calm coastal water with simple floating kelp and gentle ripples",
            "base_prop": "sea star"
        }
    ]

    # Select a subject not recently used
    unused = [t for t in fallback_templates if t["subject"] not in history]
    selected = random.choice(unused) if unused else random.choice(fallback_templates)
    
    props = [
        ("holding a chunky toddler toothbrush", "Color the toothbrush bright yellow!"),
        ("munching on one single oversized strawberry", "Trace the 3 tiny seeds on the strawberry!"),
        ("balancing a smooth round apple on head", "Count the 1 big apple on top!"),
        ("wearing a cheerful wide-brimmed sunhat", "Color the sunhat with your favorite crayon!"),
        ("patting one simple floating beach ball", "Color the 3 stripes on the beach ball!"),
        ("patting one little rubber ducky in water", "Count the 1 cute rubber ducky!"),
        ("holding the string of one round balloon", "Color the round balloon bright red!"),
        ("Patting a smooth round river stone", "Count the 1 smooth stone underfoot!"),
        ("patting a fluffy star-shaped pillow", "Color the star pillow soft blue!"),
        ("looking up at a single smiling crescent moon", "Count the 1 glowing crescent moon!")
    ]
    
    scenes = []
    for i in range(1, 31):
        prop_action, prompt_text = props[(i - 1) % len(props)]
        action_desc = f"{selected['subject']} {prop_action} in a simple background."
        scenes.append({
            "action": action_desc,
            "micro_prompt": f"Page {i}: {prompt_text}"
        })
        
    return {
        "subject": selected["subject"],
        "category": selected["category"],
        "target_age": selected["target_age"],
        "character_dna": selected["character_dna"],
        "habitat_rules": selected["habitat_rules"],
        "scenes": scenes
    }

# ---------------------------------------------------------------------------
# GEMINI RESEARCH ENGINE
# ---------------------------------------------------------------------------
def generate_daily_plan():
    history = load_history()
    recent_history_str = ", ".join(history[-40:]) if history else "None"
    plan_data = None

    if GEMINI_API_KEY and HAS_GENAI:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""
You are the Creative Director of a top-selling Amazon KDP children's coloring book brand, 
celebrated for ultra-simple, high-contrast toddler line art in the exact style of 'Monkey.pdf'.

TASK:
1. Brainstorm an adorable animal or vehicle subject for today's coloring book.
2. DO NOT repeat any of these previously published subjects: [{recent_history_str}].
3. ENFORCE STRICT MONKEY.PDF SIMPLICITY RULES:
   - Style of Monkey.pdf: ultra-thick 6pt smooth 2D outlines, single central character, simple squishy shapes, wide open spaces for coloring.
   - Pair the character with EXACTLY 1 simple prop per scene (e.g., a single leaf, a balloon, a star, a banana, a straw, a drum).
   - Character DNA MUST specify exact anatomical features to anchor the species across all pages.
   - ZERO fur hatching, ZERO wood grain, ZERO texture lines, ZERO shading, ZERO background clutter.
   - ABSOLUTELY NO human characters, NO human faces, NO adults, NO children under any circumstance.
   - Captions (micro_prompt) MUST 100% align with the visual scene action!
4. SCRIPT A 30-SCENE STORYTELLING ARC (morning to evening).
"""
        candidate_models = ["gemini-3.8-flash", "gemini-2.0-flash-exp"]

        for model_name in candidate_models:
            print(f"Attempting book architecture generation with model: '{model_name}'...")
            max_retries = 3

            for attempt in range(1, max_retries + 1):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=DailyBookPlan,
                            temperature=0.95,
                        ),
                    )
                    if response and response.text:
                        plan_data = json.loads(response.text)
                        print(f"Successfully generated daily plan using '{model_name}'!")
                        break
                except Exception as e:
                    err_msg = str(e)
                    if "NOT_FOUND" in err_msg or "404" in err_msg:
                        print(f"[Notice] Model '{model_name}' returned 404. Trying next candidate...")
                        break
                    wait_time = min(15, (2 ** attempt) + random.uniform(1, 3))
                    print(f"[Notice] Retry attempt {attempt}/{max_retries} in {wait_time:.1f}s...")
                    time.sleep(wait_time)

            if plan_data:
                break

    # If API calls fail or hit demand limits, execute fallback plan
    if not plan_data:
        plan_data = generate_fallback_plan(history)

    # Save daily plan
    with open(DAILY_PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2)

    history.append(plan_data["subject"])
    save_history(history)

    print("=====================================================")
    print(f"Selected Subject: '{plan_data['subject']}'")
    print(f"Category: {plan_data['category']} ({plan_data['target_age']})")
    print(f"Character DNA: {plan_data['character_dna']}")
    print(f"Total Scenes Generated: {len(plan_data['scenes'])}")
    print(f"Saved to '{DAILY_PLAN_FILE}'.")
    print("=====================================================")

if __name__ == "__main__":
    generate_daily_plan()
