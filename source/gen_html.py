# -*- coding: utf-8 -*-
"""
Bootstrap: parse existing Top100/*.md → generate index.html + Top100/*.html
Run from anywhere: python source/gen_html.py
"""
import os, re, sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(__file__, "../.."))
sys.path.insert(0, os.path.join(ROOT, 'source'))
os.chdir(os.path.join(ROOT, 'source'))

from process import WriteHTML, topics, topics_display

_MD_ROW = re.compile(
    r'^\|\s*\d+\s*\|'
    r'\s*\[([^\]]+)\]\(([^)]+)\)\s*\|'
    r'\s*([\d,]+)\s*\|'
    r'\s*([\d,]+)\s*\|'
    r'\s*([^|]*?)\s*\|'
    r'\s*(\d+)\s*\|'
    r'\s*(.*?)\s*\|'
    r'\s*([\dT:Z\-]+)\s*\|'
)


def parse_md(path: str) -> list:
    repos = []
    if not os.path.exists(path):
        return repos
    with open(path, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f):
            m = _MD_ROW.match(line.strip())
            if not m:
                continue
            name      = m.group(1).strip()
            url       = m.group(2).strip()
            stars     = int(m.group(3).replace(',', ''))
            forks     = int(m.group(4).replace(',', ''))
            lang_raw  = m.group(5).strip()
            issues    = int(m.group(6))
            desc_raw  = m.group(7).strip()
            pushed_at = m.group(8).strip()

            lang = None if not lang_raw or lang_raw.lower() == 'none' else lang_raw
            desc = (desc_raw.replace(r'\|', '|')
                    if desc_raw and desc_raw.lower() != 'none' else None)
            parts = url.rstrip('/').split('/')
            owner = parts[-2] if len(parts) >= 2 else 'unknown'

            repos.append({
                'name': name, 'html_url': url,
                'stargazers_count': stars, 'forks_count': forks,
                'language': lang, 'owner': {'login': owner},
                'open_issues_count': issues,
                'description': desc, 'pushed_at': pushed_at,
                'zh_description': '',
            })
    return repos


def attach_translations(all_lists: list) -> None:
    try:
        from translate import load_cache
        cache = load_cache()
        for repos in all_lists:
            for r in repos:
                desc = (r.get('description') or '').strip()
                if desc and desc in cache and cache[desc] != desc:
                    r['zh_description'] = cache[desc]
    except Exception as e:
        print(f"Translation cache unavailable: {e}")


def main():
    top100 = os.path.join(ROOT, 'Top100')
    repos_stars = parse_md(os.path.join(top100, 'Top-100-stars.md'))
    repos_forks = parse_md(os.path.join(top100, 'Top-100-forks.md'))
    repos_topics = {t: parse_md(os.path.join(top100, f'{t}.md')) for t in topics}

    all_lists = [repos_stars, repos_forks] + list(repos_topics.values())
    attach_translations(all_lists)

    wt = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    WriteHTML(repos_stars, repos_forks, repos_topics, wt).write_all()
    print("Done.")


if __name__ == '__main__':
    main()
