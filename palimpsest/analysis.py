"""
Analysis module for site structure and link analysis.
"""

import os
import json


class SiteAnalyzer:
    """Analyzer for site structure, links, and content relationships."""
    
    def __init__(self, sitemap_data=None):
        """
        Initialize the analyzer.
        
        Args:
            sitemap_data (dict): Parsed sitemap data
        """
        self.sitemap = sitemap_data or {}
    
    def load_sitemap(self, sitemap_path='sitemap.json'):
        """
        Load sitemap data from JSON file.
        
        Args:
            sitemap_path (str): Path to sitemap JSON file
        """
        with open(sitemap_path, 'r') as f:
            self.sitemap = json.load(f)
    
    def analyze_links(self):
        """
        Analyze internal links and calculate link popularity.
        
        Returns:
            dict: Dictionary mapping page UIDs to incoming link counts
        """
        links_to = {}
        
        for k, v in self.sitemap.items():
            for link in v.get('links', []):
                if link.startswith('http'):
                    continue
                if '?' in link:
                    continue
                
                link = link.lstrip('/')
                
                # Handle relative links
                if link.startswith('../'):
                    if '.' in k.split('/')[-1]:
                        k2 = '/'.join(k.split('/')[:-1]) + '/'
                    else:
                        k2 = k
                    link = os.path.normpath(k2 + link)
                
                if link not in self.sitemap:
                    continue
                
                links_to[link] = links_to.get(link, 0) + 1
        
        return links_to
    
    def generate_page_list(self):
        """
        Generate an HTML list of pages sorted by link popularity.
        
        Returns:
            str: HTML content with ordered list of pages
        """
        links_to = self.analyze_links()
        
        html = "<html><head><meta charset='utf-8' /></head><body><ol>\n"
        
        # Sort pages by link count (descending)
        sorted_pages = sorted(
            self.sitemap.items(), 
            key=lambda x: links_to.get(x[0], 0), 
            reverse=True
        )
        
        for k, v in sorted_pages:
            if '?' in k:
                continue
            
            cnt = links_to.get(k, 0)
            link = k.replace('.html', '')
            if link == 'index':
                link = ''
            
            html += f"<li><a href='https://pa-f.net/{link}' target='_blank'>{v['title']}</a> <small>({cnt})</small></li>\n"
        
        html += "</ol></body></html>\n"
        return html
    
    def generate_graphviz(self):
        """
        Generate a GraphViz representation of the site structure.
        
        Returns:
            str: GraphViz DOT format content
        """
        badchars = '/-.?=+& '
        
        dot_content = "digraph F {\n"
        
        for uid_raw, obj in self.sitemap.items():
            # Clean up UID for GraphViz
            uid = uid_raw
            for ch in badchars:
                uid = uid.replace(ch, '_')
            
            # Add node with title
            title = obj["title"].replace('"', '')
            dot_content += f'{uid} [label="{title}"];\n'
            
            # Add links
            for link_raw in obj.get('links', []):
                link = link_raw
                if link.strip() == '/':
                    link = "index.html"
                link = link.lstrip('/')
                
                if not link.strip():
                    continue
                
                if link.startswith("http"):
                    continue
                
                # Clean up link for GraphViz
                for ch in badchars:
                    link = link.replace(ch, '_')
                
                dot_content += f"{uid} -> {link};\n"
        
        dot_content += "}"
        return dot_content
    
    def get_content_statistics(self):
        """
        Get statistics about the parsed content.
        
        Returns:
            dict: Statistics about pages, content, dates, etc.
        """
        stats = {
            'total_pages': len(self.sitemap),
            'pages_with_dates': 0,
            'pages_with_images': 0,
            'total_content_length': 0,
            'date_range': {'earliest': None, 'latest': None}
        }
        
        dates = []
        
        for uid, data in self.sitemap.items():
            # Count pages with dates
            if data.get('date'):
                stats['pages_with_dates'] += 1
                dates.append(data['date'])
            
            # Count pages with images
            if data.get('image'):
                stats['pages_with_images'] += 1
            
            # Sum content length
            if data.get('md'):
                stats['total_content_length'] += len(data['md'])
        
        # Calculate date range
        if dates:
            dates.sort()
            stats['date_range']['earliest'] = dates[0]
            stats['date_range']['latest'] = dates[-1]
        
        return stats
    
    def find_pages_by_keyword(self, keyword):
        """
        Find pages containing a specific keyword in title or content.
        
        Args:
            keyword (str): Keyword to search for
            
        Returns:
            list: List of tuples (uid, title, relevance_score)
        """
        results = []
        keyword_lower = keyword.lower()
        
        for uid, data in self.sitemap.items():
            score = 0
            
            # Check title
            if keyword_lower in data['title'].lower():
                score += 10
            
            # Check content
            if data.get('md') and keyword_lower in data['md'].lower():
                score += data['md'].lower().count(keyword_lower)
            
            if score > 0:
                results.append((uid, data['title'], score))
        
        # Sort by relevance score (descending)
        results.sort(key=lambda x: x[2], reverse=True)
        return results
    
    def get_pages_by_date_range(self, start_date=None, end_date=None):
        """
        Get pages within a specific date range.
        
        Args:
            start_date (str): Start date in YYYY-MM-DD format
            end_date (str): End date in YYYY-MM-DD format
            
        Returns:
            list: List of tuples (uid, title, date)
        """
        results = []
        
        for uid, data in self.sitemap.items():
            page_date = data.get('date')
            if not page_date:
                continue
            
            # Check date range
            if start_date and page_date < start_date:
                continue
            if end_date and page_date > end_date:
                continue
            
            results.append((uid, data['title'], page_date))
        
        # Sort by date (descending)
        results.sort(key=lambda x: x[2], reverse=True)
        return results
    
    def export_analysis_report(self, output_path='analysis_report.html'):
        """
        Export a comprehensive analysis report as HTML.
        
        Args:
            output_path (str): Path to save the analysis report
        """
        stats = self.get_content_statistics()
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Site Analysis Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 2rem; }}
        .stat {{ margin: 1rem 0; }}
        .stat strong {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>Site Analysis Report</h1>
    
    <h2>Content Statistics</h2>
    <div class="stat"><strong>Total Pages:</strong> {stats['total_pages']}</div>
    <div class="stat"><strong>Pages with Dates:</strong> {stats['pages_with_dates']}</div>
    <div class="stat"><strong>Pages with Images:</strong> {stats['pages_with_images']}</div>
    <div class="stat"><strong>Total Content Length:</strong> {stats['total_content_length']:,} characters</div>
    
    <h2>Date Range</h2>
    <div class="stat"><strong>Earliest:</strong> {stats['date_range']['earliest'] or 'N/A'}</div>
    <div class="stat"><strong>Latest:</strong> {stats['date_range']['latest'] or 'N/A'}</div>
    
    <h2>Recent Pages</h2>
    <table>
        <tr><th>Page</th><th>Title</th><th>Date</th></tr>"""
        
        recent_pages = self.get_pages_by_date_range()[:20]  # Top 20 recent pages
        for uid, title, date in recent_pages:
            html += f"<tr><td>{uid}</td><td>{title}</td><td>{date}</td></tr>"
        
        html += """
    </table>
</body>
</html>"""
        
        with open(output_path, 'w') as f:
            f.write(html)
        
        print(f"Analysis report saved to {output_path}")
