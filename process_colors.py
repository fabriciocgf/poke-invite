import os
import json
import requests
from PIL import Image

image_folder = "pokemon_logos"
output_json = "refined_colors.json"

def get_pokemon_name(dex_number):
    """Fetches the Pokémon name from PokeAPI."""
    try:
        url = f"https://pokeapi.co/api/v2/pokemon/{dex_number}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            name = response.json().get('name', '')
            return name.capitalize()
    except Exception as e:
        print(f"Error fetching name for {dex_number}: {e}")
    return f"Pokémon #{dex_number}"

def is_black_or_white_or_gray(rgb, threshold_low=150, threshold_high=700):
    r, g, b = rgb
    rgb_sum = r + g + b
    if rgb_sum < threshold_low or rgb_sum > threshold_high: return True
    if max(rgb) - min(rgb) < 30: return True
    return False

def get_vibrant_predominant_color(img_path):
    try:
        with Image.open(img_path) as img:
            img = img.convert("RGBA")
            img = img.resize((50, 50), resample=Image.NEAREST)
            pixels = list(img.getdata())
            
            valid_pixels = [
                (p[0], p[1], p[2]) for p in pixels 
                if p[3] > 128 and not is_black_or_white_or_gray(p[:3])
            ]
            
            if not valid_pixels: return "#808080"

            counts = {}
            for p in valid_pixels: counts[p] = counts.get(p, 0) + 1
            most_frequent = max(counts, key=counts.get)
            
            return f"#{most_frequent[0]:02x}{most_frequent[1]:02x}{most_frequent[2]:02x}"
    except Exception:
        return "#808080"

# Main Execution
results = []
if not os.path.exists(image_folder):
    print(f"Error: Folder '{image_folder}' not found.")
else:
    files = sorted([f for f in os.listdir(image_folder) if f.endswith(".webp")])
    print(f"Processing {len(files)} images and fetching names...")

    for filename in files:
        full_path = os.path.join(image_folder, filename)
        color = get_vibrant_predominant_color(full_path)
        
        # Extract dex number from filename (e.g., "0025.png" -> 25)
        dex_number = int(filename.split('.')[0])
        name = get_pokemon_name(dex_number)
        
        results.append({
            "filename": filename,
            "name": name,
            "predominant_color": color
        })
        print(f"Processed #{dex_number} {name}: {color}")

    with open(output_json, "w") as f:
        json.dump(results, f, indent=4)
    print(f"\nSuccess! Results saved to {output_json}")