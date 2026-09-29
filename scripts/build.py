#!/usr/bin/env python3
"""Dependency-free static blog builder. See README for supported Markdown."""
import datetime as dt
import html
import json
import math
import re
from pathlib import Path
from string import Template
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
EMPTY = ''


def esc(value):
    return html.escape(str(value), quote=True)


def safe_url(value):
    return value if urlsplit(value).scheme.lower() in ('', 'https', 'http', 'mailto') else '#'


def inline(value):
    tokens = []

    def protect(rendered):
        tokens.append(rendered)
        return f'\x00{len(tokens)-1}\x00'

    value = re.sub(r'`([^`]+)`', lambda m: protect('<code>' + esc(m[1]) + '</code>'), value)
    value = re.sub(r'\$([^$\n]+)\$', lambda m: protect('<span class="math">' + esc(m[1]) + '</span>'), value)
    value = re.sub(r'!\[([^\]]*)\]\(([^\s)]+)\)', lambda m: protect(f'<img src="{esc(safe_url(m[2]))}" alt="{esc(m[1])}" loading="lazy">'), value)
    value = re.sub(r'\[([^\]]+)\]\(([^\s)]+)\)', lambda m: protect(f'<a href="{esc(safe_url(m[2]))}">{esc(m[1])}</a>'), value)
    value = esc(value)
    value = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', value)
    value = re.sub(r'\*(.+?)\*', r'<em>\1</em>', value)
    return re.sub(r'\x00(\d+)\x00', lambda m: tokens[int(m[1])], value)


def markdown(source):
    result, paragraph, items, quote, code = [], [], [], [], []
    listing = None
    fence = None
    equation = None
    heading_count = 0

    def flush():
        nonlocal listing
        if paragraph:
            result.append('<p>' + inline(' '.join(paragraph)) + '</p>')
            paragraph.clear()
        if items:
            result.append(f'<{listing}>' + ''.join('<li>' + inline(x) + '</li>' for x in items) + f'</{listing}>')
            items.clear()
            listing = None
        if quote:
            result.append('<blockquote><p>' + inline(' '.join(quote)) + '</p></blockquote>')
            quote.clear()

    for line in source.splitlines():
        if fence is None and line.strip() == '$$':
            if equation is None:
                flush()
                equation = []
            else:
                result.append('<div class="math math-block">' + esc('\n'.join(equation)) + '</div>')
                equation = None
            continue
        if equation is not None:
            equation.append(line)
            continue
        if line.startswith('```'):
            if fence is not None:
                result.append('<pre><code>' + esc('\n'.join(code)) + '</code></pre>')
                code.clear()
                fence = None
            else:
                flush()
                fence = line[3:]
            continue
        if fence is not None:
            code.append(line)
            continue
        if not line.strip():
            flush()
            continue
        heading = re.match(r'^(#{1,6})\s+(.+)$', line)
        item = re.match(r'^\s*(?:([-*])|\d+\.)\s+(.+)$', line)
        if heading:
            flush()
            heading_count += 1
            level = len(heading[1])
            result.append(f'<h{level} id="section-{heading_count}">' + inline(heading[2]) + f'</h{level}>')
        elif item:
            kind = 'ul' if item[1] else 'ol'
            if paragraph or quote or (listing and kind != listing):
                flush()
            listing = kind
            items.append(item[2])
        elif line.startswith('> '):
            if paragraph or items:
                flush()
            quote.append(line[2:])
        elif line.strip() == '---':
            flush()
            result.append('<hr>')
        else:
            if items or quote:
                flush()
            paragraph.append(line.strip())
    if fence is not None:
        raise ValueError('代码块未闭合')
    if equation is not None:
        raise ValueError('公式块未闭合')
    flush()
    return '\n'.join(result)


def read_posts():
    posts = []
    for path in sorted((ROOT / 'content/posts').glob('*.md')):
        raw = path.read_text(encoding='utf-8')
        if not raw.startswith('---\n'):
            raise ValueError(f'{path.name}: 缺少文章元信息')
        parts = raw.split('---', 2)
        if len(parts) != 3:
            raise ValueError(f'{path.name}: 元信息未闭合')
        meta = {}
        for line in parts[1].strip().splitlines():
            key, value = line.split(':', 1)
            meta[key.strip()] = value.strip()
        for key in ('title', 'date', 'summary', 'draft'):
            if not meta.get(key):
                raise ValueError(f'{path.name}: 缺少 {key}')
        dt.date.fromisoformat(meta['date'])
        if meta['draft'] not in ('true', 'false'):
            raise ValueError(f'{path.name}: draft 必须是 true 或 false')
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', path.stem):
            raise ValueError(f'{path.name}: 文件名请使用小写英文、数字和连字符')
        rendered = markdown(parts[2].strip())
        if meta['draft'] == 'true':
            continue
        source = parts[2].strip()
        headings = re.findall(r'<h([23]) id="([^"]+)">(.*?)</h\1>', rendered)
        toc = ''.join(f'<a class="toc-level-{level}" href="#{anchor}">{esc(html.unescape(re.sub(r"<[^>]+>", "", text)))}</a>' for level, anchor, text in headings)
        plain = re.sub(r'\$\$[\s\S]*?\$\$|\$[^$\n]+\$', '', source)
        chinese = len(re.findall(r'[\u4e00-\u9fff]', plain))
        words = len(re.findall(r'[A-Za-z]+', plain))
        minutes = max(1, math.ceil(chinese / 400 + words / 200 + source.count('$$') / 2 * .2))
        meta.update(slug=path.stem, body=rendered, toc=toc, minutes=minutes)
        posts.append(meta)
    return sorted(posts, key=lambda x: (x['date'], x['slug']), reverse=True)


