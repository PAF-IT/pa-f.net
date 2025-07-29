"""
Parser module for extracting content from HTML files.
"""

from bs4 import BeautifulSoup
from markdownify import MarkdownConverter
import re
import os
import json


def md(soup, **options):
    """Convert BeautifulSoup object to markdown."""
    return MarkdownConverter(**options).convert_soup(soup)


class SiteParser:
    """Parser for extracting content and metadata from HTML files."""
    
    def __init__(self, root_dir="pa-f.net/"):
        """
        Initialize the parser.
        
        Args:
            root_dir (str): Root directory containing HTML files to parse
        """
        self.root_dir = root_dir
        self.sitemap = {}
    
    def should_skip_file(self, path):
        """
        Determine if a file should be skipped during parsing.
        
        Args:
            path (str): File path to check
            
        Returns:
            bool: True if file should be skipped
        """
        skip_conditions = [
            path.startswith("pa-f.net/book/export"),
            "size=" in path,
            path.startswith("pa-f.net/tracker?"),
            path.startswith("pa-f.net/files/")
        ]
        return any(skip_conditions)
    
    def extract_title(self, soup):
        """
        Extract title from HTML soup.
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            str: Extracted title or 'pa-f' as default
        """
        try:
            title_element = soup.select("title")[0]
            title = ' |'.join(title_element.text.split(" |")[:-1]) or 'pa-f'
            return title
        except IndexError:
            return None
    
    def extract_links(self, soup):
        """
        Extract internal links from HTML soup.
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            list: List of internal links
        """
        links = []
        for link_elem in soup.select('a'):
            href = link_elem.get("href")
            if not href or href.startswith("mailto:"):
                continue
            
            # Clean up the href to get internal links
            clean_href = (href.split("https://pa-f.net")[-1]
                         .split("http://pa-f.net")[-1]
                         .split("http://www.pa-f.net")[-1])
            links.append(clean_href)
        
        return list(set(links))
    
    def extract_content(self, soup):
        """
        Extract main content from HTML soup and convert to markdown.
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            tuple: (content_md, image_path)
        """
        content_md = ""
        image = False
        
        # Handle multiple nodes
        if len(soup.select(".node .content")) > 1:
            for node in soup.select(".node"):
                title_elem = node.select_one(".title")
                content_elem = node.select_one(".content")
                if title_elem:
                    content_md += md(title_elem)
                if content_elem:
                    content_md += md(content_elem)
        else:
            content = soup.select_one(".node .content")
            if content:
                content_md = md(content)
                
                # Extract single image if present
                if len(content.select('img')) == 1:
                    image = content.select_one('img').get("src").lstrip("./")
        
        # Add galleries, images, and pager content
        for section_class in [".galleries", ".images", ".pager"]:
            section = soup.select_one(section_class)
            if section:
                if section_class == ".galleries":
                    # Clean up galleries
                    for el in section.select('.count, .last'):
                        el.decompose()
                content_md += "\n\n" + md(section)
        
        return content_md, image
    
    def extract_date(self, soup):
        """
        Extract date from HTML soup.
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            str or None: Extracted date in YYYY-MM-DD format
        """
        submitted = soup.select_one(".node .submitted")
        if submitted:
            date_match = re.search(r'\d{4}-\d{2}-\d{2}', submitted.text)
            if date_match:
                return date_match.group()
        return None
    
    def has_content(self, soup):
        """
        Check if the page has meaningful content.
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            bool: True if page has content
        """
        content = soup.select_one(".node .content")
        galleries = soup.select_one(".galleries")
        images = soup.select_one(".images")
        return bool(content or galleries or images)
    
    def parse_file(self, file_path):
        """
        Parse a single HTML file.
        
        Args:
            file_path (str): Path to HTML file
            
        Returns:
            dict or None: Parsed content data or None if skipped
        """
        if self.should_skip_file(file_path):
            print(f"skipping {file_path}")
            return None
        
        print(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')
        except UnicodeDecodeError:
            print("skipping - can't decode")
            return None
        
        title = self.extract_title(soup)
        if not title:
            print("skipping - no title")
            return None
        
        if not self.has_content(soup):
            print(f"no content found for page {file_path}")
            return None
        
        links = self.extract_links(soup)
        content_md, image = self.extract_content(soup)
        date = self.extract_date(soup)
        
        return {
            "title": title,
            "md": content_md,
            "date": date,
            "image": image,
            "links": links
        }
    
    def parse(self):
        """
        Parse all HTML files in the root directory.
        
        Returns:
            dict: Complete sitemap data
        """
        self.sitemap = {}
        
        for (dirpath, dirnames, filenames) in os.walk(self.root_dir):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                
                # Get relative path from root
                uid = file_path.split(self.root_dir)[1]
                
                parsed_data = self.parse_file(file_path)
                if parsed_data:
                    self.sitemap[uid] = parsed_data
        
        return self.sitemap
    
    def save_sitemap(self, output_path='sitemap.json'):
        """
        Save the parsed sitemap to a JSON file.
        
        Args:
            output_path (str): Path to save the sitemap JSON
        """
        with open(output_path, 'w') as f:
            json.dump(self.sitemap, f, indent=2)
    
    def load_sitemap(self, input_path='sitemap.json'):
        """
        Load sitemap from a JSON file.
        
        Args:
            input_path (str): Path to load the sitemap JSON from
            
        Returns:
            dict: Loaded sitemap data
        """
        with open(input_path, 'r') as f:
            self.sitemap = json.load(f)
        return self.sitemap
