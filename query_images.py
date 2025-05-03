import json
import torch
import numpy as np
from transformers import CLIPProcessor, CLIPModel

class ImageSearchEngine:
    """
    A search engine for finding images based on text queries using CLIP embeddings.
    """
    
    def __init__(self, embeddings_file=None, model_name="openai/clip-vit-base-patch32", device=None):
        """
        Initialize the search engine with embeddings and CLIP model
        
        Args:
            embeddings_file: Path to JSON file containing image embeddings
            model_name: HuggingFace model name for CLIP
            device: PyTorch device (cuda/cpu); if None, will auto-detect
        """
        # Set up device for model
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        # Load CLIP model & processor
        self.model = CLIPModel.from_pretrained(model_name).to(self.device)
        self.processor = CLIPProcessor.from_pretrained(model_name)
        self.model.eval()
        
        # Initialize empty image entries list
        self.image_entries = []
        
        # Load embeddings if file is provided
        if embeddings_file:
            self.load_embeddings(embeddings_file)
    
    def load_embeddings(self, embeddings_file):
        """
        Load image embeddings from a JSON file
        
        Args:
            embeddings_file: Path to JSON file containing image embeddings
        """
        try:
            with open(embeddings_file, "r", encoding="utf-8") as f:
                page_dict = json.load(f)
                
            # Reset image entries
            self.image_entries = []
            
            # Process each entry
            for page_url, entries in page_dict.items():
                for e in entries:
                    self.image_entries.append({
                        "url": e["url"],
                        "heading": e.get("heading"),
                        "embedding": np.array(e["embedding"], dtype=np.float32)
                    })
                    
            print(f"Loaded {len(self.image_entries)} image embeddings from {embeddings_file}")
            return True
        except Exception as e:
            print(f"Error loading embeddings: {e}")
            return False
    
    def search(self, query, top_k=2):
        """
        Find top-K matching images for a text query
        
        Args:
            query: Text query to search for
            top_k: Number of results to return
            
        Returns:
            List of dicts with url, heading, and similarity score
        """
        if not self.image_entries:
            print("No embeddings loaded. Use load_embeddings() first.")
            return []
            
        # Encode query text
        inputs = self.processor(text=[query], return_tensors="pt", padding=True).to(self.device)
        with torch.no_grad():
            text_feats = self.model.get_text_features(**inputs)
            text_feats = text_feats / text_feats.norm(p=2, dim=-1, keepdim=True)
        text_feats = text_feats.cpu().numpy()[0]  # (512,)

        # Stack all image embeddings
        img_embs = np.stack([ie["embedding"] for ie in self.image_entries])  # (N,512)

        # Cosine similarity = dot product since both are normalized
        sims = img_embs @ text_feats  # (N,)

        # Take top_k indices
        top_idxs = np.argsort(-sims)[:top_k]

        # Return the matching URLs (and optional headings/scores)
        results = []
        for idx in top_idxs:
            ie = self.image_entries[idx]
            results.append({
                "url": ie["url"],
                "heading": ie["heading"],
                "score": float(sims[idx])
            })
        return results

def create_search_engine(embeddings_file=None):
    """
    Helper function to create a search engine instance
    
    Args:
        embeddings_file: Path to JSON file with image embeddings
        
    Returns:
        Initialized ImageSearchEngine
    """
    return ImageSearchEngine(embeddings_file)

def search_images(query, top_k=2, embeddings_file="images_log.json"):
    """
    Quick search function - creates engine, loads embeddings and searches in one call
    
    Args:
        query: Text query to search for
        top_k: Number of results to return
        embeddings_file: Path to JSON file with image embeddings
        
    Returns:
        List of dicts with url, heading, and similarity score
    """
    engine = ImageSearchEngine(embeddings_file)
    return engine.search(query, top_k)

# Default config
JSON_LOG = "images_log.json"
TOP_K = 2

if __name__ == "__main__":
    # Example usage with the modular approach
    query = input("Enter your search query: ")
    
    # Create and use the search engine
    engine = ImageSearchEngine(JSON_LOG)
    matches = engine.search(query, TOP_K)
    
    print("\nTop matches:")
    for m in matches:
        print(f"- {m['url']}  (heading: {m['heading']}, score: {m['score']:.4f})")
