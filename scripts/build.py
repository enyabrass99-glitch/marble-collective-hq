import os, json, requests, re
from pathlib import Path

TOKEN = os.environ["NOTION_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

PAGES = {
    "mission":      "39df4023b3f381e1a80ec786dcfd695d",
    "welcome":      "39df4023b3f381fc8acce7598e2a9e53",
    "ambassadors":  "39df4023b3f38166b1f6dfb0046ac4a8",
    "impact":       "39df4023b3f381b983f1ca2c2677226a",
    "quotes":       "39df4023b3f38144b8fcde6549f76936",
    "exhibition":   "39df4023b3f381d181f2d0549c9e8b79",
    "pressroom":    "39df4023b3f38173b745e6351c0c13c6",
    "evidence":     "39df4023b3f3810586cecf653181f391",
    "history":      "39df4023b3f381f38e3fda873e42b56a",
    "inventions":   "39df4023b3f38198b95ae7e5c6b6ddde",
    "reflection":   "39df4023b3f3816eab45cb23f9f827f0",
}

def get_page_title(page_id):
    r = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=HEADERS)
    data = r.json()
    try:
        props = data.get("properties", {})
        for val in props.values():
            if val.get("type") == "title":
                parts = val["title"]
                return "".join(p["plain_text"] for p in parts)
    except:
        pass
    return "Untitled"

def get_blocks(page_id):
    blocks, cursor = [], None
    while True:
        url = f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        r = requests.get(url, headers=HEADERS)
        data = r.json()
        blocks.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return blocks

def rich_text_to_html(rich_text):
    html = ""
    for t in rich_text:
        text = t.get("plain_text", "")
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        ann = t.get("annotations", {})
        link = t.get("href")
        if ann.get("bold"):        text = f"<strong>{text}</strong>"
        if ann.get("italic"):      text = f"<em>{text}</em>"
        if ann.get("code"):        text = f"<code>{text}</code>"
        if ann.get("strikethrough"): text = f"<s>{text}</s>"
        if link:                   text = f'<a href="{link}" target="_blank">{text}</a>'
        html += text
    return html

