#!/usr/bin/env python3
"""Convert a Slack canvas HTML export to GitHub-flavored markdown.

Reads HTML on stdin, writes markdown on stdout. Handles the structure Slack
canvas exports use: h1/h2 headings, nested ul/li lists, b/i, p, hr, br,
<a>/<lnk href> links, and emoji shortcodes left as text (GitHub renders them).
Slack user mentions (@U...) are left intact for downstream name substitution.
"""
import re
import sys
from html.parser import HTMLParser


class CanvasToMarkdown(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.ul_depth = 0
        self.href = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("h1", "h2", "h3"):
            level = {"h1": "#", "h2": "##", "h3": "###"}[tag]
            self.out.append("\n\n" + level + " ")
        elif tag == "p":
            self.out.append("\n\n")
        elif tag == "ul":
            self.ul_depth += 1
        elif tag == "li":
            self.out.append("\n" + "  " * max(0, self.ul_depth - 1) + "- ")
        elif tag in ("b", "strong"):
            self.out.append("**")
        elif tag in ("i", "em"):
            self.out.append("*")
        elif tag in ("a", "lnk") and a.get("href"):
            self.href = a["href"]
            self.out.append("[")
        elif tag == "hr":
            self.out.append("\n\n---\n")
        elif tag == "br":
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag == "ul":
            self.ul_depth = max(0, self.ul_depth - 1)
        elif tag in ("b", "strong"):
            self.out.append("**")
        elif tag in ("i", "em"):
            self.out.append("*")
        elif tag in ("a", "lnk") and self.href:
            self.out.append("](%s)" % self.href)
            self.href = None

    def handle_data(self, data):
        self.out.append(data)


def main():
    parser = CanvasToMarkdown()
    parser.feed(sys.stdin.read())
    text = "".join(parser.out)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    print(text.strip())


if __name__ == "__main__":
    main()
