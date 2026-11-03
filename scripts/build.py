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
        toc = ''.join(
            f'<a class="toc-level-{level}" href="#{anchor}">{esc(html.unescape(re.sub(r"<[^>]+>", "", text)))}</a>'
            for level, anchor, text in headings
        )
        plain = re.sub(r'\$\$[\s\S]*?\$\$|\$[^$\n]+\$', '', source)
        chinese = len(re.findall(r'[\u4e00-\u9fff]', plain))
        words = len(re.findall(r'[A-Za-z]+', plain))
        minutes = max(1, math.ceil(chinese / 400 + words / 200 + source.count('$$') / 2 * .2))
        meta.update(slug=path.stem, body=rendered, toc=toc, minutes=minutes)
        posts.append(meta)
    return sorted(posts, key=lambda x: (x['date'], x['slug']), reverse=True)


def read_series(posts_by_slug):
    path = ROOT / 'content/series.json'
    if not path.exists():
        return []
    catalog = json.loads(path.read_text(encoding='utf-8'))
    series_list = []
    for entry in catalog:
        for key in ('id', 'title', 'summary', 'posts'):
            if not entry.get(key):
                raise ValueError(f'series.json: 缺少 {key}')
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', entry['id']):
            raise ValueError('series.json: id 请使用小写英文、数字和连字符')
        members = []
        for slug in entry['posts']:
            post = posts_by_slug.get(slug)
            if not post:
                raise ValueError(f'series.json: 找不到文章 {slug}')
            members.append(post)
        if not members:
            raise ValueError(f'series.json: {entry["id"]} 没有文章')
        series_list.append({
            'id': entry['id'],
            'title': entry['title'],
            'summary': entry['summary'],
            'posts': members,
            'count': len(members),
            'start': min(p['date'] for p in members),
            'end': max(p['date'] for p in members),
            'updated': max(p['date'] for p in members),
        })
    return sorted(series_list, key=lambda x: x['updated'], reverse=True)


def read_news():
    path = ROOT / 'content/news.json'
    if not path.exists():
        return []
    items = json.loads(path.read_text(encoding='utf-8'))
    news = []
    for entry in items:
        for key in ('date', 'text'):
            if not entry.get(key):
                raise ValueError('news.json: 缺少 date 或 text')
        dt.date.fromisoformat(entry['date'])
        href = entry.get('href') or ''
        if href and not href.startswith('/'):
            raise ValueError(f'news.json: href 仅支持站内路径，收到 {href}')
        news.append({'date': entry['date'], 'text': entry['text'], 'href': href})
    return sorted(news, key=lambda x: x['date'], reverse=True)


def read_pages():
    pages = []
    root = ROOT / 'content/pages'
    if not root.exists():
        return pages
    for path in sorted(root.glob('*.md')):
        raw = path.read_text(encoding='utf-8')
        if not raw.startswith('---\n'):
            raise ValueError(f'pages/{path.name}: 缺少元信息')
        parts = raw.split('---', 2)
        if len(parts) != 3:
            raise ValueError(f'pages/{path.name}: 元信息未闭合')
        meta = {}
        for line in parts[1].strip().splitlines():
            key, value = line.split(':', 1)
            meta[key.strip()] = value.strip()
        for key in ('title', 'summary'):
            if not meta.get(key):
                raise ValueError(f'pages/{path.name}: 缺少 {key}')
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', path.stem):
            raise ValueError(f'pages/{path.name}: 文件名请使用小写英文、数字和连字符')
        pages.append({
            'slug': path.stem,
            'title': meta['title'],
            'summary': meta['summary'],
            'body': markdown(parts[2].strip()),
        })
    return pages


