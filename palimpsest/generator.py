"""
Static site generator module for creating HTML files from parsed content.
"""

from markdown import markdown
from html import escape as html_escape
import re
import os
import random
import json


def markdown2html(md_content):
    """
    Convert markdown content to HTML.

    Args:
        md_content (str): Markdown content

    Returns:
        str: HTML content
    """
    # Clean up markdown formatting
    md_content = re.sub(r"^\s*\*? (#+)\s*(.*)$", r"\1 \2", md_content, flags=re.MULTILINE)
    return markdown(md_content, extensions=["extra"])


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def excerpt(md_content, max_chars=180):
    """Return a plain-text excerpt of markdown suitable for og:description."""
    text = _TAG_RE.sub("", markdown2html(md_content or ""))
    text = _WS_RE.sub(" ", text).strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return f"{cut}…"


class StaticSiteGenerator:
    """Generator for creating static HTML sites from parsed content."""

    def __init__(self, sitemap_data=None, output_dir="paf-static", site_root="https://pa-f.net"):
        """
        Initialize the generator.

        Args:
            sitemap_data (dict): Parsed sitemap data
            output_dir (str): Output directory for generated site
            site_root (str): Absolute origin used for canonical/OG URLs
        """
        self.sitemap = sitemap_data or {}
        self.output_dir = output_dir
        self.site_root = site_root.rstrip("/")
        self.sidebar_content = ""

    def load_sitemap(self, sitemap_path='sitemap.json'):
        """
        Load sitemap data from JSON file.

        Args:
            sitemap_path (str): Path to sitemap JSON file
        """
        with open(sitemap_path, 'r') as f:
            self.sitemap = json.load(f)

    def load_sidebar(self, sidebar_path='sidebar.html'):
        """
        Load sidebar content from HTML file.

        Args:
            sidebar_path (str): Path to sidebar HTML file
        """
        try:
            with open(sidebar_path, 'r') as f:
                self.sidebar_content = f.read()
        except FileNotFoundError:
            print(f"Warning: Sidebar file {sidebar_path} not found")
            self.sidebar_content = ""

    def setup_output_directory(self):
        """Create output directory and setup image symlinks."""
        os.makedirs(self.output_dir, exist_ok=True)

        # Symlink to the scraped images
        im_src_path = os.path.abspath("pa-f.net/sites/pa-f.net/files")
        im_dest_path = os.path.join(self.output_dir, "sites/pa-f.net/files")
        im_dir = os.path.dirname(im_dest_path)
        os.makedirs(im_dir, exist_ok=True)

        if not os.path.exists(im_dest_path) and os.path.exists(im_src_path):
            os.symlink(im_src_path, im_dest_path)

    def get_all_images(self):
        """
        Get all images from the sitemap.

        Returns:
            list: List of tuples (page_path, image_path)
        """
        all_images = []
        for k, v in self.sitemap.items():
            if v.get("image"):
                all_images.append((k, v['image']))
        return all_images

    def calculate_relative_root(self, page_path):
        """
        Calculate relative path to root from a given page path.

        Args:
            page_path (str): Path to the page

        Returns:
            str: Relative path to root
        """
        return "../" * (len(page_path.split("/")) - 1)

    def generate_page_html(self, page_path, page_data, all_images):
        """
        Generate HTML content for a single page.

        Args:
            page_path (str): Path to the page
            page_data (dict): Page data from sitemap
            all_images (list): List of all available images

        Returns:
            str: Complete HTML content
        """
        root_path = self.calculate_relative_root(page_path)

        # Process sidebar content
        sidebar_html = self.sidebar_content.replace("https://pa-f.net/", root_path)

        # Pick random logo and image
        logo_names = ["roundtable_logo.png", "paf-yellow.png", "paf-orange.png",
                     "paf-pink.png", "paf-waves.png"]
        logo_name = random.choice(logo_names)
        logo_path = f"/sites/pa-f.net/files/{logo_name}"
        home_path = root_path or "/"

        # Pick random image
        if all_images:
            im_pagepath, im_path = random.choice(all_images)
            im_pagepath = root_path + strip_html_suffix(im_pagepath)
            im_path = images_from_root(root_path + im_path)
        else:
            im_pagepath = im_path = ""

        # Generate title HTML
        title_html = ""
        if page_data["title"] != "pa-f":
            title_html = f'<h2>{page_data["title"]}</h2>'
            if page_data.get("date"):
                title_html += f'<div id="date">{page_data["date"]}</div>'

        # --- Open Graph / Twitter Card meta tags ---
        page_title = page_data.get("title") or "pa-f"
        description = excerpt(page_data.get("md", ""))
        canonical = f"{self.site_root}/{strip_html_suffix(page_path.lstrip('/'))}"
        # Hero image: explicit `image` field if set, else the same random one used in the sidebar.
        hero = page_data.get("image") or im_path
        if hero:
            hero_abs = hero if hero.startswith("http") else f"{self.site_root}/{hero.lstrip('/')}"
        else:
            hero_abs = ""
        og_title = html_escape(page_title, quote=True)
        og_desc = html_escape(description, quote=True)
        og_url = html_escape(canonical, quote=True)
        og_image = html_escape(hero_abs, quote=True)
        og_image_tag = f'<meta property="og:image" content="{og_image}" />\n    <meta name="twitter:image" content="{og_image}" />' if hero_abs else ""
        meta_tags = f"""<link rel="canonical" href="{og_url}" />
    <meta name="description" content="{og_desc}" />
    <meta property="og:type" content="article" />
    <meta property="og:site_name" content="pa-f" />
    <meta property="og:title" content="{og_title}" />
    <meta property="og:description" content="{og_desc}" />
    <meta property="og:url" content="{og_url}" />
    {og_image_tag}
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="{og_title}" />
    <meta name="twitter:description" content="{og_desc}" />"""

        # Generate complete HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html_escape(page_title, quote=True)} | pa-f</title>
    {meta_tags}
    <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: sans-serif;
            margin: 0;
        }}
        .page-wrapper {{
            display: flex;
        }}
        .left-sidebar {{
            width: 325px;
            flex-shrink: 0;
        }}
        .logo-container img {{
            display: block;
        }}
        main {{
            flex-grow: 1;
            padding: 1rem;
        }}
        aside {{
            width: 250px;
            flex-shrink: 0;
            padding: 1rem;
        }}

        a {{
            color: #6cc;
            text-decoration: none;
        }}
        a:hover {{
            color: black;
            text-decoration: underline;
        }}
        h2 a {{
            color: black;
        }}
        nav ul, aside ul {{ list-style: none; padding: 0; }}
        nav ul li a, aside ul li a {{ display: block; padding: 0.2rem 0; }}
        nav {{ padding: 1rem; }}

        .attendees-mobile {{ display: none; }}

        footer {{
            text-align: center;
            font-weight: bold;
            padding: 1rem;
        }}

        .hamburger {{
            display: none;
            position: absolute;
            top: 15px;
            right: 15px;
            z-index: 1000;
            background: #333;
            color: white;
            border: none;
            padding: 10px;
            cursor: pointer;
        }}

        @media (max-width: 800px) {{
            .page-wrapper {{
                flex-direction: column;
            }}
            .left-sidebar, main, aside {{
                width: 100%;
            }}
            .left-sidebar {{ order: 1; }}
            main {{ order: 2; }}
            aside {{ order: 3; }}
            .logo-container {{
                height: 80px;
                text-align: center;
            }}
            .logo-container img {{
                height: 100%;
                width: auto;
            }}
            aside {{
                display: none;
            }}
            .left-sidebar nav {{
                display: none;
            }}
            body.show-menu .left-sidebar nav,
            body.show-menu .attendees-mobile {{
                display: block;
                background-color: #333;
                color: white;
            }}
            .hamburger {{
                display: block;
            }}
        }}
    </style>
