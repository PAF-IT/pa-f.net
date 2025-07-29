from bs4 import BeautifulSoup
from markdown import markdown
from markdownify import MarkdownConverter
import re
import random

import os

import json

def md(soup, **options):
    return MarkdownConverter(**options).convert_soup(soup)


def parse():

    ROOT = "pa-f.net/"

    sitemap = {}

    for (dirpath, dirnames, filenames) in os.walk(ROOT):
        for filename in filenames:
            path = os.path.join(dirpath, filename)

            if path.startswith("pa-f.net/book/export"):
                print("skipping printer-friendly page", path)
                continue

            if "size=" in path:
                #print("skipping resized image", path)
                continue

            if path.startswith("pa-f.net/tracker?"):
                #print("skipping tracker", path)
                continue
            if path.startswith("pa-f.net/files/"):
                #print("skipping file", path)
                continue

            print(path)

            my_uid = path.split(ROOT)[1]

            try:
                soup = BeautifulSoup(open(path))
            except UnicodeDecodeError:
                print("skipping - can't decode")
                continue

            try:
                title = ' |'.join(soup.select("title")[0].text.split(" |")[:-1]) or 'pa-f'
            except IndexError:
                print("skipping - no title")
                continue

            links = list(set([X['href'].split("https://pa-f.net")[-1].split("http://pa-f.net")[-1].split("http://www.pa-f.net")[-1] for X in soup.select('a') if X.get("href") and not X['href'].startswith("mailto:")]))

            image = False

            content_md = ""

            if len(soup.select(".node .content")) > 1:
                # There are many nodes listed here - bring in some *basic* structure

                for node in soup.select(".node"):
                    content_md += md(node.select_one(".title"))
                    # TODO: Include a date somehow? Or some sort of divider, or list indication?
                    content_md += md(node.select_one(".content"))

            else:
                content = soup.select_one(".node .content")
                if content:
                    content_md = md(content)

                    if len(content.select('img')) == 1:
                        image = content.select_one('img').get("src").lstrip("./")

            galleries = soup.select_one(".galleries")

            images = soup.select_one(".images")
            pager = soup.select_one(".pager")

            if not (content or galleries or images):
                print("no content found for page", path, content)
                continue

            # Find a timestamp
            submitted = soup.select_one(".node .submitted")
            date = None
            if submitted:
                date_match = re.search(r'\d{4}-\d{2}-\d{2}', submitted.text)
                if date_match:
                    date = date_match.group()

            if galleries:
                # some cleanup
                for el in galleries.select('.count, .last'):
                    el.decompose()

                content_md += "\n\n" + md(galleries)

            if images:
                content_md += "\n\n" + md(images)
            if pager:
                content_md += "\n\n" + md(pager)


            #sitemap[my_uid] = {"title": title, "links": links, "md": content_md, "date": date}
            sitemap[my_uid] = {"title": title, "md": content_md, "date": date, "image": image}

    json.dump(sitemap, open('sitemap.json', 'w'), indent=2)
    return sitemap

# sitemap = parse()

def markdown2html(md):
    md = re.sub(r"^\s*\*? (#+)\s*(.*)$", r"\1 \2", md, flags=re.MULTILINE)
    out = markdown(md, extensions=["extra"])
    return out

