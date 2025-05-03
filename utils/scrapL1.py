import requests
from bs4 import BeautifulSoup
import csv
import logging

# Configure logging
logging.basicConfig(
    filename='scraper_errors.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# URL to scrape
url = "https://in.mathworks.com/help/slrealtime/ug/troubleshooting-basics.html"

# Send HTTP request
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Ubuntu/22.04'
}

try:
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # Raise exception for 4XX/5XX responses
        
    # Parse HTML content
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Extract main content
    main_content = soup.find('div', id='pgtype-topic')
    if main_content:
        all_a_tags = main_content.find_all('a')
        # Extract all image URLs
        all_img_tags = main_content.find_all('img')
        
        # for all a tags extract href and text
        with open('output.csv', 'w', newline='', encoding='utf-8') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(['Text', 'Link'])
            for a_tag in all_a_tags:
                text = a_tag.get_text(strip=True)
                link = a_tag.get('href')
                if text and link:
                    csvwriter.writerow([text, link])
        
        # Save image links to a separate CSV
        with open('image_links.csv', 'w', newline='', encoding='utf-8') as imgfile:
            imgwriter = csv.writer(imgfile)
            imgwriter.writerow(['Image URL', 'Alt Text'])
            for img_tag in all_img_tags:
                img_src = img_tag.get('src')
                img_alt = img_tag.get('alt', '')
                if img_src:
                    imgwriter.writerow([img_src, img_alt])
        
        print(f"Successfully extracted {len(all_a_tags)} links and {len(all_img_tags)} images")
    else:
        print("Main content not found")
        logging.error("Main content not found on the page")

except requests.exceptions.RequestException as e:
    error_msg = f"Error fetching the webpage: {e}"
    print(error_msg)
    logging.error(error_msg)
except Exception as e:
    error_msg = f"An error occurred: {e}"
    print(error_msg)
    logging.error(error_msg)