import os
import re
import json
import time
import requests
import base64
from io import BytesIO
from PIL import Image, ImageEnhance, ImageDraw, ImageFont, ImageFilter

# ---------------------------------------------------------------------------
# CONFIGURATION & MODEL SETUP
# ---------------------------------------------------------------------------
ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")

# By default, SDXL-Lightning is used for both cover and interior to comfortably
# fit all 35 pages within the 10,000 daily free neurons without 429 lockouts.
# If you have Cloudflare Workers Paid ($5/mo), set COVER_MODEL to flux-1-schnell.
COVER_MODEL = os.environ.get("COVER_MODEL", "@cf/bytedance/stable-diffusion-xl-lightning")
INTERIOR_MODEL = os.environ.get("INTERIOR_MODEL", "@cf/bytedance/stable-diffusion-xl-lightning")

# Standard 8.5 x 11 inches at 300 DPI
PAGE_WIDTH = 2550
PAGE_HEIGHT = 3300

session = requests.Session()

# ---------------------------------------------------------------------------
# FONT & TEXT UTILITIES (Fixes IndexError on bbox)
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

def draw_wrapped_centered_text(draw, text, center_x, start_y, font, fill="black", max_width=1800, line_spacing=18):
    """Accurately wraps and centers text to prevent border collisions."""
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        # textbbox returns (left, top, right, bottom)
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]

    if current_line:
        lines.append(" ".join(current_line))

    y = start_y
    for line in lines:
        draw.text((center_x, y), line, fill=fill, font=font, anchor="mm")
        bbox = draw.textbbox((0, 0), line, font=font)
        line_height = bbox[3] - bbox[1]
        y += line_height + line_spacing
    return y

# ---------------------------------------------------------------------------
# CLOUDFLARE AI API CALLS WITH BACKOFF
# ---------------------------------------------------------------------------
def fetch_cloudflare_image(prompt, model, max_retries=6):
    if not ACCOUNT_ID or not API_TOKEN:
        raise ValueError("Missing CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN in environment variables.")

    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/{model}"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    payload = {"prompt": prompt}

    for attempt in range(max_retries):
        try:
            response = session.post(url, headers=headers, json=payload, timeout=90)

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

    raise RuntimeError(f"Failed to fetch image after {max_retries} attempts.")

def create_blank_page():
    return Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), "white")

# ---------------------------------------------------------------------------
# HIGH-END PAGE GENERATION FUNCTIONS
# ---------------------------------------------------------------------------
def generate_cover_page(subject, category):
    print(f"Generating full-color cover for '{subject}'...")

    prompt = (
        f"A beautiful, vibrant children's book cover illustration of an adorable {subject}. "
        "Style: High-end Disney storybook 2D cartoon art, bright sunny colors, cheerful atmosphere. "
        "Large readable shapes, adorable smiling character centered in a lush colorful natural setting. "
        "Completely clean, strictly NO text, NO letters, NO words, NO logos."
    )
    image_bytes = fetch_cloudflare_image(prompt, COVER_MODEL)
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

