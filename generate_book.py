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
# HIGH-END STORY ACTIONS & SCENES (Monkey.pdf Style: Natural & Diverse)
# ---------------------------------------------------------------------------
HIGH_END_ACTIONS = [
    # Act 1: Morning & Playful Introductions (Pages 1-6)
    "waving hello with a cheerful joyful expression, character centered",
    "swinging happily from a gentle leafy tree branch with a spiral curled tail",
    "curiously smelling a large tropical blossom flower on a branch",
    "clapping paws and dancing happily with cute musical notes floating nearby",
    "happily sitting on a branch peeling a fresh banana or favorite sweet fruit snack",
    "peeking playfully from behind a friendly broad jungle palm leaf",

    # Act 2: Family, Companions & Nature Exploration (Pages 7-14)
    "riding happily on its mother's back holding on with tiny paws",
    "perched side by side on a sturdy branch chatting with a friendly smiling tropical parrot",
    "gently reaching out a paw to let a cheerful smiling cartoon butterfly land",
    "drinking fresh juice with a fun striped straw from a round coconut cup",
    "splashing playfully with toes in a calm jungle puddle under warm sunlight",
    "wearing a wide-brimmed safari sun hat decorated with a small flower",
    "balancing playfully on one foot along a fallen mossy tree log",
    "playing peekaboo behind a cluster of hanging jungle vines",

    # Act 3: Playful Feats & Outdoor Adventures (Pages 15-22)
    "hanging upside down by feet and tail with a big playful grin",
    "juggling three smooth round jungle fruits with happy bright cartoon eyes",
    "flying a colorful diamond-shaped kite high against puffy cartoon clouds",
    "proudly holding up a shiny star-shaped wooden badge like a junior explorer",
    "sitting inside a hollow tree trunk cozy nook waving through a knot hole",
    "making funny goofy faces in the reflection of a calm water pool",
    "curiously inspecting a friendly little caterpillar creeping along a leaf",
    "happily rolling a giant shiny polished river pebble like a ball",

    # Act 4: Joyful Games & Celebrations (Pages 23-28)
    "wearing a tiny party party hat surrounded by floating festive confetti",
    "building a neat stack of rounded river stones with focused cute eyes",
    "giggling while blowing giant round soap bubbles floating into the sky",
    "holding a vibrant balloon cluster tied to a tiny wrist string",
    "happily sharing a cluster of sweet wild berries with a little songbird",
    "taking a cheerful victory bow with arms outstretched in joy",

    # Act 5: Twilight & Bedtime (Pages 29-30)
    "sitting peacefully on a high branch gazing at a smiling crescent moon and twinkling stars",
    "curled up fast asleep on a cozy hammock of jungle leaves hugging a tiny leaf pillow"
]

# ---------------------------------------------------------------------------
# FONT HELPER WITH SAFE FALLBACKS
# ---------------------------------------------------------------------------
def get_font(size):
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
# DAILY SCHEDULE & SUBJECT EXTRACTION
# ---------------------------------------------------------------------------
def extract_clean_subject(raw_theme):
    """
    Strips 'glued' action phrases (like 'eating watermelon slices', 'building a tower')
    so the character remains pure across all 30 unique pages.
    """
    text = raw_theme.strip().lower()
    text = re.sub(r'\b(eating|building|driving|riding|flying|holding|cooking|playing|with)\b.*$', '', text)
    text = text.strip()
    if not text:
        text = "cute friendly animal character"
    return text

def get_daily_configuration(csv_path="themes.csv"):
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
                todays_theme = {"id": 1, "theme": "cute monkey", "category": "Kids Animals"}
    else:
        todays_theme = {"id": 1, "theme": "cute monkey", "category": "Kids Animals"}

    clean_subject = extract_clean_subject(todays_theme["theme"])

    seed_value = int(f"{year}{day_of_year}")
    rng = random.Random(seed_value)
    todays_30_actions = rng.sample(HIGH_END_ACTIONS, min(30, len(HIGH_END_ACTIONS)))

    return todays_theme, clean_subject, todays_30_actions

