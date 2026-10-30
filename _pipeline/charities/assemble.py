"""Inline data.json into template.html and wrap it as a standalone page (light theme, to match the site).

Usage: python3 -I assemble.py template.html data.json out.html
"""
import sys

tpl, data, out = sys.argv[1:4]
d = open(data, encoding="utf-8").read().replace("</", "<\\/")
body = open(tpl, encoding="utf-8").read().replace("__DATA__", d)
head = ('<!doctype html>\n<html lang="en" data-theme="light">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<style>body{margin:0}[hidden]{display:none!important}</style>\n</head>\n<body>\n')
open(out, "w", encoding="utf-8").write(head + body + "\n</body>\n</html>\n")
