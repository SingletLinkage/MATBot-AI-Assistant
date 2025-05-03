import json
import os
import requests
import torch
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import io
from tqdm import tqdm

# ───── CONFIG ───────────────────────────────────────────────────────────────
CORPUS_DIR = "/home/arka/Desktop/Hackathons/HCLTech_CS671/corpus"
JSON_LOG = "images_log.json"
# ────────────────────────────────────────────────────────────────────────────

# Load CLIP once
device    = "cuda" if torch.cuda.is_available() else "cpu"
model     = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
model.eval()

def fetch_image_embedding(img_url: str) -> list[float]:
    resp = requests.get(img_url, timeout=10)
    resp.raise_for_status()
    img = Image.open(io.BytesIO(resp.content)).convert("RGB")
    inputs = processor(images=img, return_tensors="pt").to(device)
    with torch.no_grad():
        feats = model.get_image_features(**inputs)
        feats = feats / feats.norm(p=2, dim=-1, keepdim=True)
    return feats[0].cpu().tolist()

def process_corpus_images():
    if not os.path.exists(CORPUS_DIR):
        print(f"❌ Corpus directory not found: {CORPUS_DIR}")
        return

    # Get all JSON files in the corpus directory
    corpus_files = [f for f in os.listdir(CORPUS_DIR) if f.endswith('.json')]
    
    if not corpus_files:
        print(f"❌ No JSON files found in corpus directory: {CORPUS_DIR}")
        return
    
    print(f"🔍 Found {len(corpus_files)} JSON files in corpus directory")
    
    results = {}
    total_images_count = 0
    processed_images_count = 0
    
    # First pass to count total images for overall progress bar
    for filename in corpus_files:
        try:
            with open(os.path.join(CORPUS_DIR, filename), 'r', encoding='utf-8') as f:
                data = json.load(f)
            image_urls = data.get("images", [])
            total_images_count += len(image_urls)
        except Exception as e:
            print(f"  ❌ Error counting images in {filename}: {e}")
    
    print(f"📊 Total images to process: {total_images_count}")
    
    # Process each file with progress bar
    overall_pbar = tqdm(total=total_images_count, desc="Total progress", unit="img")
    
    # Process each file
    for filename in tqdm(corpus_files, desc="Processing files", unit="file"):
        filepath = os.path.join(CORPUS_DIR, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Get the page URL from the data
            page_url = data.get("link", f"file://{filepath}")
            
            # Extract image URLs from the data
            image_urls = data.get("images", [])
            
            if not image_urls:
                results[page_url] = []
                continue
            
            # Process each image with a nested progress bar
            entries = []
            for img_url in image_urls:
                # Find relevant heading from the chunks if available
                heading = None
                if "chunks" in data:
                    for chunk in data["chunks"]:
                        if "heading" in chunk:
                            heading = chunk["heading"]
                            break
                
                try:
                    emb = fetch_image_embedding(img_url)
                    entries.append({
                        "url":       img_url,
                        "heading":   heading,
                        "embedding": emb
                    })
                    processed_images_count += 1
                    overall_pbar.set_postfix({"success": f"{processed_images_count}/{total_images_count}"})
                except Exception as e:
                    overall_pbar.write(f"⚠️ Could not embed {img_url}: {e}")
                
                overall_pbar.update(1)
            
            results[page_url] = entries
            
        except Exception as e:
            overall_pbar.write(f"❌ Error processing {filename}: {e}")
            continue
    
    overall_pbar.close()
    
    # Write JSON log
    with open(JSON_LOG, "w", encoding="utf-8") as jf:
        json.dump(results, jf, ensure_ascii=False, indent=2)
    
    print(f"\n🎉 Done—processed {processed_images_count}/{total_images_count} images from {len(results)} files")
    print(f"📄 Results logged to {JSON_LOG}")

if __name__ == "__main__":
    process_corpus_images()