def build():
    config = json.loads((ROOT / 'site.json').read_text(encoding='utf-8'))
    layout = Template((ROOT / 'templates/layout.html').read_text(encoding='utf-8'))
    posts = read_posts()
    previous = json.loads((ROOT / 'generated-files.json').read_text()) if (ROOT / 'generated-files.json').exists() else []
    generated = []

    def write(path, content):
        target = ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content.rstrip() + '\n', encoding='utf-8')
        generated.append(path)

    def page(path, title, description, body, current='', og_type='website'):
        url_path = '/' if path == 'index.html' else '/' + path.removesuffix('index.html')
        write(path, layout.substitute(name=esc(config['name']), github=esc(config['github']), year=dt.date.today().year, title=esc(title), description=esc(description), canonical=esc(config['url'] + url_path), body=body, home_current='aria-current="page"' if current == 'home' else '', blog_current='aria-current="page"' if current == 'blog' else '', og_type=og_type, page_class='article-page' if og_type == 'article' else '', article_assets='<link rel="stylesheet" href="/assets/vendor/katex/katex.min.css"><script defer src="/assets/vendor/katex/katex.min.js"></script><script defer src="/assets/article.js"></script>' if og_type == 'article' else ''))

    def rows(selected):
        return ''.join(f'<a class="post-card" href="/blog/{p["slug"]}/"><div class="card-meta"><time datetime="{p["date"]}">{p["date"]}</time><span>约 {p["minutes"]} 分钟</span></div><h3>{esc(p["title"])}</h3><p>{esc(p["summary"])}</p><span class="card-open">阅读全文 <span aria-hidden="true">↗</span></span></a>' for p in selected) or EMPTY

    home = Template((ROOT / 'templates/home.html').read_text(encoding='utf-8')).substitute(name=esc(config['name']), github=esc(config['github']), posts=rows(posts[:5]))
    page('index.html', config['name'], config['description'], home, 'home')
    page('blog/index.html', '文章 · ' + config['name'], '机器学习笔记。', '<div class="page-intro"><h1>文章</h1></div><section class="post-list">' + rows(posts) + '</section>', 'blog')
    page('404.html', '页面未找到 · ' + config['name'], '页面未找到', '<div class="not-found"><h1>404</h1><p>页面未找到</p><a class="text-link" href="/">回到首页 ↗</a></div>')
    for post in posts:
        toc = '<nav class="toc-links" aria-label="文章目录">' + post['toc'] + '</nav>'
        body = f'<div class="article-layout"><article class="article"><a class="text-link" href="/blog/">← 全部文章</a><h1>{esc(post["title"])}</h1><div class="article-meta"><time datetime="{post["date"]}">{post["date"]}</time><span>预计阅读 {post["minutes"]} 分钟</span></div><details class="mobile-toc"><summary>目录</summary>{toc}</details><div class="prose">{post["body"]}</div></article><aside class="desktop-toc"><div class="toc-title">目录</div>{toc}</aside></div>'
        page(f'blog/{post["slug"]}/index.html', post['title'] + ' · ' + config['name'], post['summary'], body, 'blog', 'article')
    feed = ET.Element('rss', version='2.0')
    channel = ET.SubElement(feed, 'channel')
    for key, value in [('title', config['name']), ('link', config['url']), ('description', config['description']), ('language', 'zh-CN')]:
        ET.SubElement(channel, key).text = value
    for post in posts:
        item = ET.SubElement(channel, 'item')
        for key, value in [('title', post['title']), ('link', config['url'] + '/blog/' + post['slug'] + '/'), ('guid', config['url'] + '/blog/' + post['slug'] + '/'), ('description', post['summary']), ('pubDate', dt.datetime.strptime(post['date'], '%Y-%m-%d').strftime('%a, %d %b %Y 00:00:00 GMT'))]:
            ET.SubElement(item, key).text = value
    write('feed.xml', ET.tostring(feed, encoding='utf-8', xml_declaration=True).decode('utf-8'))
    sitemap = ET.Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
    for path in generated:
        if path.endswith('index.html'):
            entry = ET.SubElement(sitemap, 'url')
            ET.SubElement(entry, 'loc').text = config['url'] + ('/' if path == 'index.html' else '/' + path.removesuffix('index.html'))
    write('sitemap.xml', ET.tostring(sitemap, encoding='utf-8', xml_declaration=True).decode('utf-8'))
    write('robots.txt', 'User-agent: *\nAllow: /\nSitemap: ' + config['url'] + '/sitemap.xml')
    for obsolete in set(previous) - set(generated):
        if obsolete.startswith('blog/') and obsolete.endswith('/index.html'):
            target = ROOT / obsolete
            if target.exists():
                target.unlink()
    write('generated-files.json', json.dumps(generated, indent=2))
    print(f'构建完成：{len(posts)} 篇已发布文章。')


if __name__ == '__main__':
    build()
