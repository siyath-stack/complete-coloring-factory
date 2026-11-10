import os
import json
import time
import random
from pydantic import BaseModel, Field

try:
    from google import genai
    from google.genai import types
except ImportError:
    raise ImportError("Please install the Google GenAI SDK: pip install google-genai pydantic")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
HISTORY_FILE = "used_topics.json"
DAILY_PLAN_FILE = "daily_book_plan.json"

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

def generate_daily_plan():
    if not GEMINI_API_KEY:
        raise ValueError("Missing GEMINI_API_KEY environment variable.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    history = load_history()
    recent_history_str = ", ".join(history[-40:]) if history else "None"

    prompt = f"""
You are the Creative Director of a top-selling Amazon KDP and Etsy children's coloring book brand, 
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

    candidate_models = ["gemini-3.8-flash", "gemini-2.0-flash"]
    plan_data = None

    for model_name in candidate_models:
        print(f"Attempting book architecture generation with model: '{model_name}'...")
        max_retries = 6

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
                    print(f"[Notice] Model '{model_name}' returned 404. Skipping...")
                    break
                wait_time = min(60, (2 ** attempt) + random.uniform(1, 4))
                print(f"[Notice] Retry attempt {attempt}/{max_retries} in {wait_time:.1f}s...")
                time.sleep(wait_time)

        if plan_data:
            break

    if not plan_data:
        raise RuntimeError("Failed to generate plan across candidate models.")

    with open(DAILY_PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2)

    history.append(plan_data["subject"])
    save_history(history)

    print("=====================================================")
    print(f"Selected Subject: '{plan_data['subject']}'")
    print(f"Category: {plan_data['category']} ({plan_data['target_age']})")
    print(f"Character DNA: {plan_data['character_dna']}")
    print(f"Total Scenes Generated: {len(plan_data['scenes'])}")
    print("=====================================================")

if __name__ == "__main__":
    generate_daily_plan()
