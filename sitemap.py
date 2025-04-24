from bs4 import BeautifulSoup
import os

import json

def parse():

    ROOT = "pa-f.net/"

    sitemap = {}

    for (dirpath, dirnames, filenames) in os.walk(ROOT):
        for filename in filenames:
            path = os.path.join(dirpath, filename)

            print(path)

            my_uid = path.split(ROOT)[1]

            try:
                soup = BeautifulSoup(open(path))
            except UnicodeDecodeError:
                print("skipping - can't decode")
                continue

            try:
                title = soup.select("title")[0].text.split(" |")[0]
            except IndexError:
                print("skipping - no title")
                continue

            links = list(set([X['href'].split("https://pa-f.net")[-1].split("http://pa-f.net")[-1].split("http://www.pa-f.net")[-1] for X in soup.select('a') if X.get("href") and not X['href'].startswith("mailto:")]))

            sitemap[my_uid] = {"title": title, "links": links}

    json.dump(sitemap, open('sitemap.json', 'w'), indent=2)



links_to = {}                   # uid => cnt
for k,v in sitemap.items():
    for l in v['links']:
        if l.startswith('http'):
            continue
        if '?' in l:
            continue

        l = l.lstrip('/')

        if l not in sitemap:
            print("dead?", l)
            continue

        links_to[l] = links_to.get(l, 0) + 1



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
