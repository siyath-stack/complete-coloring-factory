import os
import csv
import requests
import urllib.request
import base64
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageEnhance, ImageDraw, ImageFont, ImageFilter

ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")
MODEL = "@cf/black-forest-labs/flux-1-schnell"
API_BASE_URL = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/{MODEL}"

# Standard 8.5x11 inches at 300 DPI
PAGE_WIDTH = 2550
PAGE_HEIGHT = 3300

def download_font():
    font_path = "Roboto-Regular.ttf"
    if not os.path.exists(font_path):
        url = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf"
        urllib.request.urlretrieve(url, font_path)
    return font_path

def get_todays_theme():
    day_of_year = datetime.now().timetuple().tm_yday
    with open('themes.csv', mode='r', encoding='utf-8') as file:
        reader = list(csv.DictReader(file))
        index = (day_of_year - 1) % len(reader)
        return reader[index]['theme']

def fetch_cloudflare_image(prompt):
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    response = requests.post(API_BASE_URL, headers=headers, json={"prompt": prompt})
    response.raise_for_status()
    
    # Cloudflare returns JSON containing a Base64 string for text-to-image models
    try:
        json_data = response.json()
        if "result" in json_data and "image" in json_data["result"]:
            image_b64 = json_data["result"]["image"]
            return base64.b64decode(image_b64)
    except ValueError:
        pass # If it's not JSON, fallback to raw content below
        
    return response.content

def create_blank_page():
    return Image.new('RGB', (PAGE_WIDTH, PAGE_HEIGHT), 'white')

def generate_cover_page(theme):
    print("Generating full-color cover...")
    prompt = (
        f"A beautiful, vibrant, full-color cover illustration for a children's coloring book "
        f"about a {theme}. Cute, whimsical, highly engaging, colorful. Clean 2D illustration. "
        "No text in the image."
    )
    image_bytes = fetch_cloudflare_image(prompt)
    img = Image.open(BytesIO(image_bytes)).convert('RGB')
    
    # Proportional Resizing to prevent stretching
    img_ratio = img.width / img.height
    page_ratio = PAGE_WIDTH / PAGE_HEIGHT
    
    if img_ratio > page_ratio:
        # Image is wider than page
        new_width = PAGE_WIDTH
        new_height = int(PAGE_WIDTH / img_ratio)
    else:
        # Image is taller than page
        new_height = PAGE_HEIGHT
        new_width = int(PAGE_HEIGHT * img_ratio)
        
    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    final_page = create_blank_page()
    # Center the proportionally resized image on the blank page
    x_offset = (PAGE_WIDTH - new_width) // 2
    y_offset = (PAGE_HEIGHT - new_height) // 2
    final_page.paste(img, (x_offset, y_offset))
    return final_page

def generate_text_page(title, subtitle="", draw_line=False, draw_shapes=False):
    print(f"Generating programmatic page: {title[:15]}...")
    img = create_blank_page()
    draw = ImageDraw.Draw(img)
    font_path = download_font()
    
    title_font = ImageFont.truetype(font_path, 120)
    sub_font = ImageFont.truetype(font_path, 60)
    
    draw.text((PAGE_WIDTH//2, PAGE_HEIGHT//3), title, fill="black", font=title_font, anchor="mm")
    
    if subtitle:
        draw.text((PAGE_WIDTH//2, (PAGE_HEIGHT//3) + 150), subtitle, fill="black", font=sub_font, anchor="mm")
        
    if draw_line:
        draw.line([(PAGE_WIDTH//2 - 400, PAGE_HEIGHT//2 + 100), (PAGE_WIDTH//2 + 400, PAGE_HEIGHT//2 + 100)], fill="black", width=5)
        
    if draw_shapes:
        start_y = PAGE_HEIGHT // 2
        for i in range(4):
            x0 = (PAGE_WIDTH // 5) * (i + 1) - 150
            y0 = start_y
            x1 = x0 + 300
            y1 = y0 + 300
            draw.ellipse([x0, y0, x1, y1], outline="black", width=10)
            
    return img

def generate_interior_page(theme, modifier):
    print(f"Generating interior line art: {modifier[:20]}...")
    prompt = (
        f"A children's coloring book page of a {theme}. {modifier}. "
        "Full body shot, zoomed out, character centered entirely within the frame, no cropping. "
        "Targeted for ages 2-5: ultra-thick, bold outlines, single central subject, large open coloring areas. "
        "ABSOLUTELY NO TEXT, NO LETTERS, NO NUMBERS, NO WORDS, AND NO SIGNATURES. "
        "Clean, 2D illustration. Strictly no shading, no grayscale, no cross-hatching, no gradients, and no color. "
        "Only bold, thick, clean black outlines on a pure white background."
    )
    
    image_bytes = fetch_cloudflare_image(prompt)
    img = Image.open(BytesIO(image_bytes)).convert('L')
    
    # Pre-sharpen the image before contrast boost to prevent blur on upscale
    img = img.filter(ImageFilter.SHARPEN)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(3.0)
    img = img.point(lambda x: 255 if x > 140 else 0, '1')
    
    inner_width, inner_height = (PAGE_WIDTH - 300, PAGE_HEIGHT - 300)
    
    # Proportional resizing for interior images to prevent stretching
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
    # Paste centered within the safe margin box
    x_offset = 150 + ((inner_width - new_width) // 2)
    y_offset = 150 + ((inner_height - new_height) // 2)
    final_page.paste(img, (x_offset, y_offset))
    return final_page

def build_book():
    theme = get_todays_theme()
    print(f"--- Building digital product for: {theme} ---")
    
    pages = []
    pages.append(generate_cover_page(theme))
    pages.append(generate_text_page("This Book Belongs To:", draw_line=True))
    pages.append(generate_text_page("Terms of Use", "This digital file is for personal use only.\nDo not resell or distribute.", draw_line=False))
    pages.append(generate_text_page("Color Test Page", "Try your markers, crayons, or colored pencils below!", draw_shapes=True))
    
    # Dynamic modifiers to ensure all 30 pages are unique
    scene_modifiers = [
        "Surrounded by simple fluffy clouds and stars",
        "Standing in a grassy field with tiny flowers",
        "Looking very happy with a big smile",
        "With a big bright sun in the sky",
        "Sitting down playfully",
        "With a few simple trees in the background",
        "Waving hello",
        "Surrounded by simple geometric shapes like circles and triangles",
        "Wearing a cute little bow tie",
        "Looking curious with wide open spaces around"
    ]
    
    # Generate 30 illustrations, cycling through the modifiers
    for i in range(30):
        mod = scene_modifiers[i % len(scene_modifiers)]
        pages.append(generate_interior_page(theme, mod))
        
    filename = f"Digital_Coloring_Book_{theme.replace(' ', '_')}.pdf"
    pages[0].save(
        filename, "PDF", resolution=300, save_all=True, append_images=pages[1:]
    )
    print(f"Successfully saved {filename}")

if __name__ == "__main__":
    build_book()