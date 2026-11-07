import os
import csv
import re
import time
import random
import requests
import base64
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageEnhance, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# CONFIGURATION & API SETUP
# ---------------------------------------------------------------------------
ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")
MODEL = "@cf/black-forest-labs/flux-1-schnell"
API_BASE_URL = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/{MODEL}"

# Standard 8.5 x 11 inches at 300 DPI
PAGE_WIDTH = 2550
PAGE_HEIGHT = 3300

session = requests.Session()

# ---------------------------------------------------------------------------
# 1,000 UNIQUE MODIFIERS ENGINE (50 Actions x 20 Environments)
# ---------------------------------------------------------------------------
ACTIONS = [
    "happily eating breakfast", "reading a colorful storybook", "flying a high diamond kite",
    "riding a wooden skateboard", "baking cupcakes with a chef hat", "painting a rainbow on a canvas",
    "planting flower seeds with a trowel", "looking through a brass telescope", "dancing under the rain with an umbrella",
    "building a tall sandcastle with seashells", "sleeping peacefully on a fluffy cloud", "splashing in muddy puddles with rainboots",
    "riding a small bicycle with a basket", "fishing on a wooden dock", "blowing giant iridescent soap bubbles",
    "playing a wooden acoustic guitar", "wearing a shiny superhero cape", "hiking up a gentle mountain trail",
    "having a cozy tea party with plush toys", "catching fluttering yellow butterflies with a net",
    "rowing a little wooden boat on a lake", "gliding on ice skates across a pond", "juggling three round apples",
    "climbing a sturdy wooden ladder into a treehouse", "peeking curiously from behind a thick oak tree",
    "balancing carefully on a wooden balance beam", "building a puzzle on a braided rug", "wearing a cozy knitted winter scarf",
    "carrying a wicker basket full of apples", "camping inside a canvas tent with a lantern", "playing hide and seek behind a hedge",
    "swinging high on a wooden tire swing", "eating a large slice of watermelon", "licking a double-scoop ice cream cone",
    "drawing with colorful chalk on the sidewalk", "racing with a small toy wooden sailboat in a brook",
    "making a snow angel in deep fresh snow", "picking ripe red strawberries in a patch", "sipping hot cocoa from a mug with marshmallows",
    "listening to birds singing on a branch", "taking a photo with a vintage toy camera", "wearing a folded paper pirate hat",
    "wrapping a gift with a big satin bow", "watering potted sunflowers with a watering can", "stacking wooden alphabet blocks",
    "sliding down a gentle playground slide", "wearing snorkel goggles in shallow water", "flying a tiny toy propeller plane",
    "skipping flat stones across a river", "whistling a cheerful tune along a footpath"
]

ENVIRONMENTS = [
    "in a lush sunny meadow filled with daisies", "under a starry night sky with a crescent moon",
    "inside a cozy rustic kitchen with warm pies", "on an enchanted woodland trail surrounded by mushrooms",
    "at a sunny sandy beach with gentle rolling waves", "in a vibrant flower garden buzzing with friendly bumblebees",
    "on the front porch of a charming cottage", "in a lively playground with swings and sandpits",
    "near a crystal-clear forest stream with smooth pebbles", "at a joyful village carnival with colorful balloons",
    "inside a secret treehouse overlooking rolling green hills", "in a peaceful snowy pine forest with gentle snowflakes",
    "at an apple orchard with ripe fruit on branches", "inside a whimsical library with tall wooden bookshelves",
    "in a golden wheat field under puffy white clouds", "at a community duck pond with swimming ducklings",
    "beside a mossy stone wall covered in ivy", "in a blooming botanical greenhouse filled with tropical ferns",
    "at a backyard campsite under a canopy of oak trees", "on a breezy hilltop overlooking a peaceful valley"
]

ALL_1000_MODIFIERS = [f"{act} {env}" for act in ACTIONS for env in ENVIRONMENTS]

# ---------------------------------------------------------------------------
# FONT HELPER WITH SAFE FALLBACKS
# ---------------------------------------------------------------------------
def get_font(size):
    """Safely loads a font with system and fallback detection."""
    system_font_paths = [
        "Roboto-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Regular.ttf",
        "arial.ttf"
    ]
    for path in system_font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    try:
        url = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf"
        r = session.get(url, timeout=5)
        if r.status_code == 200:
            with open("Roboto-Regular.ttf", "wb") as f:
                f.write(r.content)
            return ImageFont.truetype("Roboto-Regular.ttf", size)
    except Exception:
        pass

    return ImageFont.load_default()