def build():
    config = json.loads((ROOT / 'site.json').read_text(encoding='utf-8'))
    layout = Template((ROOT / 'templates/layout.html').read_text(encoding='utf-8'))
    posts = read_posts()
    posts_by_slug = {p['slug']: p for p in posts}
    series_list = read_series(posts_by_slug)
    series_slugs = {slug for series in series_list for slug in (p['slug'] for p in series['posts'])}
    standalone = [p for p in posts if p['slug'] not in series_slugs]
    news_items = read_news()
    pages = read_pages()
    previous = json.loads((ROOT / 'generated-files.json').read_text()) if (ROOT / 'generated-files.json').exists() else []
    generated = []

    def write(path, content):
        target = ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content.rstrip() + '\n', encoding='utf-8')
        generated.append(path)

    def page(path, title, description, body, current='', og_type='website', extra_assets='', page_class=''):
        url_path = '/' if path == 'index.html' else '/' + path.removesuffix('index.html')
        article_assets = (
            '<link rel="stylesheet" href="/assets/vendor/katex/katex.min.css">'
            '<script defer src="/assets/vendor/katex/katex.min.js"></script>'
            '<script defer src="/assets/article.js"></script>'
            if og_type == 'article' else ''
        )
        classes = ' '.join(x for x in [page_class, 'article-page' if og_type == 'article' else ''] if x)
        write(path, layout.substitute(
            name=esc(config['name']),
            github=esc(config['github']),
            year=dt.date.today().year,
            title=esc(title),
            description=esc(description),
            canonical=esc(config['url'] + url_path),
            body=body,
            home_current='aria-current="page"' if current == 'home' else '',
            about_current='aria-current="page"' if current == 'about' else '',
            cv_current='aria-current="page"' if current == 'cv' else '',
            blog_current='aria-current="page"' if current == 'blog' else '',
            og_type=og_type,
            page_class=classes,
            article_assets=article_assets + extra_assets,
        ))

    def blog_rows(selected):
        return ''.join(
            f'<a class="post-card" href="/blog/{p["slug"]}/">'
            f'<div class="card-meta"><time datetime="{p["date"]}">{p["date"]}</time>'
            f'<span>约 {p["minutes"]} 分钟</span></div>'
            f'<h3>{esc(p["title"])}</h3><p>{esc(p["summary"])}</p>'
            f'<span class="card-open">阅读全文 <span aria-hidden="true">↗</span></span></a>'
            for p in selected
        ) or EMPTY

    def compact_card(post, index=None):
        index_html = f'<span class="series-index">{index:02d}</span>' if index is not None else ''
        return (
            f'<a class="post-card post-card-compact" href="/blog/{post["slug"]}/" '
            f'aria-label="{esc(post["title"])}。{esc(post["summary"])}">'
            f'{index_html}'
            f'<div class="compact-copy"><time datetime="{post["date"]}">{post["date"]}</time>'
            f'<h3>{esc(post["title"])}</h3>'
            f'<p class="card-summary">{esc(post["summary"])}</p></div>'
            f'</a>'
        )

    def roomy_card(post, index=None):
        index_html = f'<span class="series-index">{index:02d}</span>' if index is not None else ''
        return (
            f'<a class="post-card post-card-roomy" href="/blog/{post["slug"]}/">'
            f'{index_html}'
            f'<div class="roomy-copy">'
            f'<div class="card-meta"><time datetime="{post["date"]}">{post["date"]}</time>'
            f'<span>约 {post["minutes"]} 分钟</span></div>'
            f'<h3>{esc(post["title"])}</h3>'
            f'<p>{esc(post["summary"])}</p>'
            f'<span class="card-open">阅读全文 <span aria-hidden="true">↗</span></span>'
            f'</div></a>'
        )

    def series_folder(series, *, card='compact', open_by_default=False, variant=''):
        span = series['start'] if series['start'] == series['end'] else f'{series["start"]} — {series["end"]}'
        maker = roomy_card if card == 'roomy' else compact_card
        cards = ''.join(maker(post, index=i) for i, post in enumerate(series['posts'], 1))
        open_attr = ' open' if open_by_default else ''
        class_name = 'series-folder' + (f' {variant}' if variant else '')
        return (
            f'<details class="{class_name}"{open_attr}>'
            f'<summary class="series-folder-summary">'
            f'<span class="series-folder-mark" aria-hidden="true">'
            f'<span class="series-folder-tab"></span><span class="series-folder-body"></span>'
            f'<span class="series-folder-stack"></span></span>'
            f'<span class="series-folder-copy"><span class="series-folder-kicker">系列</span>'
            f'<span class="series-folder-title">{esc(series["title"])}</span>'
            f'<span class="series-folder-meta">{series["count"]} 篇 · {span}</span></span>'
            f'<span class="series-folder-chevron" aria-hidden="true"></span>'
            f'</summary>'
            f'<div class="series-folder-panel"><div class="series-folder-panel-inner">'
            f'<p class="series-folder-blurb">{esc(series["summary"])}</p>'
            f'<div class="series-folder-posts">{cards}</div>'
            f'<a class="series-folder-link" href="/series/{series["id"]}/">打开系列页 '
            f'<span aria-hidden="true">↗</span></a>'
            f'</div></div></details>'
        )

    def news_list(items, limit=3):
        selected = items[:limit]
        if not selected:
            return '<p class="dash-empty">No news yet.</p>'
        rows = []
        for item in selected:
            text = esc(item['text'])
            if item['href']:
                text = f'<a href="{esc(item["href"])}">{text}</a>'
            rows.append(
                f'<li class="news-item"><time datetime="{item["date"]}">{item["date"]}</time>'
                f'<span class="news-text">{text}</span></li>'
            )
        return '<ul class="news-list">' + ''.join(rows) + '</ul>'

    def home_feed():
        latest_series = series_list[:1]
        parts = [series_folder(series) for series in latest_series]
        parts.extend(compact_card(post) for post in standalone[:2])
        return ''.join(parts) or '<p class="dash-empty">No posts yet.</p>'

    def blog_feed():
        parts = [series_folder(series, card='roomy', variant='series-folder-roomy') for series in series_list]
        if standalone:
            if series_list:
                parts.append('<h2 class="blog-section-title">其他文章</h2>')
            parts.append('<div class="post-list">' + blog_rows(standalone) + '</div>')
        elif not series_list:
            parts.append('<div class="post-list">' + EMPTY + '</div>')
        return ''.join(parts)

    home = Template((ROOT / 'templates/home.html').read_text(encoding='utf-8')).substitute(
        news=news_list(news_items, 3),
        feed=home_feed(),
    )
    page('index.html', config['name'], config['description'], home, 'home', extra_assets='<script defer src="/assets/home.js"></script>')
    page(
        'blog/index.html',
        'Blog · ' + config['name'],
        '机器学习笔记。',
        '<div class="page-intro"><h1>Blog</h1></div>'
        '<section class="blog-feed" aria-label="文章与系列">' + blog_feed() + '</section>',
        'blog',
        extra_assets='<script defer src="/assets/home.js"></script>',
    )
    page(
        '404.html',
        '页面未找到 · ' + config['name'],
        '页面未找到',
        '<div class="not-found"><h1>404</h1><p>页面未找到</p><a class="text-link" href="/">回到首页 ↗</a></div>',
    )
    for item in pages:
        body = (
            f'<div class="page-shell"><div class="page-intro"><h1>{esc(item["title"])}</h1>'
            f'<p class="page-lede">{esc(item["summary"])}</p></div>'
            f'<div class="prose page-prose">{item["body"]}</div></div>'
        )
        page(
            f'{item["slug"]}/index.html',
            item['title'] + ' · ' + config['name'],
            item['summary'],
            body,
            item['slug'],
            page_class='site-page',
        )
    for series in series_list:
        cards = ''.join(roomy_card(post, index=i) for i, post in enumerate(series['posts'], 1))
        body = (
            f'<div class="page-intro"><a class="text-link" href="/blog/">← Blog</a>'
            f'<p class="series-page-kicker">系列</p><h1>{esc(series["title"])}</h1>'
            f'<p class="series-page-summary">{esc(series["summary"])}</p></div>'
            f'<section class="series-page-list" aria-label="{esc(series["title"])} 文章">{cards}</section>'
        )
        page(
            f'series/{series["id"]}/index.html',
            series['title'] + ' · ' + config['name'],
            series['summary'],
            body,
            'blog',
        )
    for post in posts:
        toc = '<nav class="toc-links" aria-label="文章目录">' + post['toc'] + '</nav>'
        body = (
            f'<div class="article-layout"><article class="article">'
            f'<a class="text-link" href="/blog/">← 全部文章</a>'
            f'<h1>{esc(post["title"])}</h1>'
            f'<div class="article-meta"><time datetime="{post["date"]}">{post["date"]}</time>'
            f'<span>预计阅读 {post["minutes"]} 分钟</span></div>'
            f'<details class="mobile-toc"><summary>目录</summary>{toc}</details>'
            f'<div class="prose">{post["body"]}</div></article>'
            f'<aside class="desktop-toc"><div class="toc-title">目录</div>{toc}</aside></div>'
        )
        page(
            f'blog/{post["slug"]}/index.html',
            post['title'] + ' · ' + config['name'],
            post['summary'],
            body,
            'blog',
            'article',
        )
    feed = ET.Element('rss', version='2.0')
    channel = ET.SubElement(feed, 'channel')
    for key, value in [
        ('title', config['name']),
        ('link', config['url']),
        ('description', config['description']),
        ('language', 'zh-CN'),
    ]:
        ET.SubElement(channel, key).text = value
    for post in posts:
        item = ET.SubElement(channel, 'item')
        for key, value in [
            ('title', post['title']),
            ('link', config['url'] + '/blog/' + post['slug'] + '/'),
            ('guid', config['url'] + '/blog/' + post['slug'] + '/'),
            ('description', post['summary']),
            ('pubDate', dt.datetime.strptime(post['date'], '%Y-%m-%d').strftime('%a, %d %b %Y 00:00:00 GMT')),
        ]:
            ET.SubElement(item, key).text = value
    write('feed.xml', ET.tostring(feed, encoding='utf-8', xml_declaration=True).decode('utf-8'))
    sitemap = ET.Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
    for path in generated:
        if path.endswith('index.html'):
            entry = ET.SubElement(sitemap, 'url')
            ET.SubElement(entry, 'loc').text = config['url'] + (
                '/' if path == 'index.html' else '/' + path.removesuffix('index.html')
            )
    write('sitemap.xml', ET.tostring(sitemap, encoding='utf-8', xml_declaration=True).decode('utf-8'))
    write('robots.txt', 'User-agent: *\nAllow: /\nSitemap: ' + config['url'] + '/sitemap.xml')
    page_slugs = {p['slug'] for p in pages}
    for obsolete in set(previous) - set(generated):
        if not obsolete.endswith('/index.html') or obsolete == 'index.html':
            continue
        top = obsolete.split('/', 1)[0]
        if (
            obsolete.startswith('blog/')
            or obsolete.startswith('series/')
            or top in page_slugs
        ):
            target = ROOT / obsolete
            if target.exists():
                target.unlink()
    write('generated-files.json', json.dumps(generated, indent=2))
    print(f'构建完成：{len(posts)} 篇已发布文章，{len(pages)} 个页面。')


if __name__ == '__main__':
    build()
