# -*- coding: utf-8 -*-
"""
Bootstrap script: parse existing Top100/*.md files and generate
index.html + Top100/*.html without needing the GitHub API token.
Run from the repo root: python source/gen_html.py
"""
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(__file__, "../.."))
sys.path.insert(0, os.path.join(ROOT, 'source'))
os.chdir(os.path.join(ROOT, 'source'))

from process import WriteHTML, load_topics, topics, topics_display, topics_display_zh


_MD_ROW = re.compile(
    r'^\|\s*(\d+)\s*\|'           # rank
    r'\s*\[([^\]]+)\]\(([^)]+)\)\s*\|'  # [name](url)
    r'\s*([\d,]+)\s*\|'           # stars
    r'\s*([\d,]+)\s*\|'           # forks
    r'\s*([^|]*?)\s*\|'           # language
    r'\s*(\d+)\s*\|'              # issues
    r'\s*(.*?)\s*\|'              # description
    r'\s*([\dT:Z-]+)\s*\|'        # pushed_at
)


def parse_md(filepath: str) -> list:
    repos = []
    if not os.path.exists(filepath):
        return repos
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            m = _MD_ROW.match(line.strip())
            if not m:
                continue
            name_raw  = m.group(2).strip()
            url       = m.group(3).strip()
            stars     = int(m.group(4).replace(',', ''))
            forks     = int(m.group(5).replace(',', ''))
            lang_raw  = m.group(6).strip() or None
            issues    = int(m.group(7))
            desc_raw  = m.group(8).strip()
            pushed_at = m.group(9).strip()

            # unescape escaped pipe
            desc = desc_raw.replace(r'\|', '|') if desc_raw and desc_raw != 'None' else None
            lang = None if not lang_raw or lang_raw.lower() == 'none' else lang_raw

            # extract owner from url (https://github.com/owner/repo)
            parts = url.rstrip('/').split('/')
            owner = parts[-2] if len(parts) >= 2 else 'unknown'

            repos.append({
                'name': name_raw,
                'html_url': url,
                'stargazers_count': stars,
                'forks_count': forks,
                'language': lang,
                'owner': {'login': owner},
                'open_issues_count': issues,
                'description': desc,
                'pushed_at': pushed_at,
                'zh_description': '',  # will be filled from cache if available
            })
    return repos


def load_translations(repos_list: list) -> None:
    """Attach zh_description from cache if available."""
    try:
        from translate import load_cache
        cache = load_cache()
        for repos in repos_list:
            for r in repos:
                desc = (r.get('description') or '').strip()
                if desc and desc in cache and cache[desc] != desc:
                    r['zh_description'] = cache[desc]
    except Exception as e:
        print(f"Translation cache not loaded: {e}")


def main():
    top100_dir = os.path.join(ROOT, 'Top100')

    # Stars / Forks
    repos_stars = parse_md(os.path.join(top100_dir, 'Top-100-stars.md'))
    repos_forks = parse_md(os.path.join(top100_dir, 'Top-100-forks.md'))

    # Topics
    repos_topics = {}
    for i, topic_id in enumerate(topics):
        repos_topics[topic_id] = parse_md(os.path.join(top100_dir, f'{topic_id}.md'))

    all_lists = [repos_stars, repos_forks] + list(repos_topics.values())
    load_translations(all_lists)

    write_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    writer = WriteHTML(repos_stars, repos_forks, repos_topics, write_time)
    writer.write_all()
    print("Done! index.html and Top100/*.html generated.")


if __name__ == '__main__':
    main()
