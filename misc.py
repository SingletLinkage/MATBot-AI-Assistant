import os
import json
from pathlib import Path

def find_and_fix_jsons_without_title():
    corpus_dir = Path("corpus")
    files_fixed = []
    
    # Check if corpus directory exists
    if not corpus_dir.exists() or not corpus_dir.is_dir():
        print(f"Error: Directory {corpus_dir} not found.")
        return []
    
    count = 0
    # Scan all JSON files
    for json_file in corpus_dir.glob("**/*.json"):
        count += 1
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Check if title field is missing
            if "title" not in data or not data["title"]:
                # Generate title from filename (without extension)
                new_title = json_file.stem.replace('_', ' ')
                
                # Update the title
                data["title"] = new_title
                
                # Save the updated JSON back to file
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4)
                
                files_fixed.append((str(json_file), new_title))
        except json.JSONDecodeError:
            print(f"Warning: Could not decode JSON file: {json_file}")
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
    
    print(f"Checked {count} JSON files in total.")
    
    return files_fixed

if __name__ == "__main__":
    # fixed_files = find_and_fix_jsons_without_title()
    
    # if fixed_files:
    #     print(f"Fixed {len(fixed_files)} JSON files without 'title' field:")
    #     for file, title in fixed_files:
    #         print(f"  - {file} (new title: '{title}')")
    # else:
    #     print("All JSON files already had 'title' field or no JSON files were found.")
    
    def create_consolidated_corpus():
        corpus_dir = Path("corpus")
        all_documents = []
        
        if not corpus_dir.exists() or not corpus_dir.is_dir():
            print(f"Error: Directory {corpus_dir} not found.")
            return
        
        print("Creating consolidated corpus.json file...")
        
        # Collect data from all JSON files
        for json_file in corpus_dir.glob("**/*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    all_documents.append(data)
            except Exception as e:
                print(f"Error reading {json_file}: {e}")
        
        if not all_documents:
            print("No JSON files found to consolidate.")
            return
        
        # Save all documents to a single corpus.json file
        with open("corpus.json", 'w', encoding='utf-8') as f:
            json.dump(all_documents, f, indent=4)
        
        print(f"Created corpus.json with {len(all_documents)} documents.")

    # After fixing titles, create the consolidated corpus
    create_consolidated_corpus()