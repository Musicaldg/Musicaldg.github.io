"""Check published page links, directory anchors and every math expression."""
import json
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.equations = set(), [], []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            assert attrs['id'] not in self.ids, '重复的章节标识'
            self.ids.add(attrs['id'])
        for key in ('href', 'src'):
            if key in attrs:
                self.links.append(attrs[key])
        classes = attrs.get('class', '').split()
        if 'math' in classes:
            self.current = {'tex': '', 'displayMode': 'math-block' in classes}

    def handle_data(self, data):
        if self.current is not None:
            self.current['tex'] += data

    def handle_endtag(self, tag):
        if self.current is not None and tag in ('span', 'div'):
            self.equations.append(self.current)
            self.current = None


equations = []
for name in json.loads((ROOT / 'generated-files.json').read_text()):
    if not name.endswith('.html'):
        continue
    path = ROOT / name
    page = Page()
    page.feed(path.read_text(encoding='utf-8'))
    equations.extend(page.equations)
    for link in page.links:
        url = urlsplit(link)
        if url.scheme or url.netloc:
            continue
        if url.path:
            target = ROOT / url.path.lstrip('/') if url.path.startswith('/') else path.parent / url.path
            assert target.exists(), f'{name}: 缺失文件 {link}'
        elif url.fragment:
            assert url.fragment in page.ids, f'{name}: 缺失目录锚点 {link}'
subprocess.run(['node', str(ROOT / 'scripts/check-math.js')], input=json.dumps(equations), text=True, check=True)
print('本地链接与目录锚点检查通过。')
