import os
import requests

# Configuration
ids = [778, 700, 94, 658, 258, 6, 448, 133, 1, 393, 59, 445, 197, 359, 501, 405, 54, 257, 194, 143, 609, 571, 303, 470, 196, 849, 26, 149, 38, 722, 151, 212, 384, 37, 715, 181, 579, 677, 392, 330, 570, 302, 132, 254, 959, 195, 282, 980, 724, 471, 7, 131, 25, 104, 887, 595, 260, 155, 134, 135, 706, 403, 79, 472, 872, 158, 214, 937, 637, 376, 385, 363, 286, 389, 491, 545, 635, 334, 494, 229, 248, 157, 623, 475, 354, 9, 350, 768, 418, 754, 681, 704, 807, 730, 487, 306, 802, 492, 249, 58]
base_url = "https://www.pokemon.co.jp/ex/30th_logo/assets/img/download/"
download_folder = "pokemon_logos"

# Create the folder if it doesn't exist
os.makedirs(download_folder, exist_ok=True)

print(f"Starting download of {len(ids)} Pokémon images...")

for i in ids:
    # Format number to 4 digits (e.g., 778 -> 0778.png)
    filename = f"{i:04d}.png"
    url = f"{base_url}{filename}"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            # Save the file directly to the folder
            filepath = os.path.join(download_folder, filename)
            with open(filepath, "wb") as f:
                f.write(response.content)
            
            print(f"Downloaded: {filename}")
        else:
            print(f"Failed to download {filename} (Status: {response.status_code})")
            
    except Exception as e:
        print(f"Error downloading {filename}: {e}")

print(f"\nTask complete! Check the '{download_folder}' folder.")