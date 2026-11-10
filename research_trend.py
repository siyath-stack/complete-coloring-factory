import os
import json
import time
from pydantic import BaseModel, Field

# Google GenAI SDK
try:
    from google import genai
    from google.genai import types
except ImportError:
    raise ImportError("Please install the Google GenAI SDK: pip install google-genai pydantic")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
HISTORY_FILE = "used_topics.json"
DAILY_PLAN_FILE = "daily_book_plan.json"

# ---------------------------------------------------------------------------
# STRUCTURED PYDANTIC OUTPUT SCHEMA
# ---------------------------------------------------------------------------
class ScenePlan(BaseModel):
    action: str = Field(description="Visual action and setting in simple Monkey.pdf line art style with 1 simple prop and zero background clutter")
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
# GEMINI RESEARCH ENGINE (With Multi-Model Fallback & Backoff Protection)
# ---------------------------------------------------------------------------
def generate_daily_plan():
    if not GEMINI_API_KEY:
        raise ValueError("Missing GEMINI_API_KEY environment variable. Please add it to your secrets or environment.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    history = load_history()
    recent_history_str = ", ".join(history[-40:]) if history else "None"

    prompt = f"""
You are the Creative Director of a top-selling Amazon KDP and Etsy children's coloring book brand, 
celebrated for ultra-simple, high-contrast toddler line art in the exact style of 'Monkey.pdf'.

TASK:
1. Brainstorm an adorable, commercially viral animal or vehicle subject for today's coloring book.
2. Rotate across diverse niches: 
   - Cozy Animals (e.g., baby sea otter, capybara, red panda, axolotl, highland cow, koala)
   - Friendly Vehicles (e.g., cute excavator, cheerful tugboat, little camper van)
   - Whimsical Fantasy (e.g., baby dragon, tiny cloud pegasus, friendly forest gnome)
3. DO NOT repeat any of these previously published subjects: [{recent_history_str}].
4. ENFORCE STRICT MONKEY.PDF SIMPLICITY & SPECIES ACCURACY RULES:
   - Style of Monkey.pdf: ultra-thick 6pt smooth 2D outlines, single central character, simple squishy shapes, wide open spaces for coloring.
   - Pair the character with EXACTLY 1 simple prop per scene (e.g., a single leaf, a balloon, a star, a banana, a straw, a drum).
   - Character DNA MUST specify exact anatomical features to anchor the species across all pages.
   - ZERO fur hatching, ZERO wood grain, ZERO texture lines, ZERO shading, ZERO background clutter.
   - ABSOLUTELY NO human characters, NO human faces, NO adults, NO children under any circumstance.
   - Captions (micro_prompt) MUST 100% align with the visual scene action!
5. SCRIPT A 30-SCENE STORYTELLING ARC (morning to evening):
   - Pages 1 to 6: Morning wake-up, breakfast snack, getting ready.
   - Pages 7 to 18: Midday outdoor adventures, meeting animal friends, playing simple games.
   - Pages 19 to 25: Afternoon hobbies, crafts, snacks, and celebration.
   - Pages 26 to 30: Winding down, gazing at the stars/moon, cozy bedtime sleep.
6. Provide an engaging 1-line educational micro-prompt for every page (counting items, tracing, or coloring specifics).
"""

    # Priority list of models to fall back through if one is at capacity (503)
    candidate_models = ["gemini-2.5-flash", "gemini-1.5-flash"]
    plan_data = None

    for model_name in candidate_models:
        print(f"Attempting book generation with model: '{model_name}'...")
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
                wait_time = 3 * attempt
                print(f"[Notice] {model_name} attempt {attempt}/{max_retries} failed ({e}). Retrying in {wait_time}s...")
                time.sleep(wait_time)

        if plan_data:
            break

    if not plan_data:
        raise RuntimeError("Failed to generate plan across all fallback models. Check network connectivity or API key permissions.")

    # Save plan output
    with open(DAILY_PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2)

    # Record history
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
