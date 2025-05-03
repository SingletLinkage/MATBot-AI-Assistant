import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
from urllib.parse import urljoin
from structurify import struct_text
import os
import logging
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    filename='failed_urls.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# URL to scrap
base_url = "https://in.mathworks.com/help/slrealtime/ug/"

all_corpus = []
visited_urls = set()  # Keep track of visited URLs

# Read the CSV file
try:
    df = pd.read_csv('all_links.csv')
    for index, row in tqdm(df.iterrows(), total=len(df), desc="Processing links"):
        text = row['Text']
        link = row['Link']
        if pd.notna(link):
            # convert into absolute URL using base url and link
            absolute_url = urljoin(base_url, link)
            
            # Skip if already visited
            if absolute_url in visited_urls:
                continue
            
            visited_urls.add(absolute_url)
            
            try:
                # fetch page
                response = requests.get(absolute_url)
                response.raise_for_status()  # Raise exception for 4XX/5XX responses
                soup = BeautifulSoup(response.text, 'html.parser')

                main_content = soup.find('div', id='pgtype-topic')

                if main_content:
                    op_file_name = text.replace(" ", "_") + ".json"
                    op_file_name = op_file_name.replace(":", "_")
                    op_file_name = op_file_name.replace("/", "_")

                    # Extract all image URLs from the page
                    images = []
                    for img_tag in soup.find_all('img', src=True):
                        img_src = img_tag.get('src')
                        absolute_img_url = urljoin(absolute_url, img_src)
                        images.append(absolute_img_url)

                    if not os.path.exists('corpus'):
                        os.makedirs('corpus')

                    # save the file in corpus folder
                    save_path = os.path.join('corpus', op_file_name)
                    _json = struct_text(str(main_content), save_path, link=absolute_url, return_json=True)
                    
                    # Add images to the json
                    _json['images'] = images
                    all_corpus.append(_json)
                    
                    # Also save the individual file with images
                    with open(save_path, 'w', encoding='utf-8') as f:
                        json.dump(_json, f, ensure_ascii=False, indent=4)
            except Exception as e:
                error_msg = f"Error processing {absolute_url}: {str(e)}"
                print(error_msg)
                logging.error(error_msg)
    
    # save all_corpus to a single file
    with open('corpus.json', 'w', encoding='utf-8') as f:
        json.dump(all_corpus, f, ensure_ascii=False, indent=4)
    print(f"All corpus saved to corpus.json")
                    
except FileNotFoundError:
    print("File 'all_links.csv' not found.")
except pd.errors.EmptyDataError:
    print("File 'all_links.csv' is empty.")
except Exception as e:
    print(f"An error occurred: {e}")
    logging.error(f"General error: {str(e)}")