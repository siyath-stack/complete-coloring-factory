import os
import re
import json
import time
import math
import random
import requests
import base64
from io import BytesIO
from PIL import Image, ImageEnhance, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# CONFIGURATION & MODEL SETUP
# ---------------------------------------------------------------------------
ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")

COVER_MODEL = os.environ.get("COVER_MODEL", "@cf/bytedance/stable-diffusion-xl-lightning")
INTERIOR_MODEL = os.environ.get("INTERIOR_MODEL", "@cf/bytedance/stable-diffusion-xl-lightning")

PAGE_WIDTH = 2550
PAGE_HEIGHT = 3300

session = requests.Session()

# ---------------------------------------------------------------------------
# FONT & TEXT UTILITIES
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
    """Wraps and centers text using correct 4-tuple indexing (right-left for width, bottom-top for height)."""
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]  # right - left
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
        line_height = bbox[3] - bbox[1]  # bottom - top
        y += line_height + line_spacing
    return y

# ---------------------------------------------------------------------------
# ADAPTIVE LINE-ART CLEANER (Clamps grays to pure white, thickens outlines)
# ---------------------------------------------------------------------------
def clean_line_art_adaptive(gray_img):
    """
    Clamps faint grays, shadows, and mid-tones to pure white (#FFFFFF),
    and forces dark stroke pixels to deep solid black (#000000).
    """
    lut = []
    for i in range(256):
        if i >= 165:
            lut.append(255)
        elif i <= 110:
            lut.append(0)
        else:
            norm = (i - 110) / (165 - 110)
            lut.append(int(255 * (norm ** 1.5)))
    return gray_img.point(lut)