# ---------------------------------------------------------------------------
# CLOUDFLARE AI API CALLS WITH RATE-LIMIT BACKOFF
# ---------------------------------------------------------------------------
def fetch_cloudflare_image(prompt, max_retries=6):
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
# HIGH-END PAGE GENERATION FUNCTIONS
# ---------------------------------------------------------------------------
def generate_cover_page(clean_subject, category):
    print(f"Generating premium vector-style cover for '{clean_subject}'...")

    prompt = (
        f"A premium, professional children's book cover illustration of a {clean_subject} swinging from a tropical leafy vine. "
        "Style: High-end storybook art, vibrant joyful colors, adorable cartoon styling with bright friendly eyes. "
        "Clean composition, large readable shapes, cheerful daylight setting. "
        "Strictly NO text, NO letters, NO words, NO logos."
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
    draw.text((PAGE_WIDTH // 2, 300), f"30 Premium Adventures in {category}", fill="#333333", font=sub_font, anchor="mm")

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

def generate_high_end_interior_page(clean_subject, action_scene, page_num):
    print(f"Generating page {page_num}/30: {action_scene[:45]}...")

    # Monkey.pdf Benchmark Prompt: Vector line art, large open spaces, pure white background
    prompt = (
        f"A premium children's coloring book page featuring a {clean_subject}. "
        f"Scene: {action_scene}. "
        "Style: Professional children's book vector line art illustration, Monkey Pen style, Disney storybook character design. "
        "Clean, continuous, bold black contour outlines on a solid pure white background. "
        "Large, wide, open coloring spaces perfectly suited for young children coloring with crayons. "
        "Cute expressive cartoon character with large friendly sparkling eyes. "
        "Balanced minimal background with simple outline elements (like simple vine, flower, branch, or cloud). "
        "ABSOLUTELY NO COLOR, NO GRAYSCALE, NO SHADING, NO HALFTONES, NO HATCHING, NO TEXTURES, NO GRITTY DETAIL. "
        "ABSOLUTELY NO TEXT, NO LETTERS, NO NUMBERS, NO CAPTIONS, NO WATERMARKS, NO ARTIST SIGNATURES."
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
    theme_data, clean_subject, daily_actions = get_daily_configuration()
    category = theme_data.get("category", "Kids Animals")
    print(f"=====================================================")
    print(f"Starting Premium Production for Character: '{clean_subject}'")
    print(f"Original Theme Entry: '{theme_data['theme']}' | Category: {category}")
    print(f"=====================================================")

    pages = [
        generate_cover_page(clean_subject, category),
        generate_ownership_page(),
        generate_terms_page(),
        generate_color_test_page()
    ]

    time.sleep(4)

    for i, action in enumerate(daily_actions, start=1):
        page_img = generate_high_end_interior_page(clean_subject, action, i)
        pages.append(page_img)
        time.sleep(3)

    safe_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", clean_subject.strip().lower())
    safe_slug = re.sub(r"_+", "_", safe_slug)
        safe_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", clean_subject.strip().lower())
    safe_slug = re.sub(r"_+", "_", safe_slug)
    filename = f"Digital_Coloring_Book_{safe_slug}.pdf"

    # Fix: Call .save() on pages[0], not pages
    pages[0].save(
        filename, "PDF", resolution=300, save_all=True, append_images=pages[1:]
    )
    print(f"=====================================================")
    print(f"Successfully generated high-end book: {filename}")
    print(f"Total pages compiled: {len(pages)} (4 front matter + 30 coloring pages)")
    print(f"=====================================================")

    print(f"=====================================================")
    print(f"Successfully generated high-end book: {filename}")
    print(f"Total pages compiled: {len(pages)} (4 front matter + 30 coloring pages)")
    print(f"=====================================================")

if __name__ == "__main__":
    build_book()