def blocks_to_html(blocks):
    html = ""
    i = 0
    while i < len(blocks):
        b = blocks[i]
        bt = b["type"]
        if bt == "heading_1":
            html += f'<h1>{rich_text_to_html(b["heading_1"]["rich_text"])}</h1>\n'
        elif bt == "heading_2":
            html += f'<h2>{rich_text_to_html(b["heading_2"]["rich_text"])}</h2>\n'
        elif bt == "heading_3":
            html += f'<h3>{rich_text_to_html(b["heading_3"]["rich_text"])}</h3>\n'
        elif bt == "paragraph":
            text = rich_text_to_html(b["paragraph"]["rich_text"])
            if text.strip():
                html += f'<p>{text}</p>\n'
            else:
                html += '<br>\n'
        elif bt == "bulleted_list_item":
            items = []
            while i < len(blocks) and blocks[i]["type"] == "bulleted_list_item":
                items.append(f'<li>{rich_text_to_html(blocks[i]["bulleted_list_item"]["rich_text"])}</li>')
                i += 1
            html += f'<ul>{"".join(items)}</ul>\n'
            continue
        elif bt == "numbered_list_item":
            items = []
            while i < len(blocks) and blocks[i]["type"] == "numbered_list_item":
                items.append(f'<li>{rich_text_to_html(blocks[i]["numbered_list_item"]["rich_text"])}</li>')
                i += 1
            html += f'<ol>{"".join(items)}</ol>\n'
            continue
        elif bt == "to_do":
            checked = b["to_do"].get("checked", False)
            check = "✅" if checked else "☐"
            text = rich_text_to_html(b["to_do"]["rich_text"])
            html += f'<p class="todo">{check} {text}</p>\n'
        elif bt == "quote":
            html += f'<blockquote>{rich_text_to_html(b["quote"]["rich_text"])}</blockquote>\n'
        elif bt == "callout":
            emoji = b["callout"].get("icon", {}).get("emoji", "💡")
            text = rich_text_to_html(b["callout"]["rich_text"])
            html += f'<div class="callout"><span class="callout-icon">{emoji}</span><div>{text}</div></div>\n'
        elif bt == "divider":
            html += '<hr>\n'
        elif bt == "table":
            rows_html = ""
            if b.get("has_children"):
                child_blocks = get_blocks(b["id"])
                for j, row in enumerate(child_blocks):
                    if row["type"] == "table_row":
                        cells = row["table_row"]["cells"]
                        tag = "th" if j == 0 else "td"
                        row_html = "".join(f'<{tag}>{rich_text_to_html(cell)}</{tag}>' for cell in cells)
                        rows_html += f'<tr>{row_html}</tr>'
            html += f'<div class="table-wrap"><table>{rows_html}</table></div>\n'
        elif bt == "toggle":
            summary = rich_text_to_html(b["toggle"]["rich_text"])
            inner = ""
            if b.get("has_children"):
                child_blocks = get_blocks(b["id"])
                inner = blocks_to_html(child_blocks)
            html += f'<details><summary>{summary}</summary><div class="toggle-content">{inner}</div></details>\n'
        elif bt == "image":
            img = b["image"]
            url = img.get("file", {}).get("url") or img.get("external", {}).get("url", "")
            caption = rich_text_to_html(img.get("caption", []))
            html += f'<figure><img src="{url}" alt="{caption}"><figcaption>{caption}</figcaption></figure>\n'
        elif bt == "column_list":
            if b.get("has_children"):
                cols = get_blocks(b["id"])
                html += '<div class="columns">'
                for col in cols:
                    if col["type"] == "column" and col.get("has_children"):
                        col_blocks = get_blocks(col["id"])
                        html += f'<div class="column">{blocks_to_html(col_blocks)}</div>'
                html += '</div>\n'
        i += 1
    return html

NAV_LINKS = [
    ("🪨 Mission", "mission"),
    ("👋 Welcome", "welcome"),
    ("⭐ Ambassadors", "ambassadors"),
    ("📊 Impact", "impact"),
    ("💬 Quotes", "quotes"),
    ("🎉 Exhibition", "exhibition"),
    ("🎨 Pressroom", "pressroom"),
]