def fetch_cloudflare_image(prompt, model, max_retries=6):
    if not ACCOUNT_ID or not API_TOKEN:
        raise ValueError("Missing CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN.")

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
# PROCEDURAL ACTIVITY PAGES (0 Neurons Consumed)
# ---------------------------------------------------------------------------
def generate_procedural_maze_page(subject):
    img = create_blank_page()
    draw = ImageDraw.Draw(img)

    margin_x, margin_y = 140, 140
    draw.rounded_rectangle([margin_x, margin_y, PAGE_WIDTH - margin_x, PAGE_HEIGHT - margin_y], radius=40, outline="black", width=12)

    title_font = get_font(95)
    sub_font = get_font(52)
    draw.text((PAGE_WIDTH // 2, 320), "PUZZLE ADVENTURE: THE MAZE!", fill="black", font=title_font, anchor="mm")
    draw.text((PAGE_WIDTH // 2, 430), f"Help the baby {subject} find the bubble party!", fill="#444444", font=sub_font, anchor="mm")

    cols, rows = 8, 8
    cell_w, cell_h = 210, 210
    start_x = (PAGE_WIDTH - (cols * cell_w)) // 2
    start_y = 680

    draw.line([(start_x + cell_w, start_y), (start_x + cols * cell_w, start_y)], fill="black", width=14)
    draw.line([(start_x, start_y + rows * cell_h), (start_x + (cols - 1) * cell_w, start_y + rows * cell_h)], fill="black", width=14)
    draw.line([(start_x, start_y), (start_x, start_y + rows * cell_h)], fill="black", width=14)
    draw.line([(start_x + cols * cell_w, start_y), (start_x + cols * cell_w, start_y + rows * cell_h)], fill="black", width=14)

    random.seed(42)
    for r in range(rows):
        for c in range(cols):
            x = start_x + c * cell_w
            y = start_y + r * cell_h
            if random.random() > 0.45 and c < cols - 1 and r > 0:
                draw.line([(x + cell_w, y), (x + cell_w, y + cell_h)], fill="black", width=12)
            if random.random() > 0.50 and r < rows - 1 and c > 0:
                draw.line([(x, y + cell_h), (x + cell_w, y + cell_h)], fill="black", width=12)

    draw.text((start_x + cell_w // 2, start_y - 70), "START ★", fill="black", font=get_font(60), anchor="mm")
    draw.text((start_x + (cols - 1) * cell_w + cell_w // 2, start_y + rows * cell_h + 70), "FINISH 🎈", fill="black", font=get_font(60), anchor="mm")

    draw.text((PAGE_WIDTH // 2, PAGE_HEIGHT - 220), "Trace the path with your crayon, then color the decorations!", fill="#555555", font=get_font(48), anchor="mm")
    draw.text((PAGE_WIDTH // 2, PAGE_HEIGHT - 65), "- Activity Page 1 -", fill="#777777", font=get_font(44), anchor="mm")
    return img

def generate_procedural_dot_to_dot_page(subject):
    img = create_blank_page()
    draw = ImageDraw.Draw(img)

    margin_x, margin_y = 140, 140
    draw.rounded_rectangle([margin_x, margin_y, PAGE_WIDTH - margin_x, PAGE_HEIGHT - margin_y], radius=40, outline="black", width=12)

    title_font = get_font(95)
    sub_font = get_font(52)
    draw.text((PAGE_WIDTH // 2, 320), "CONNECT THE DOTS: 1 TO 20!", fill="black", font=title_font, anchor="mm")
    draw.text((PAGE_WIDTH // 2, 430), "Connect all the numbered dots in order to reveal the secret gift!", fill="#444444", font=sub_font, anchor="mm")

    center_x = PAGE_WIDTH // 2
    center_y = 1500
    points = []
    num_points = 20

    for i in range(num_points):
        angle = (2 * math.pi * i) / num_points - (math.pi / 2)
        radius = 700 if i % 2 == 0 else 380
        px = int(center_x + radius * math.cos(angle))
        py = int(center_y + radius * math.sin(angle))
        points.append((px, py))

    num_font = get_font(52)
    for i, (px, py) in enumerate(points, start=1):
        draw.ellipse([px - 16, py - 16, px + 16, py + 16], fill="black")
        text_offset_x = 40 if px >= center_x else -40
        text_offset_y = 40 if py >= center_y else -40
        draw.text((px + text_offset_x, py + text_offset_y), str(i), fill="black", font=num_font, anchor="mm")

    draw.ellipse([center_x - 80, center_y - 80, center_x + 80, center_y + 80], outline="black", width=10)
    draw.text((center_x, center_y), "★", fill="black", font=get_font(80), anchor="mm")

    draw.text((PAGE_WIDTH // 2, PAGE_HEIGHT - 220), "Connect from 1 to 20 without lifting your crayon!", fill="#555555", font=get_font(48), anchor="mm")
    draw.text((PAGE_WIDTH // 2, PAGE_HEIGHT - 65), "- Activity Page 2 -", fill="#777777", font=get_font(44), anchor="mm")
    return img

def generate_procedural_spot_differences_page(subject):
    img = create_blank_page()
    draw = ImageDraw.Draw(img)

    margin_x, margin_y = 140, 140
    draw.rounded_rectangle([margin_x, margin_y, PAGE_WIDTH - margin_x, PAGE_HEIGHT - margin_y], radius=40, outline="black", width=12)

    title_font = get_font(95)
    sub_font = get_font(52)
    draw.text((PAGE_WIDTH // 2, 320), "SPOT THE 4 DIFFERENCES!", fill="black", font=title_font, anchor="mm")
    draw.text((PAGE_WIDTH // 2, 430), "Look closely at Picture A and Picture B. Can you find all 4 changes?", fill="#444444", font=sub_font, anchor="mm")

    box_w, box_h = 1000, 1300
    y0 = 650
    x_left = 220
    x_right = PAGE_WIDTH - 220 - box_w

    for x_pos, label in [(x_left, "PICTURE A"), (x_right, "PICTURE B")]:
        draw.rounded_rectangle([x_pos, y0, x_pos + box_w, y0 + box_h], radius=30, outline="black", width=10)
        draw.text((x_pos + box_w // 2, y0 - 45), label, fill="black", font=get_font(55), anchor="mm")

        cx = x_pos + box_w // 2
        cy = y0 + box_h // 2
        draw.ellipse([cx - 200, cy - 180, cx + 200, cy + 220], outline="black", width=12)
        draw.ellipse([cx - 90, cy - 30, cx - 40, cy + 20], fill="black")
        draw.ellipse([cx + 40, cy - 30, cx + 90, cy + 20], fill="black")
        draw.arc([cx - 70, cy + 30, cx + 70, cy + 110], 0, 180, fill="black", width=10)
        draw.line([(x_pos + 40, y0 + box_h - 120), (x_pos + box_w - 40, y0 + box_h - 120)], fill="black", width=10)

    # 4 Differences added to Picture B
    draw.ellipse([x_right + 180, y0 + 180, x_right + 260, y0 + 260], outline="black", width=10)
    draw.ellipse([x_right + 220, y0 + 290, x_right + 280, y0 + 350], outline="black", width=10)
    draw.arc([x_right + box_w // 2 - 70, y0 + box_h // 2 + 10, x_right + box_w // 2 + 70, y0 + box_h // 2 + 110], 0, 180, fill="black", width=14)
    draw.text((x_right + box_w - 180, y0 + 200), "★", fill="black", font=get_font(80), anchor="mm")

    draw.text((PAGE_WIDTH // 2, PAGE_HEIGHT - 220), "Circle the 4 differences with your favorite bright marker!", fill="#555555", font=get_font(48), anchor="mm")
    draw.text((PAGE_WIDTH // 2, PAGE_HEIGHT - 65), "- Activity Page 3 -", fill="#777777", font=get_font(44), anchor="mm")
    return img

# ---------------------------------------------------------------------------
# COLORING PAGES & MONKEY.PDF SIMPLICITY GENERATION
# ---------------------------------------------------------------------------
def generate_cover_page(subject, category):
    print(f"Generating full-color cover for '{subject}'...")

    prompt = (
        f"A beautiful, vibrant children's book cover illustration of an adorable {subject}. "
        "Style: Monkey.pdf simple cartoon line art style, bright cheerful daylight colors, thick smooth black outlines. "
        "Large readable shapes, adorable smiling animal character centered in its natural environment. "
        "High key lighting, completely clean, strictly NO text, NO letters, NO words, NO logos."
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

    draw.rectangle([100, 120, PAGE_WIDTH - 100, 360], fill=(255, 255, 255), outline="black", width=10)
    draw.text((PAGE_WIDTH // 2, 200), "TODDLER COLORING BOOK", fill="black", font=title_font, anchor="mm")
    draw.text((PAGE_WIDTH // 2, 300), f"Simple Adventures in {category}", fill="#333333", font=sub_font, anchor="mm")

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
        "Thank you for downloading this simple toddler coloring book!\n\n"
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

    prompt = (
        f"A simple vector coloring book page for toddlers, exact style of Monkey.pdf. "
        f"Subject: {character_dna}. "
        f"Scene: {action}. Single central character centered in frame, wide open white coloring areas, "
        "ultra-thick smooth 6pt black outlines, heavy 2D vector line art, minimalist background with 1 simple element, solid pure white background. "
        "CRITICAL NEGATIVE CONSTRAINTS: NO shading, NO shadows, NO grayscale, NO gradients, NO fine details, NO fur hatching, NO wood grain, NO texture lines, NO intricate background clutter, NO human characters, NO dark sky, NO solid black fills, NO text, NO letters, NO signatures."
    )

    image_bytes = fetch_cloudflare_image(prompt, INTERIOR_MODEL)
    img = Image.open(BytesIO(image_bytes)).convert("L")

    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.8)
    img = clean_line_art_adaptive(img)

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

    draw.rounded_rectangle([border_margin_x, border_margin_y, PAGE_WIDTH - border_margin_x, PAGE_HEIGHT - border_margin_y], radius=40, outline="black", width=10)

    x_offset = border_margin_x + 20 + ((inner_w - new_width) // 2)
    y_offset = border_margin_y + 40 + ((inner_h - new_height) // 2)
    final_page.paste(img.convert("RGB"), (x_offset, y_offset))

    prompt_font = get_font(50)
    draw.text((PAGE_WIDTH // 2, PAGE_HEIGHT - border_margin_y - 100), micro_prompt, fill="#333333", font=prompt_font, anchor="mm")

    page_font = get_font(44)
    draw.text((PAGE_WIDTH // 2, PAGE_HEIGHT - 65), f"- {page_num} -", fill="#666666", font=page_font, anchor="mm")

    return final_page

def generate_certificate_page(subject):
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

    draw.line([(PAGE_WIDTH // 2 - 700, 1400), (PAGE_WIDTH // 2 + 700, 1400)], fill="black", width=6)
    draw.text((PAGE_WIDTH // 2, 1480), "Super Colorist", fill="#777777", font=get_font(45), anchor="mm")

    desc = f"For creatively completing all simple coloring adventures with the {subject}!"
    draw_wrapped_centered_text(draw, desc, PAGE_WIDTH // 2, 1780, body_font, fill="black", max_width=1750)

    draw.line([(350, 2450), (950, 2450)], fill="black", width=5)
    draw.text((650, 2510), "Date", fill="black", font=get_font(48), anchor="mm")

    draw.ellipse([PAGE_WIDTH // 2 - 120, 2270, PAGE_WIDTH // 2 + 120, 2510], outline="black", width=8)
    draw.text((PAGE_WIDTH // 2, 2390), "★", fill="black", font=get_font(95), anchor="mm")

    draw.line([(PAGE_WIDTH - 950, 2450), (PAGE_WIDTH - 350, 2450)], fill="black", width=5)
    draw.text((PAGE_WIDTH - 650, 2510), "Artist Signature", fill="black", font=get_font(48), anchor="mm")

    return img

def generate_retail_back_cover_with_thumbnails(subject, sample_pages):
    print("Generating retail showcase back cover with live interior thumbnails...")
    img = create_blank_page()
    draw = ImageDraw.Draw(img)

    draw.rectangle([100, 100, PAGE_WIDTH - 100, PAGE_HEIGHT - 100], outline="black", width=12)

    title_font = get_font(105)
    sub_font = get_font(55)
    draw.text((PAGE_WIDTH // 2, 380), "30 Simple Coloring Pages Inside!", fill="black", font=title_font, anchor="mm")
    draw.text((PAGE_WIDTH // 2, 500), f"Peek inside to see what you will color with the {subject}!", fill="#555555", font=sub_font, anchor="mm")

    thumb_w, thumb_h = 750, 970
    cols, rows = 2, 2
    spacing_x = 180
    spacing_y = 120
    start_x = (PAGE_WIDTH - (cols * thumb_w + spacing_x)) // 2
    start_y = 660

    for idx, sample_page in enumerate(sample_pages[:4]):
        c = idx % 2
        r = idx // 2
        x0 = start_x + c * (thumb_w + spacing_x)
        y0 = start_y + r * (thumb_h + spacing_y)

        draw.rounded_rectangle([x0 + 15, y0 + 15, x0 + thumb_w + 15, y0 + thumb_h + 15], radius=25, fill="#dddddd")
        thumb = sample_page.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        img.paste(thumb, (x0, y0))
        draw.rounded_rectangle([x0, y0, x0 + thumb_w, y0 + thumb_h], radius=25, outline="black", width=6)

    draw.text((PAGE_WIDTH // 2, 2900), "Perfect for crayons, colored pencils, and soft markers.", fill="#333333", font=get_font(52), anchor="mm")
    draw.text((PAGE_WIDTH // 2, 3010), "Proudly printed for young artists. Share your artwork with family!", fill="#777777", font=get_font(44), anchor="mm")

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
    category = plan.get("category", "Toddler Animal Adventures")
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
    sample_thumbnails = []

    # Insert 30 coloring sheets with procedural activity breaks at pages 8, 16, and 24
    for i, scene in enumerate(scenes[:30], start=1):
        if i == 8:
            pages.append(generate_procedural_maze_page(subject))
        elif i == 16:
            pages.append(generate_procedural_dot_to_dot_page(subject))
        elif i == 24:
            pages.append(generate_procedural_spot_differences_page(subject))

        page_img = generate_vector_interior_page(character_dna, scene, i)
        pages.append(page_img)

        # Collect sample thumbnails for back cover (Pages 3, 11, 19, 27)
        if i in [3, 11, 19, 27]:
            sample_thumbnails.append(page_img)

        time.sleep(2)

    pages.append(generate_certificate_page(subject))
    pages.append(generate_retail_back_cover_with_thumbnails(subject, sample_thumbnails))

    safe_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", subject.strip().lower())
    safe_slug = re.sub(r"_+", "_", safe_slug)
    filename = f"Digital_Coloring_Book_{safe_slug}.pdf"

    # Save complete multi-page PDF via primary PIL Image instance
    pages[0].save(
        filename, "PDF", resolution=300, save_all=True, append_images=pages[1:]
    )
    print("=====================================================")
    print(f"Successfully generated high-end book: {filename}")
    print(f"Total compiled pages: {len(pages)} (Front matter + 30 coloring sheets + 3 activities + certificate + back cover)")
    print("=====================================================")

if __name__ == "__main__":
    build_book()