# ---------------------------------------------------------------------------
# DAILY SCHEDULE & RANDOMIZATION LOGIC
# ---------------------------------------------------------------------------
def get_daily_configuration(csv_path="themes.csv"):
    """
    Selects today's theme and randomly samples 30 unique modifiers from the
    1,000 pool using the date as a deterministic seed.
    """
    now = datetime.now()
    day_of_year = now.timetuple().tm_yday
    year = now.year

    if os.path.exists(csv_path):
        with open(csv_path, mode="r", encoding="utf-8") as file:
            reader = list(csv.DictReader(file))
            if reader:
                theme_index = (day_of_year - 1) % len(reader)
                todays_theme = reader[theme_index]
            else:
                todays_theme = {"id": 1, "theme": "cute animal adventure", "category": "Kids Animals"}
    else:
        todays_theme = {"id": 1, "theme": "cute animal adventure", "category": "Kids Animals"}

    seed_value = int(f"{year}{day_of_year}")
    rng = random.Random(seed_value)

    todays_30_modifiers = rng.sample(ALL_1000_MODIFIERS, 30)

    return todays_theme, todays_30_modifiers

# ---------------------------------------------------------------------------
# CLOUDFLARE AI API CALLS WITH RETRY & RATE-LIMIT BACKOFF
# ---------------------------------------------------------------------------
def fetch_cloudflare_image(prompt, max_retries=6):
    """Fetches text-to-image output from Cloudflare AI with robust 429 backoff handling."""
    if not ACCOUNT_ID or not API_TOKEN:
        raise ValueError("Missing CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN in environment variables.")

    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    payload = {"prompt": prompt}

    for attempt in range(max_retries):
        try:
            response = session.post(API_BASE_URL, headers=headers, json=payload, timeout=90)

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_time = int(retry_after) if retry_after and retry_after.isdigit() else (12 * (attempt + 1))
                print(f"[Rate Limit 429] Waiting {wait_time}s before retrying (attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
                continue

            response.raise_for_status()

            try:
                json_data = response.json()
                if "result" in json_data and "image" in json_data["result"]:
                    return base64.b64decode(json_data["result"]["image"])
            except ValueError:
                pass
            return response.content

        except requests.RequestException as e:
            if attempt == max_retries - 1:
                raise e
            wait_time = 6 * (attempt + 1)
            print(f"[Request Error] {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)

    raise RuntimeError(f"Failed to fetch image after {max_retries} attempts due to rate limiting.")

def create_blank_page():
    return Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), "white")

