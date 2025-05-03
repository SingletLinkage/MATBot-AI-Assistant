import requests
from bs4 import BeautifulSoup
import csv

# URL to scrape
url = "https://in.mathworks.com/help/slrealtime/ug/troubleshooting-basics.html"

# Send HTTP request
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Ubuntu/22.04'
}

try:
    response = requests.get(url)
        
    # Parse HTML content
    soup = BeautifulSoup(response.text, 'html.parser')

    
    # Extract main content
    main_content = soup.find('div', id='pgtype-topic')
    if main_content:
        all_a_tags = main_content.find_all('a')
        # for all a tags extract href and text
        with open('output.csv', 'w', newline='', encoding='utf-8') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(['Text', 'Link'])
            for a_tag in all_a_tags:
                text = a_tag.get_text(strip=True)
                link = a_tag.get('href')
                if text and link:
                    csvwriter.writerow([text, link])
                    # print(f"Text: {text}, Link: {link}")
    else:
        print("Main content not found")

except requests.exceptions.RequestException as e:
    print(f"Error fetching the webpage: {e}")
except Exception as e:
    print(f"An error occurred: {e}")