def build_page(key, content_html, title):
    nav = "".join(
        f'<a href="{k}.html" class="{"active" if k == key else ""}">{label}</a>'
        for label, k in NAV_LINKS
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — The Marble Collective</title>
<style>
  :root {{
    --marble-blue: #1a56db;
    --marble-blue-light: #e8f0fe;
    --marble-dark: #1a1a2e;
    --marble-mid: #374151;
    --marble-light: #f9fafb;
    --marble-border: #e5e7eb;
    --marble-accent: #3b82f6;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--marble-light); color: var(--marble-mid); line-height: 1.7; }}
  .site-header {{ background: linear-gradient(135deg, #1a56db 0%, #1e3a8a 100%); color: white; padding: 20px 32px; box-shadow: 0 2px 12px rgba(26,86,219,0.3); }}
  .site-header .logo {{ font-size: 28px; font-weight: 800; }}
  .site-header .tagline {{ font-size: 13px; opacity: 0.85; margin-top: 2px; }}
  nav {{ background: white; border-bottom: 1px solid var(--marble-border); padding: 0 24px; display: flex; gap: 4px; overflow-x: auto; position: sticky; top: 0; z-index: 100; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
  nav a {{ color: var(--marble-mid); text-decoration: none; padding: 14px 16px; font-size: 14px; font-weight: 500; white-space: nowrap; border-bottom: 3px solid transparent; transition: all 0.15s; }}
  nav a:hover {{ color: var(--marble-blue); border-bottom-color: var(--marble-blue-light); }}
  nav a.active {{ color: var(--marble-blue); border-bottom-color: var(--marble-blue); font-weight: 700; }}
  main {{ max-width: 860px; margin: 40px auto; padding: 0 24px 80px; }}
  .page-title {{ font-size: 32px; font-weight: 800; color: var(--marble-dark); margin-bottom: 32px; padding-bottom: 16px; border-bottom: 2px solid var(--marble-border); }}
  h1 {{ font-size: 22px; font-weight: 700; color: var(--marble-dark); margin: 32px 0 12px; }}
  h2 {{ font-size: 18px; font-weight: 700; color: var(--marble-dark); margin: 24px 0 10px; }}
  h3 {{ font-size: 16px; font-weight: 600; color: var(--marble-mid); margin: 20px 0 8px; }}
  p {{ margin: 8px 0; }}
  ul, ol {{ margin: 10px 0 10px 24px; }}
  li {{ margin: 4px 0; }}
  a {{ color: var(--marble-blue); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  hr {{ border: none; border-top: 1px solid var(--marble-border); margin: 24px 0; }}
  strong {{ font-weight: 700; }}
  em {{ font-style: italic; }}
  code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 13px; }}
  blockquote {{ border-left: 4px solid var(--marble-accent); padding: 12px 20px; background: var(--marble-blue-light); border-radius: 0 8px 8px 0; margin: 16px 0; color: var(--marble-dark); font-style: italic; }}
  .callout {{ display: flex; gap: 12px; background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 10px; padding: 16px; margin: 12px 0; }}
  .callout-icon {{ font-size: 20px; flex-shrink: 0; }}
  .todo {{ padding: 4px 0; }}
  .table-wrap {{ overflow-x: auto; margin: 16px 0; border-radius: 10px; border: 1px solid var(--marble-border); }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: var(--marble-dark); color: white; padding: 12px 16px; text-align: left; font-size: 13px; font-weight: 600; }}
  td {{ padding: 11px 16px; border-bottom: 1px solid var(--marble-border); font-size: 14px; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:nth-child(even) td {{ background: #f8fafc; }}
  details {{ background: white; border: 1px solid var(--marble-border); border-radius: 10px; margin: 8px 0; }}
  summary {{ padding: 14px 18px; cursor: pointer; font-weight: 600; color: var(--marble-dark); list-style: none; }}
  summary::before {{ content: '▶ '; font-size: 11px; color: var(--marble-accent); }}
  details[open] summary::before {{ content: '▼ '; }}
  .toggle-content {{ padding: 4px 18px 16px; }}
  figure {{ margin: 16px 0; }}
  img {{ max-width: 100%; border-radius: 10px; }}
  figcaption {{ font-size: 12px; color: #9ca3af; margin-top: 6px; }}
  .columns {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 24px; margin: 16px 0; }}
  footer {{ text-align: center; padding: 24px; color: #9ca3af; font-size: 12px; border-top: 1px solid var(--marble-border); margin-top: 40px; }}
</style>
</head>
<body>
<header class="site-header">
  <div>
    <div class="logo">🪨 The Marble Collective</div>
    <div class="tagline">An in-person after-school community · Denver, CO · 2026</div>
  </div>
</header>
<nav>{nav}</nav>
<main>
  <div class="page-title">{title}</div>
  {content_html}
</main>
<footer>The Marble Collective · Built from Notion · Updates automatically</footer>
</body>
</html>"""

def main():
    dist = Path("dist")
    dist.mkdir(exist_ok=True)
    first_key = None
    for key, page_id in PAGES.items():
        print(f"Fetching {key}...")
        try:
            title = get_page_title(page_id)
            blocks = get_blocks(page_id)
            content = blocks_to_html(blocks)
            html = build_page(key, content, title)
            (dist / f"{key}.html").write_text(html, encoding="utf-8")
            if first_key is None:
                first_key = key
                (dist / "index.html").write_text(html, encoding="utf-8")
            print(f"  ✓ {title}")
        except Exception as e:
            print(f"  ✗ {key}: {e}")
    print("Done!")

if __name__ == "__main__":
    main()