# ---------------------------------------------------------------------------
# PAGE GENERATION FUNCTIONS
# ---------------------------------------------------------------------------
def generate_cover_page(theme_data):
    theme = theme_data["theme"]
    category = theme_data.get("category", "Kids")
    print(f"Generating full-color cover for theme: '{theme}'...")

    prompt = (
        f"A beautiful, vibrant, professional full-color children's book cover illustration "
        f"featuring {theme}. Vibrant joyful colors, adorable cartoon styling, clean composition. "
        "High quality 2D children's book artwork. Absolutely no text, no letters, no title."
    )
    image_bytes = fetch_cloudflare_image(prompt)
    img = Image.open(BytesIO(image_bytes)).convert("RGB")

    img_ratio = img.width / img.height
    page_ratio = PAGE_WIDTH / PAGE_HEIGHT

    if img_ratio > page_ratio:
        new_width = PAGE_WIDTH
        new_height = int(PAGE_WIDTH / img_ratio)
    else:
        new_height = PAGE_HEIGHT
        new_width = int(PAGE_HEIGHT * img_ratio)

    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    final_page = create_blank_page()
    x_offset = (PAGE_WIDTH - new_width) // 2
    y_offset = (PAGE_HEIGHT - new_height) // 2
    final_page.paste(img, (x_offset, y_offset))

    draw = ImageDraw.Draw(final_page)
    title_font = get_font(130)
    sub_font = get_font(60)

    draw.rectangle([100, 120, PAGE_WIDTH - 100, 360], fill=(255, 255, 255), outline="black", width=8)
    draw.text((PAGE_WIDTH // 2, 200), "COLORING BOOK", fill="black", font=title_font, anchor="mm")
    draw.text((PAGE_WIDTH // 2, 300), f"30 Fun Adventures in {category}", fill="#333333", font=sub_font, anchor="mm")

    return final_page

def generate_ownership_page():
    img = create_blank_page()
    draw = ImageDraw.Draw(img)
    title_font = get_font(120)
    sub_font = get_font(70)

    draw.rectangle([120, 120, PAGE_WIDTH - 120, PAGE_HEIGHT - 120], outline="black", width=12)
    draw.rectangle([150, 150, PAGE_WIDTH - 150, PAGE_HEIGHT - 150], outline="black", width=4)

    draw.text((PAGE_WIDTH // 2, 800), "This Coloring Book", fill="black", font=sub_font, anchor="mm")
    draw.text((PAGE_WIDTH // 2, 980), "BELONGS TO:", fill="black", font=title_font, anchor="mm")

    box_x0, box_y0 = PAGE_WIDTH // 2 - 800, 1300
    box_x1, box_y1 = PAGE_WIDTH // 2 + 800, 1600
    draw.rectangle([box_x0, box_y0, box_x1, box_y1], outline="black", width=10)
    draw.line([(box_x0 + 100, 1530), (box_x1 - 100, 1530)], fill="black", width=6)

    for x in [PAGE_WIDTH // 4, PAGE_WIDTH // 2, (PAGE_WIDTH // 4) * 3]:
        draw.ellipse([x - 70, 2400, x + 70, 2540], outline="black", width=8)

    draw.text((PAGE_WIDTH // 2, 2800), "Color your own adventure!", fill="#444444", font=sub_font, anchor="mm")
    return img

def generate_terms_page():
    img = create_blank_page()
    draw = ImageDraw.Draw(img)
    title_font = get_font(100)
    body_font = get_font(55)

    draw.text((PAGE_WIDTH // 2, 1000), "Terms of Use", fill="black", font=title_font, anchor="mm")
    terms_text = (
        "Thank you for downloading this coloring book!\n\n"
        "This digital file is intended strictly for personal,\n"
        "classroom, or non-commercial home use.\n\n"
        "Please do not resell, redistribute, or host these files\n"
        "publicly online. All illustrations are proprietary."
    )
    draw.multiline_text((PAGE_WIDTH // 2, 1500), terms_text, fill="#333333", font=body_font, anchor="mm", align="center", spacing=25)
    return img

def generate_color_test_page():
    img = create_blank_page()
    draw = ImageDraw.Draw(img)
    title_font = get_font(110)
    sub_font = get_font(60)

    draw.text((PAGE_WIDTH // 2, 450), "Color & Swatch Test Page", fill="black", font=title_font, anchor="mm")
    draw.text((PAGE_WIDTH // 2, 600), "Test your crayons, markers, and colored pencils below!", fill="#444444", font=sub_font, anchor="mm")

    cols, rows = 3, 4
    box_w, box_h = 550, 400
    start_x = (PAGE_WIDTH - (cols * box_w + (cols - 1) * 150)) // 2
    start_y = 850

    for r in range(rows):
        for c in range(cols):
            x0 = start_x + c * (box_w + 150)
            y0 = start_y + r * (box_h + 120)
            x1, y1 = x0 + box_w, y0 + box_h
            draw.rectangle([x0, y0, x1, y1], outline="black", width=8)
            draw.text((x0 + 20, y1 + 35), f"Color #{r * cols + c + 1}", fill="black", font=get_font(40))

    return img

def generate_interior_page(theme, modifier, page_num):
    print(f"Generating page {page_num}/30: {modifier[:40]}...")

    prompt = (
        f"Children's coloring book line art page of {theme}, {modifier}. "
        "Full body shot, centered in frame, zoomed out with generous borders. "
        "Targeted for young children ages 3-8: ultra-thick, bold, clean black outlines on a pure solid white background. "
        "Strictly black and white line art only. No colors, no shading, no gradients, no grey wash, no halftones, no crosshatching. "
        "ABSOLUTELY NO TEXT, NO LETTERS, NO NUMBERS, NO CAPTIONS, NO WATERMARKS, AND NO ARTIST SIGNATURES."
    )

    image_bytes = fetch_cloudflare_image(prompt)
    img = Image.open(BytesIO(image_bytes)).convert("L")

    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.2)

    inner_width, inner_height = (PAGE_WIDTH - 300, PAGE_HEIGHT - 350)
    img_ratio = img.width / img.height
    inner_ratio = inner_width / inner_height

    if img_ratio > inner_ratio:
        new_width = inner_width
        new_height = int(inner_width / img_ratio)
    else:
        new_height = inner_height
        new_width = int(inner_height * img_ratio)

    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    final_page = create_blank_page()
    x_offset = 150 + ((inner_width - new_width) // 2)
    y_offset = 150 + ((inner_height - new_height) // 2)
    final_page.paste(img.convert("RGB"), (x_offset, y_offset))

    draw = ImageDraw.Draw(final_page)
    draw.text((PAGE_WIDTH // 2, PAGE_HEIGHT - 120), f"- {page_num} -", fill="#555555", font=get_font(45), anchor="mm")

    return final_page

# ---------------------------------------------------------------------------
# MAIN COMPILER
# ---------------------------------------------------------------------------
def build_book():
    theme_data, daily_modifiers = get_daily_configuration()
    theme = theme_data["theme"]
    print(f"=====================================================")
    print(f"Starting Daily Production for: {theme}")
    print(f"Category: {theme_data.get('category', 'Kids')}")
    print(f"=====================================================")

    pages = [
        generate_cover_page(theme_data),
        generate_ownership_page(),
        generate_terms_page(),
        generate_color_test_page()
    ]
    
    time.sleep(4)

    for i, modifier in enumerate(daily_modifiers, start=1):
        page_img = generate_interior_page(theme, modifier, i)
        pages.append(page_img)
        time.sleep(3)

    safe_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", theme.strip().lower())
    safe_slug = re.sub(r"_+", "_", safe_slug)
    filename = f"Digital_Coloring_Book_{safe_slug}.pdf"

    pages[0].save(
    filename,
    "PDF",
    resolution=300,
    save_all=True,
    append_images=pages[1:],
)
    print(f"=====================================================")
    print(f"Successfully generated: {filename}")
    print(f"Total pages compiled: {len(pages)} (4 front matter + 30 coloring pages)")
    print(f"=====================================================")

if __name__ == "__main__":
    build_book()