def generate_vector_interior_page(character_dna, scene_data, page_num):
    action = scene_data["action"]
    micro_prompt = scene_data["micro_prompt"]
    print(f"Generating page {page_num}/30: {action[:42]}...")

    # Vector line-art benchmark prompt with negative constraints against sketchy fur
    prompt = (
        f"A premium children's coloring book vector line art page. "
        f"Character: {character_dna}. "
        f"Scene: {action}. Grounded environment with a clean continuous bottom horizon line. "
        "Style: Professional Monkey Pen storybook vector illustration, clean bold continuous black contours, "
        "smooth uniform 5pt outline strokes on a pure solid white background. "
        "Large wide open spaces designed specifically for kids coloring with crayons. "
        "CRITICAL NEGATIVE CONSTRAINTS: NO fur textures, NO hair lines, NO sketchy strokes, NO pencil grain, "
        "NO shading, NO grayscale, NO crosshatching, NO stippling, NO floating characters, "
        "NO text, NO letters, NO numbers, NO watermarks, NO signatures."
    )

    image_bytes = fetch_cloudflare_image(prompt, INTERIOR_MODEL)
    img = Image.open(BytesIO(image_bytes)).convert("L")

    # High-contrast sharpening + binary threshold filter (cleans away fuzzy shading)
    img = img.filter(ImageFilter.SHARPEN)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(3.0)
    img = img.point(lambda x: 255 if x > 145 else 0, "1")

    border_margin_x = 140
    border_margin_y = 140
    inner_w = PAGE_WIDTH - (2 * border_margin_x) - 40
    inner_h = PAGE_HEIGHT - (2 * border_margin_y) - 260

    img_ratio = img.width / img.height
    target_ratio = inner_w / inner_h

    if img_ratio > target_ratio:
        new_width = inner_w
        new_height = int(inner_w / img_ratio)
    else:
        new_height = inner_h
        new_width = int(inner_h * img_ratio)

    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    final_page = create_blank_page()
    draw = ImageDraw.Draw(final_page)

    # Rounded outer page frame
    draw.rounded_rectangle(
        [border_margin_x, border_margin_y, PAGE_WIDTH - border_margin_x, PAGE_HEIGHT - border_margin_y],
        radius=40,
        outline="black",
        width=8
    )

    # Paste illustration inside frame
    x_offset = border_margin_x + 20 + ((inner_w - new_width) // 2)
    y_offset = border_margin_y + 40 + ((inner_h - new_height) // 2)
    final_page.paste(img.convert("RGB"), (x_offset, y_offset))

    # Activity prompt at bottom of framed box
    prompt_font = get_font(50)
    draw.text(
        (PAGE_WIDTH // 2, PAGE_HEIGHT - border_margin_y - 100),
        micro_prompt,
        fill="#333333",
        font=prompt_font,
        anchor="mm"
    )

    # Centered page number
    page_font = get_font(44)
    draw.text(
        (PAGE_WIDTH // 2, PAGE_HEIGHT - 65),
        f"- {page_num} -",
        fill="#666666",
        font=page_font,
        anchor="mm"
    )

    return final_page

def generate_certificate_page(subject):
    """Generates a polished Certificate of Completion with wrapped text."""
    img = create_blank_page()
    draw = ImageDraw.Draw(img)

    draw.rectangle([140, 140, PAGE_WIDTH - 140, PAGE_HEIGHT - 140], outline="black", width=16)
    draw.rectangle([180, 180, PAGE_WIDTH - 180, PAGE_HEIGHT - 180], outline="black", width=4)

    title_font = get_font(135)
    sub_font = get_font(70)
    body_font = get_font(55)

    draw.text((PAGE_WIDTH // 2, 600), "CERTIFICATE", fill="black", font=title_font, anchor="mm")
    draw.text((PAGE_WIDTH // 2, 770), "OF COMPLETION", fill="black", font=sub_font, anchor="mm")

    draw.text((PAGE_WIDTH // 2, 1120), "This certificate is proudly awarded to:", fill="#444444", font=body_font, anchor="mm")

    # Name underline
    draw.line([(PAGE_WIDTH // 2 - 700, 1400), (PAGE_WIDTH // 2 + 700, 1400)], fill="black", width=6)
    draw.text((PAGE_WIDTH // 2, 1480), "Super Colorist", fill="#777777", font=get_font(45), anchor="mm")

    # Wrapped description text prevents horizontal border overflow
    desc = f"For creatively completing all 30 coloring adventures with the {subject}!"
    draw_wrapped_centered_text(draw, desc, PAGE_WIDTH // 2, 1780, body_font, fill="black", max_width=1750)

    # Signature and date lines
    draw.line([(350, 2450), (950, 2450)], fill="black", width=5)
    draw.text((650, 2510), "Date", fill="black", font=get_font(48), anchor="mm")

    draw.ellipse([PAGE_WIDTH // 2 - 120, 2270, PAGE_WIDTH // 2 + 120, 2510], outline="black", width=8)
    draw.text((PAGE_WIDTH // 2, 2390), "★", fill="black", font=get_font(95), anchor="mm")

    draw.line([(PAGE_WIDTH - 950, 2450), (PAGE_WIDTH - 350, 2450)], fill="black", width=5)
    draw.text((PAGE_WIDTH - 650, 2510), "Artist Signature", fill="black", font=get_font(48), anchor="mm")

    return img

def generate_promotional_back_cover(subject):
    """MonkeyPen-style promotional back cover showcasing upcoming books."""
    img = create_blank_page()
    draw = ImageDraw.Draw(img)

    draw.rectangle([100, 100, PAGE_WIDTH - 100, PAGE_HEIGHT - 100], outline="black", width=12)

    title_font = get_font(110)
    sub_font = get_font(60)
    body_font = get_font(48)

    draw.text((PAGE_WIDTH // 2, 400), "Fuel Your Child's Imagination!", fill="black", font=title_font, anchor="mm")
    draw.text((PAGE_WIDTH // 2, 540), "More Free Adventures & Printable Books Coming Daily", fill="#555555", font=sub_font, anchor="mm")

    tiles = [
        "Kids Safari Animals",
        "Speed & Race Cars",
        "Fantasy Unicorns",
        "Ocean Explorers"
    ]
    cols, rows = 2, 2
    box_w, box_h = 850, 700
    start_x = (PAGE_WIDTH - (cols * box_w + 150)) // 2
    start_y = 800

    for idx, name in enumerate(tiles):
        c = idx % 2
        r = idx // 2
        x0 = start_x + c * (box_w + 150)
        y0 = start_y + r * (box_h + 150)
        x1, y1 = x0 + box_w, y0 + box_h
        draw.rounded_rectangle([x0, y0, x1, y1], radius=30, outline="black", width=8)
        draw.text(((x0 + x1) // 2, (y0 + y1) // 2 - 30), name, fill="black", font=get_font(58), anchor="mm")
        draw.text(((x0 + x1) // 2, (y0 + y1) // 2 + 50), "Coloring Adventure", fill="#666666", font=get_font(40), anchor="mm")

    draw.text((PAGE_WIDTH // 2, 2750), "Share your completed artwork with family & friends!", fill="#333333", font=body_font, anchor="mm")
    draw.text((PAGE_WIDTH // 2, 2870), "Printed on demand for young creative minds.", fill="#777777", font=get_font(42), anchor="mm")

    return img

# ---------------------------------------------------------------------------
# MAIN COMPILER
# ---------------------------------------------------------------------------
def build_book():
    plan_file = "daily_book_plan.json"
    if not os.path.exists(plan_file):
        raise FileNotFoundError(f"Missing '{plan_file}'. Run 'python research_trend.py' first.")

    with open(plan_file, "r", encoding="utf-8") as f:
        plan = json.load(f)

    subject = plan["subject"]
    category = plan.get("category", "Trending Kids Characters")
    character_dna = plan["character_dna"]
    scenes = plan["scenes"]

    print("=====================================================")
    print(f"Starting High-End Book Production: '{subject}'")
    print(f"Total Unique Habitat Scenes: {len(scenes)}")
    print("=====================================================")

    pages = [
        generate_cover_page(subject, category),
        generate_ownership_page(),
        generate_terms_page(),
        generate_color_test_page()
    ]

    time.sleep(3)

    for i, scene in enumerate(scenes[:30], start=1):
        page_img = generate_vector_interior_page(character_dna, scene, i)
        pages.append(page_img)
        time.sleep(2)

    pages.append(generate_certificate_page(subject))
    pages.append(generate_promotional_back_cover(subject))

    safe_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", subject.strip().lower())
    safe_slug = re.sub(r"_+", "_", safe_slug)
    filename = f"Digital_Coloring_Book_{safe_slug}.pdf"

    # Multi-page PDF compilation called on the first image object
    pages[0].save(
        filename, "PDF", resolution=300, save_all=True, append_images=pages[1:]
    )
    print("=====================================================")
    print(f"Successfully generated high-end book: {filename}")
    print(f"Total compiled pages: {len(pages)} (4 front matter + 30 coloring sheets + 1 certificate + 1 back cover)")
    print("=====================================================")

if __name__ == "__main__":
    build_book()
