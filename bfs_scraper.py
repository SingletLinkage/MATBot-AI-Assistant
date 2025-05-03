import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
from urllib.parse import urljoin, urlparse
from structurify import struct_text
import os
import logging
from collections import deque
from tqdm import tqdm
import time

# Configure logging
logging.basicConfig(
    filename='scraper_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class BFSScraper:
    def __init__(self, base_url, max_depth=2, delay=1):
        """
        Initialize the BFS scraper
        
        Args:
            base_url: The starting URL for scraping
            max_depth: Maximum depth of links to follow (default: 2)
            delay: Time to wait between requests in seconds (default: 1)
        """
        self.base_url = base_url
        self.max_depth = max_depth
        self.delay = delay
        self.visited_urls = set()
        self.queue = deque()
        self.all_corpus = []
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Ubuntu/22.04'
        }
        
        # Create necessary directories
        if not os.path.exists('corpus'):
            os.makedirs('corpus')
        
    def is_valid_url(self, url):
        """Check if URL belongs to the same domain as base_url"""
        base_domain = urlparse(self.base_url).netloc
        url_domain = urlparse(url).netloc
        return base_domain in url_domain or not url_domain
    
    def get_page_content(self, url):
        """Fetch and parse page content, returns soup object or None if failed"""
        try:
            response = requests.get(url)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            logging.error(f"Failed to fetch {url}: {str(e)}")
            return None
    
    def extract_links(self, soup, current_url):
        """Extract all links from the page's main content area only"""
        links = []
        if soup:
            # Look specifically in the main content area
            main_content = soup.find('div', id='pgtype-topic')
            
            # If main content area is found, extract links only from there
            if main_content:
                for a_tag in main_content.find_all('a', href=True):
                    href = a_tag.get('href')
                    if href and not href.startswith(('#', 'javascript:', 'mailto:')):
                        absolute_url = urljoin(current_url, href)
                        if self.is_valid_url(absolute_url) and absolute_url not in self.visited_urls:
                            link_text = a_tag.get_text(strip=True)
                            links.append((link_text, absolute_url))
            else:
                logging.warning(f"No main content div found on {current_url}")
        return links
    
    def extract_images(self, soup, current_url):
        """Extract image URLs from the page's main content area only"""
        images = []
        if soup:
            # Look specifically in the main content area
            main_content = soup.find('div', id='pgtype-topic')
            
            # If main content area is found, extract images only from there
            if main_content:
                for img_tag in main_content.find_all('img', src=True):
                    img_src = img_tag.get('src')
                    absolute_img_url = urljoin(current_url, img_src)
                    images.append(absolute_img_url)
        return images
    
    def process_page(self, url, depth):
        """Process a single page: extract content, links and images"""
        if url in self.visited_urls:
            return []
        
        self.visited_urls.add(url)
        soup = self.get_page_content(url)
        
        if not soup:
            return []
        
        # Extract main content
        main_content = soup.find('div', id='pgtype-topic')
        if not main_content:
            logging.warning(f"No main content found on {url}, skipping content extraction")
            main_content = None  # Don't use whole page if pgtype-topic not found
            
            # Still return links for next level if we're not at max depth
            if depth < self.max_depth:
                return self.extract_links(soup, url)
            return []
        
        # Extract images
        images = self.extract_images(soup, url)
        
        # Generate a filename based on the URL
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.strip('/').split('/')
        filename = path_parts[-1] if path_parts else 'index'
        if not filename.endswith('.html'):
            filename += '.html'
            
        # Get title or use formatted URL if title is blank
        title = soup.title.get_text().strip() if soup.title else None
        if not title:
            # Format the URL into a readable title
            path = parsed_url.path.strip('/')
            if path:
                # Extract last part of the path and replace hyphens/underscores with spaces
                title = path.split('/')[-1]
                title = title.replace('-', ' ').replace('_', ' ').replace('.html', '')
                # Capitalize first letter of each word
                title = ' '.join(word.capitalize() for word in title.split())
            else:
                # If no path, use the domain name
                title = parsed_url.netloc
        
        op_file_name = title.replace(" ", "_") + ".json"
        op_file_name = op_file_name.replace(":", "_")
        op_file_name = op_file_name.replace("/", "_")
        
        # Only save to file if main content was found
        if main_content:
            save_path = os.path.join('corpus', op_file_name)
            try:
                # Add images to the json
                _json = struct_text(str(main_content), save_path, link=url, return_json=True)
                _json['images'] = images
                self.all_corpus.append(_json)
                
                # Also save the individual file
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(_json, f, ensure_ascii=False, indent=4)
                
                logging.info(f"Successfully scraped and saved: {url}")
            except Exception as e:
                logging.error(f"Error processing {url}: {str(e)}")
    
        # Return links for the next level if we're not at max depth
        if depth < self.max_depth:
            return self.extract_links(soup, url)
        return []

    
    def start_scraping(self):
        """Start the BFS scraping process"""
        # Add the starting URL to the queue with depth 0
        self.queue.append((self.base_url, 0))
        
        with tqdm(desc="Scraping pages") as pbar:
            while self.queue:
                current_url, depth = self.queue.popleft()
                
                # Skip if already visited
                if current_url in self.visited_urls:
                    continue
                
                logging.info(f"Processing URL: {current_url} at depth {depth}")
                
                # Process the page and get new links
                new_links = self.process_page(current_url, depth)
                
                # Add new links to the queue
                for text, link in new_links:
                    if link not in self.visited_urls:
                        self.queue.append((link, depth + 1))
                
                pbar.update(1)
                pbar.set_postfix({"Depth": depth, "Queue": len(self.queue), "Visited": len(self.visited_urls)})
                
                # Respect the delay between requests
                time.sleep(self.delay)
        
        # Save all corpus to a single file
        with open('corpus.json', 'w', encoding='utf-8') as f:
            json.dump(self.all_corpus, f, ensure_ascii=False, indent=4)
        logging.info(f"All corpus saved to corpus.json with {len(self.all_corpus)} pages")
        print(f"Scraping completed. Processed {len(self.visited_urls)} URLs. Results saved in 'corpus.json'")
        
        # Generate a CSV with all links
        self.save_links_to_csv()
    
    def save_links_to_csv(self):
        """Save all visited links to a CSV file"""
        df = pd.DataFrame({
            'URL': list(self.visited_urls)
        })
        df.to_csv('scraped_links.csv', index=False)
        logging.info(f"Saved {len(df)} links to scraped_links.csv")

if __name__ == "__main__":
    # URL to scrap
    base_url = "https://in.mathworks.com/help/slrealtime/ug/troubleshooting-basics.html"
    
    # Create scraper with max depth 3
    scraper = BFSScraper(base_url, max_depth=3)
    
    # Start scraping
    scraper.start_scraping()
