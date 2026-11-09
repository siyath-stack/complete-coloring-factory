import os
import json
import time
from pydantic import BaseModel, Field

# Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
except ImportError:
    raise ImportError("Please install the Google GenAI SDK: pip install google-genai pydantic")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
HISTORY_FILE = "used_topics.json"
DAILY_PLAN_FILE = "daily_book_plan.json"

# ---------------------------------------------------------------------------
# STRUCTURED PYDANTIC OUTPUT SCHEMA
# ---------------------------------------------------------------------------
class ScenePlan(BaseModel):
    action: str = Field(description="Visual action and setting in Bobbie Goods cozy line art style")
    micro_prompt: str = Field(description="A 1-line interactive coloring/counting prompt for kids (e.g. 'Count the 3 floating bubbles!')")

class DailyBookPlan(BaseModel):
    subject: str = Field(description="Unique character subject (e.g. 'cheerful baby axolotl')")
    category: str = Field(description="Niche category (e.g. 'Freshwater Lagoon Explorers')")
    target_age: str = Field(description="Target age bracket (e.g. 'Ages 3-6')")
    character_dna: str = Field(description="Strict visual style & anatomical definition anchor for image diffusion")
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
# GEMINI RESEARCH ENGINE (With Automatic Retry & Fallbacks)
# ---------------------------------------------------------------------------
def generate_daily_plan():
    if not GEMINI_API_KEY:
        raise ValueError("Missing GEMINI_API_KEY environment variable. Please add it to your secrets or environment.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    history = load_history()
    recent_history_str = ", ".join(history[-40:]) if history else "None"

    prompt = f"""
You are the Creative Director of a top-selling Amazon KDP and Etsy children's coloring book brand, 
celebrated for the viral 'Bobbie Goods / Coco Wyo' cozy & bold aesthetic.

TASK:
1. Brainstorm an adorable, commercially viral character subject for today's coloring book.
2. Rotate across diverse niches: 
   - Cozy Animals (e.g., axolotl, capybara, red panda, otter, highland cow)
   - Friendly Construction & Vehicles (e.g., cute excavator, cheerful tugboat, little camper van)
   - Whimsical Fantasy (e.g., baby dragon, tiny cloud pegasus, forest gnome)
   - Cozy Everyday Life (e.g., bakery puppy, garden bunny, tea-party kitten)
3. DO NOT repeat any of these previously published subjects: [{recent_history_str}].
4. ENFORCE STRICT BIOLOGICAL & HABITAT ACCURACY:
   - Aquatic creatures (axolotls, sea otters, whales) MUST stay in clear water/lagoons with bubbles and water lilies—NEVER on dry land, climbing trees, or in mud puddles with boots.
   - Ground animals (capybaras, cows) MUST NOT climb trees or swing by tails.
5. SCRIPT A 30-SCENE STORYTELLING ARC (morning to evening):
   - Pages 1 to 6: Morning wake-up, breakfast snack, getting ready.
   - Pages 7 to 18: Midday outdoor adventures, meeting friends, playing games.
   - Pages 19 to 25: Afternoon hobbies, crafts, snacks, and celebration.
   - Pages 26 to 30: Winding down, gazing at the stars/moon, cozy bedtime sleep.
6. Provide an engaging 1-line educational micro-prompt for every page (counting items, tracing, or coloring specifics).
"""

    # Candidate models to iterate through if a 503 high-demand spike occurs
    candidate_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    response = None

    for model_name in candidate_models:
        print(f"Attempting book plan generation with '{model_name}'...")
        for attempt in range(1, 4):
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
                    print(f"Successfully generated plan using '{model_name}'.")
                    break
            except APIError as e:
                print(f"[503/API Notice] {model_name} attempt {attempt} failed: {e}. Retrying in {5 * attempt}s...")
                time.sleep(5 * attempt)
            except Exception as e:
                print(f"[Notice] {model_name} attempt {attempt} failed: {e}. Retrying in {5 * attempt}s...")
                time.sleep(5 * attempt)

        if response and response.text:
            break

    if not response or not response.text:
        raise RuntimeError("Failed to generate plan after retrying across available Gemini models.")

    plan_data = json.loads(response.text)

    # Save today's plan
    with open(DAILY_PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2)

    # Record topic history
    history.append(plan_data["subject"])
    save_history(history)

    print("=====================================================")
    print(f"Gemini Selected Subject: '{plan_data['subject']}'")
    print(f"Category: {plan_data['category']} ({plan_data['target_age']})")
    print(f"Character DNA Anchor: {plan_data['character_dna']}")
    print(f"Total Scenes Generated: {len(plan_data['scenes'])}")
    print(f"Saved to '{DAILY_PLAN_FILE}'. Total recorded topics: {len(history)}")
    print("=====================================================")

if __name__ == "__main__":
    generate_daily_plan()