</head>
<body>
    <button class="hamburger" onclick="toggleMenu()">&#9776;</button>
    <div class="page-wrapper">
        <div class="left-sidebar">
            <div class="logo-container">
                <a href="{home_path}"><img width="323" height="319" src="{logo_path}" alt="PAF Logo"></a>
            </div>
            <nav>
                <ul>
                    <li><a href="{home_path}">home</a></li>
                    <li><a href="{root_path}node/25153">news</a></li>
                    <li><a href="{root_path}downloads">downloads</a></li>
                    <li><a href="{root_path}program">events</a></li>
                    <li><a href="{root_path}basics">basics</a></li>
                    <li><a href="{root_path}image">galleries</a></li>
                    <li><a href="{root_path}basics/directions">how to get to PAF</a></li>
                    <li><a href="{root_path}node/25189">the mattress</a></li>
                    <li><a href="{root_path}contacts">contact</a></li>
                    <li><a href="{root_path}links">partners</a></li>
                </ul>
            <br />"""

        if im_path:
            html += f'<a href="{im_pagepath}"><img width="100%" src="{im_path}" /></a>'

        html += f"""
            <b>
            PAF is not sponsored or subsidised. PAF is paid for through the residency and membership fees of the about 1100 residents that pass by in a year.
            </b>
                <div class="attendees-mobile">
                    {sidebar_html}
                </div>
            </nav>
        </div>
        <main>
            <div id="main-content">
                {title_html}
                {images_from_root(markdown2html(page_data["md"]))}
            </div>
        </main>
        <aside>
            {sidebar_html}
        </aside>
    </div>
    <footer>
        Performing Arts Forum - 15, rue Haute 02820 St Erme Outre et Ramecourt - France | Association Loi 1901 SIRET : 499 353 001 000 13
    </footer>
    <script>
        function toggleMenu() {{
            document.body.classList.toggle('show-menu');
        }}
    </script>
</body>
</html>"""

        return html

    def generate_site(self):
        """Generate the complete static site."""
        if not self.sitemap:
            raise ValueError("No sitemap data loaded. Use load_sitemap() first.")

        self.setup_output_directory()
        self.load_sidebar()

        all_images = self.get_all_images()

        for page_path, page_data in self.sitemap.items():
            # Create directory structure
            output_path = os.path.join(self.output_dir, page_path)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Generate and write HTML
            html_content = self.generate_page_html(page_path, page_data, all_images)

            with open(output_path, "w") as fh:
                fh.write(html_content)

        print(f"Static site generated in {self.output_dir}")


def images_from_root(html):
    # Rewrite relative `../sites/pa-f.net` references to absolute `/sites/pa-f.net`.
    # Require at least one `../` — otherwise an already-absolute `/sites/pa-f.net`
    # would gain a second leading slash and resolve as protocol-relative
    # (browser reads `//sites/pa-f.net/...` as `https://sites/pa-f.net/...`).
    return re.sub(r"(?:\.\./)+sites/pa\-f\.net", "/sites/pa-f.net", html)


def strip_html_suffix(path: str) -> str:
    """Return the canonical extensionless form of a page path.

    Bucket object names still end in `.html`; this maps them to the URL form.
    """
    if path.endswith("/index.html"):
        return path[: -len("index.html")]  # keep trailing slash
    if path == "index.html":
        return ""
    if path.endswith(".html"):
        return path[: -len(".html")]
    return path
