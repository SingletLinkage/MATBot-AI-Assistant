import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
from urllib.parse import urljoin
from structurify import struct_text
import os
from tqdm import tqdm

# URL to scrap
base_url = "https://in.mathworks.com/help/slrealtime/ug/"

all_corpus = []

# Read the CSV file
try:
    df = pd.read_csv('all_links.csv')
    for index, row in tqdm(df.iterrows(), total=len(df), desc="Processing links"):
        text = row['Text']
        link = row['Link']
        if pd.notna(link):
            # convert into absolute URL using base url and link
            absolute_url = urljoin(base_url, link)
            # print(f"Text: {text} Absolute URL: {absolute_url}")

            # fetch page
            response = requests.get(absolute_url)
            soup = BeautifulSoup(response.text, 'html.parser')

            main_content = soup.find('div', id='pgtype-topic')

            if main_content:
                op_file_name = text.replace(" ", "_") + ".json"
                op_file_name = op_file_name.replace(":", "_")

                if not os.path.exists('corpus'):
                    os.makedirs('corpus')

                # save the file in corpus folder
                save_path = os.path.join('corpus', op_file_name)
                _json = struct_text(str(main_content), save_path, link=absolute_url, return_json=True)
                all_corpus.append(_json)
    
    # save all_courpus to a single file
    with open('corpus.json', 'w', encoding='utf-8') as f:
        json.dump(all_corpus, f, ensure_ascii=False, indent=4)
    print(f"All corpus saved to corpus.json")
                    

except FileNotFoundError:
    print("File 'output.csv' not found.")
except pd.errors.EmptyDataError:
    print("File 'output.csv' is empty.")
except Exception as e:
    print(f"An error occurred: {e}")