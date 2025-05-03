import sys
import json
import re
from bs4 import BeautifulSoup

def extract_text(element):
    """Extract clean text from an element, removing extra spaces and newlines."""
    if element is None:
        return ""
    text = element.get_text()
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_introduction(soup, main_title):
    """Extract the introduction text that appears before the first h3."""
    # Find the main title
    title_element = None
    if main_title:
        title_element = soup.find('h2', string=lambda s: main_title in s if s else False)
    
    if not title_element:
        title_element = soup.find('h2')
    
    if title_element:
        # Get all paragraphs between the title and the first h3
        introduction_text = []
        current = title_element.next_sibling
        first_h3 = soup.find('h3')
        
        while current and (first_h3 is None or current != first_h3):
            if current.name == 'p':
                text = extract_text(current)
                if text:
                    introduction_text.append(text)
            current = current.next_sibling
            
        return ' '.join(introduction_text)
    return ""

def html_to_simple_json(html_content):
    """
    Convert HTML content to a simplified JSON format.
    
    Args:
        html_content (str): HTML content as a string
        
    Returns:
        dict: Simple JSON representation with title, introduction, and chunks
    """
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Initialize the JSON structure
    json_data = {}
    
    # Extract the main title
    main_title_elem = soup.find('h2', class_='title')
    main_title = extract_text(main_title_elem) if main_title_elem else ""
    json_data["title"] = main_title
    
    # Extract introduction
    json_data["introduction"] = extract_introduction(soup, main_title)
    
    # Initialize chunks array
    chunks = []
    
    # Process all h3 and h4 as chunk headings
    for heading in soup.find_all(['h3', 'h4']):
        chunk = {
            "heading": extract_text(heading),
            "content": ""
        }
        
        # Collect all content until the next heading
        content_elements = []
        current = heading.next_sibling
        
        while current and current.name not in ['h3', 'h4']:
            if current.name in ['p', 'pre', 'ol', 'ul', 'div'] and not isinstance(current, str):
                if current.name in ['ol', 'ul']:
                    # For lists, extract as bullet points
                    list_items = []
                    for li in current.find_all('li'):
                        list_items.append("• " + extract_text(li))
                    if list_items:
                        content_elements.append("\n".join(list_items))
                else:
                    text = extract_text(current)
                    if text:
                        content_elements.append(text)
            
            current = current.next_sibling
        
        # Combine all content elements with proper spacing
        chunk["content"] = "\n\n".join(content_elements)
        chunks.append(chunk)
    
    json_data["chunks"] = chunks
    
    return json_data

def save_json_to_file(json_data, output_file):
    """
    Save JSON data to a file.
    
    Args:
        json_data (dict): JSON data to save
        output_file (str): Path to the output file
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, indent=2, ensure_ascii=False, fp=f)
    # print(f"JSON file created successfully: {output_file}")


def struct_file(input_file='input.html', output_file='output.json'):    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        json_data = html_to_simple_json(html_content)
        save_json_to_file(json_data, output_file)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def struct_text(text='', output_file='output.json', link=None, return_json=False):    
    try:
        
        json_data = html_to_simple_json(text)
        if link:
            json_data["link"] = link
        save_json_to_file(json_data, output_file)
        if return_json:
            return json_data
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)