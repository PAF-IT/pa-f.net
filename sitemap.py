from bs4 import BeautifulSoup
from markdown import markdown
from markdownify import MarkdownConverter
import re

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

            galleries = soup.select_one(".galleries")

            if not (content or galleries):
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
                content_md += md(galleries)


            #sitemap[my_uid] = {"title": title, "links": links, "md": content_md, "date": date}
            sitemap[my_uid] = {"title": title, "md": content_md, "date": date}

    json.dump(sitemap, open('sitemap.json', 'w'), indent=2)
    return sitemap

# sitemap = parse()

def dump():
    # Reconstruct the PAF site
    OUTDIR = "paf-static"
    os.makedirs(OUTDIR, exist_ok=True)

    # Symlink to the scraped images
    im_src_path = os.path.abspath("pa-f.net/sites/pa-f.net/files")
    im_dest_path = os.path.join(OUTDIR, "sites/pa-f.net/files")
    im_dir = os.path.dirname(im_dest_path)
    os.makedirs(im_dir, exist_ok=True)
    if not os.path.exists(im_dest_path):
        os.symlink(im_src_path, im_dest_path)

    for k,v in sitemap.items():
        os.makedirs(os.path.dirname(os.path.join(OUTDIR, k)), exist_ok=True)

        # Construct relative paths to the root
        ROOT = "../" * (len(k.split("/")) - 1)

        # Pick a logo based on nesting depth
        logo_names = ["roundtable_logo.png", "paf-yellow.png", "paf-orange.png", "paf-pink.png", "paf-waves.png"]
        logo_name = logo_names[(len(k.split("/")) - 1) % len(logo_names)]

        logo_path = f"{ROOT}sites/pa-f.net/files/{logo_name}"
        home_path = f"{ROOT}index.html"

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
            width: 100%;
            height: auto;
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
        
        nav ul, aside ul {{ list-style: none; padding: 0; }}
        nav ul li a, aside ul li a {{ text-decoration: none; color: #333; display: block; padding: 0.2rem 0; }}
        nav {{ padding: 1rem; }}

        .attendees-mobile {{ display: none; }}

        footer {{
            text-align: center;
            font-weight: bold;
            padding: 1rem;
        }}

        .hamburger {{
            display: none;
            position: fixed;
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
                <a href="{home_path}"><img src="{logo_path}" alt="PAF Logo"></a>
            </div>
            <nav>
                <h2>Navigation</h2>
                <ul>
                    <li><a href="/index.html">Home</a></li>
                    <li><a href="/about.html">About</a></li>
                    <li><a href="/contact.html">Contact</a></li>
                </ul>
                <div class="attendees-mobile">
                    <h3>Attendees</h3>
                    <ul>
                        <li>Attendee 1</li>
                        <li>Attendee 2</li>
                        <li>Attendee 3</li>
                    </ul>
                </div>
            </nav>
        </div>
        <main>
            <h2>{v["title"]}</h2>
            <div id="date">{v.get("date", "")}</div>
            <div id="main-content">
                {markdown(v["md"])}
            </div>
        </main>
        <aside>
            <h3>Attendees</h3>
            <ul>
                <li>Attendee 1</li>
                <li>Attendee 2</li>
                <li>Attendee 3</li>
            </ul>
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
