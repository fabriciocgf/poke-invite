import os
from PIL import Image

folder = "pokemon_logos"

print("Starting compression to WebP...")

count = 0
for filename in os.listdir(folder):
    if filename.endswith(".png"):
        png_path = os.path.join(folder, filename)
        webp_filename = filename.replace(".png", ".webp")
        webp_path = os.path.join(folder, webp_filename)
        
        try:
            # Open the heavy PNG
            with Image.open(png_path) as img:
                # Save it as a highly compressed WebP (quality=80 is the sweet spot)
                img.save(webp_path, "webp", quality=80)
            
            # Delete the old PNG to save space
            os.remove(png_path)
            count += 1
            print(f"Compressed: {filename} -> {webp_filename}")
            
        except Exception as e:
            print(f"Error compressing {filename}: {e}")

print(f"\nSuccess! Compressed {count} images to WebP.")