def dump():
    # Reconstruct the PAF site
    OUTDIR = "paf-static"
    os.makedirs(OUTDIR, exist_ok=True)

    # find all images nodes...
    all_images = []             # page_path, image_path
    for k,v in sitemap.items():
        if v.get("image"):
            all_images.append((k, v['image']))

    # Symlink to the scraped images
    im_src_path = os.path.abspath("pa-f.net/sites/pa-f.net/files")
    im_dest_path = os.path.join(OUTDIR, "sites/pa-f.net/files")
    im_dir = os.path.dirname(im_dest_path)
    os.makedirs(im_dir, exist_ok=True)
    if not os.path.exists(im_dest_path):
        os.symlink(im_src_path, im_dest_path)

    with open('sidebar.html', 'r') as f:
        sidebar_content = f.read()

    for k,v in sitemap.items():
        os.makedirs(os.path.dirname(os.path.join(OUTDIR, k)), exist_ok=True)

        # Construct relative paths to the root
        ROOT = "../" * (len(k.split("/")) - 1)

        sidebar_html = sidebar_content.replace("https://pa-f.net/", ROOT)

        # Pick a logo
        logo_names = ["roundtable_logo.png", "paf-yellow.png", "paf-orange.png", "paf-pink.png", "paf-waves.png"]
        logo_name = random.choice(logo_names)

        logo_path = f"{ROOT}sites/pa-f.net/files/{logo_name}"
        home_path = f"{ROOT}index.html"

        # Pick an image
        im_pagepath, im_path = random.choice(all_images)
        im_pagepath = ROOT + im_pagepath
        im_path = ROOT + im_path

        title_html = ""
        if v["title"] != "pa-f":
            title_html = f"""
            <h2>{v["title"]}</h2>
            """
            if v.get("date"):
                title_html += f"""
            <div id="date">{v.get("date", "")}</div>
            """

        with open(os.path.join(OUTDIR, k), "w") as fh:
            # generate a simple html page

            html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{v["title"]} | pa-f</title>
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
                    <li><a href="{ROOT}node/25153.html">news</a></li>
                    <li><a href="{ROOT}downloads.html">downloads</a></li>
                    <li><a href="{ROOT}program.html">events</a></li>
                    <li><a href="{ROOT}basics.html">basics</a></li>
                    <li><a href="{ROOT}image.html">galleries</a></li>
                    <li><a href="{ROOT}basics/directions.html">how to get to PAF</a></li>
                    <li><a href="{ROOT}node/25189.html">the mattress</a></li>
                    <li><a href="{ROOT}contacts.html">contact</a></li>
                    <li><a href="{ROOT}links.html">partners</a></li>
                </ul>
            <br />
            <a href="{im_pagepath}"><img width="100%" src="{im_path}" /></a>
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
                {markdown2html(v["md"])}
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

            fh.write(html)


def list():

    links_to = {}                   # uid => cnt
    for k,v in sitemap.items():

        print(k)

        for l in v['links']:
            if l.startswith('http'):
                continue
            if '?' in l:
                continue

            l = l.lstrip('/')

            if l.startswith('../'):
                if '.' in k.split('/')[-1]:
                    k2 = '/'.join(k.split('/')[:-1]) + '/'
                else:
                    k2 = k
                l2 = os.path.normpath(k2 + l)
                # print("convert", k, k2, l, l2)
                l = l2

            if l not in sitemap:
                # print("dead?", l)
                continue

            links_to[l] = links_to.get(l, 0) + 1

    txt = "<html><head><meta charset='utf-8' /></head><body><ol>\n"

    for k,v in sorted(sitemap.items(), key=lambda x: links_to.get(x[0], 0), reverse=True):
        if '?' in k:
            continue
        cnt = links_to.get(k, 0)
        link = k.replace('.html', '')
        if link == 'index':
            link = ''

        txt += f"<li><a href='https://pa-f.net/{link}' target='_blank'>{v['title']}</a> <small>({cnt})</small></li>\n"

    txt += "</ol></body></html>\n"

    return txt


def graph(sitemap):

    badchars = '/-.?=+& '

    txt = "digraph F {\n"
    for uid_raw, obj in sitemap.items():

        uid = uid_raw

        for ch in badchars:
            uid = uid.replace(ch, '_')

        txt += f'{uid} [label="{obj["title"].replace('"', '')}"];\n'
        for link_raw in obj['links']:
            link = link_raw
            if link.strip() == '/':
                link = "index-html"
            link = link.lstrip('/')

            if not link.strip():
                continue

            if link.startswith("http"):
                continue

            for ch in badchars:
                link = link.replace(ch, '_')

            txt += f"{uid} -> {link};\n"

    txt += "}"
