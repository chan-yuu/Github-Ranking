# -*- coding: utf-8 -*-
from datetime import datetime
import os
import pandas as pd
import json
from common import get_graphql_data, write_text, write_ranking_repo
import inspect
import html as html_module

# ── Load configs ────────────────────────────────────────────────────────────

def load_topics():
    root_path = os.path.abspath(os.path.join(__file__, "../../"))
    config_path = os.path.join(root_path, 'topics.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def load_filters():
    root_path = os.path.abspath(os.path.join(__file__, "../../"))
    filter_path = os.path.join(root_path, 'filters.json')
    if os.path.exists(filter_path):
        with open(filter_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"blocked_repos": [], "blocked_keywords": []}

TOPICS_CONFIG   = load_topics()
topics          = [item['id']      for item in TOPICS_CONFIG]
topics_display  = [item['name']    for item in TOPICS_CONFIG]
topics_display_zh = [item.get('name_zh', item['name']) for item in TOPICS_CONFIG]
SAFETY_FILTERS  = load_filters()

table_of_contents = """
* [Most Stars](#most-stars)
* [Most Forks](#most-forks)
""" + "\n".join(
    [f"* [{display}](#{display.lower().replace(' ', '-').replace('/', '')})"
     for display in topics_display]
)

# ── GQL Processor ───────────────────────────────────────────────────────────

class ProcessorGQL(object):
    def __init__(self):
        self.gql_format = """query{
    search(query: "%s", type: REPOSITORY, first:%d %s) {
      pageInfo { endCursor }
                edges {
                    node {
                        ...on Repository {
                            id
                            name
                            url
                            forkCount
                            stargazerCount
                            owner {
                                login
                            }
                            description
                            pushedAt
                            primaryLanguage {
                                name
                            }
                            openIssues: issues(states: OPEN) {
                                totalCount
                            }
                        }
                    }
                }
            }
        }
        """
        self.bulk_size  = 50
        self.bulk_count = 2
        self.gql_stars  = self.gql_format % ("stars:>1000 sort:stars", self.bulk_size, "%s")
        self.gql_forks  = self.gql_format % ("forks:>1000 sort:forks", self.bulk_size, "%s")
        self.gql_topic  = self.gql_format % ("%s stars:>100 sort:stars", self.bulk_size, "%s")
        self.col = ['rank', 'item', 'repo_name', 'stars', 'forks', 'language', 'repo_url',
                    'username', 'issues', 'last_commit', 'description']

    @staticmethod
    def is_safe(repo_data):
        owner_login = repo_data['owner']['login'].lower()
        repo_name   = repo_data['name'].lower()
        full_name   = f"{owner_login}/{repo_name}"
        for blocked in SAFETY_FILTERS["blocked_repos"]:
            if blocked.lower() in full_name:
                return False
        desc = repo_data['description'] if repo_data['description'] else ""
        content_to_check = f"{repo_name} {desc}".lower()
        for keyword in SAFETY_FILTERS["blocked_keywords"]:
            if keyword.lower() in content_to_check:
                return False
        if "卐" in content_to_check or "卍" in content_to_check:
            return False
        return True

    def parse_gql_result(self, result):
        res = []
        if not result or "data" not in result or "search" not in result["data"]:
            return res
        for repo in result["data"]["search"]["edges"]:
            repo_data = repo['node']
            if not self.is_safe(repo_data):
                continue
            res.append({
                'name': repo_data['name'],
                'stargazers_count': repo_data['stargazerCount'],
                'forks_count': repo_data['forkCount'],
                'language': repo_data['primaryLanguage']['name'] if repo_data['primaryLanguage'] else None,
                'html_url': repo_data['url'],
                'owner': {'login': repo_data['owner']['login']},
                'open_issues_count': repo_data['openIssues']['totalCount'],
                'pushed_at': repo_data['pushedAt'],
                'description': repo_data['description'],
            })
        return res

    def get_repos(self, qql):
        cursor = ''
        repos = []
        for _ in range(self.bulk_count):
            res = get_graphql_data(qql % cursor)
            if not res:
                break
            repos_gql = res
            if "data" not in repos_gql or not repos_gql["data"]["search"]["pageInfo"]["endCursor"]:
                repos += self.parse_gql_result(repos_gql)
                break
            cursor = ', after:"' + repos_gql["data"]["search"]["pageInfo"]["endCursor"] + '"'
            repos += self.parse_gql_result(repos_gql)
        return repos

    def get_all_repos(self):
        print("Get repos of most stars...")
        repos_stars = self.get_repos(self.gql_stars)
        print("Get repos of most stars success!")
        print("Get repos of most forks...")
        repos_forks = self.get_repos(self.gql_forks)
        print("Get repos of most forks success!")
        repos_topics = {}
        for topic in topics:
            print(f"Get research repos of {topic}...")
            repos_topics[topic] = self.get_repos(self.gql_topic % (topic, '%s'))
        return repos_stars, repos_forks, repos_topics

# ── Markdown Writer (kept for GitHub display) ────────────────────────────────

class WriteFile(object):
    def __init__(self, repos_stars, repos_forks, repos_topics):
        self.repos_stars  = repos_stars
        self.repos_forks  = repos_forks
        self.repos_topics = repos_topics
        self.col = ['rank', 'item', 'repo_name', 'stars', 'forks', 'language', 'repo_url',
                    'username', 'issues', 'last_commit', 'description']
        self.repo_list = []
        self.repo_list.extend([{
            "desc": "Stars", "desc_md": "Stars",
            "title_readme": "Most Stars", "title_100": "Top 100 Stars",
            "file_100": "Top-100-stars.md", "data": repos_stars, "item": "top-100-stars",
        }, {
            "desc": "Forks", "desc_md": "Forks",
            "title_readme": "Most Forks", "title_100": "Top 100 Forks",
            "file_100": "Top-100-forks.md", "data": repos_forks, "item": "top-100-forks",
        }])
        for i in range(len(topics)):
            topic   = topics[i]
            display = topics_display[i]
            self.repo_list.append({
                "desc": "Stars", "desc_md": "Stars",
                "title_readme": display,
                "title_100": f"Top 100 Stars in {display}",
                "file_100": f"{topic}.md",
                "data": repos_topics[topic],
                "item": topic,
            })

    @staticmethod
    def write_head_contents():
        write_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        head_contents = inspect.cleandoc("""[Github Ranking](./README.md)
            ==========

            **Global Github Repository Rankings & AI Research Frontiers.**

            *Last Automatic Update Time: {write_time}*

            ## Table of Contents
            """.format(write_time=write_time)) + "\n" + table_of_contents
        write_text("../README.md", 'w', head_contents)

    def write_readme_lang_md(self):
        os.makedirs('../Top100', exist_ok=True)
        for repo in self.repo_list:
            title_readme = repo["title_readme"]
            title_100    = repo["title_100"]
            file_100     = repo["file_100"]
            data         = repo["data"]
            write_text('../README.md', 'a',
                       f"\n## {title_readme}\n\nTop 10 repositories, for more click **[{title_100}](Top100/{file_100})**\n\n")
            write_ranking_repo('../README.md', 'a', data[:10])
            print(f"Updated {title_readme} section.")
            write_text(f"../Top100/{file_100}", "w",
                       f"[Github Ranking](../README.md)\n==========\n\n## {title_100}\n\n")
            write_ranking_repo(f"../Top100/{file_100}", 'a', data)

    def save_to_csv(self):
        dfs = []
        for repo in self.repo_list:
            df_repos = []
            for idx, r in enumerate(repo["data"]):
                df_repos.append([
                    idx + 1, repo["item"], r['name'], r['stargazers_count'], r['forks_count'],
                    r['language'], r['html_url'], r['owner']['login'],
                    r['open_issues_count'], r['pushed_at'], r['description']
                ])
            if df_repos:
                dfs.append(pd.DataFrame(df_repos, columns=self.col))
        if dfs:
            df_all = pd.concat(dfs, ignore_index=True)
            save_date = datetime.utcnow().strftime("%Y-%m-%d")
            os.makedirs('../Data', exist_ok=True)
            df_all.to_csv('../Data/github-ranking-' + save_date + '.csv', index=False, encoding='utf-8')

# ── HTML Writer ──────────────────────────────────────────────────────────────

class WriteHTML(object):
    """Generates a modern, bilingual (EN/ZH) static HTML site."""

    def __init__(self, repos_stars, repos_forks, repos_topics, write_time: str):
        self.write_time = write_time
        self.repo_list  = self._build_repo_list(repos_stars, repos_forks, repos_topics)

    @staticmethod
    def _build_repo_list(repos_stars, repos_forks, repos_topics):
        repo_list = [{
            "title_en": "Most Stars",
            "title_zh": "最多 Star",
            "icon":     "⭐",
            "id":       "most-stars",
            "file":     "Top-100-stars.html",
            "data":     repos_stars,
        }, {
            "title_en": "Most Forks",
            "title_zh": "最多 Fork",
            "icon":     "🍴",
            "id":       "most-forks",
            "file":     "Top-100-forks.html",
            "data":     repos_forks,
        }]
        for i, topic in enumerate(topics):
            display    = topics_display[i]
            display_zh = topics_display_zh[i]
            anchor_id  = display.lower().replace(' ', '-').replace('/', '').replace('_', '-')
            repo_list.append({
                "title_en": display,
                "title_zh": display_zh,
                "icon":     "🔬",
                "id":       anchor_id,
                "file":     f"{topic}.html",
                "data":     repos_topics.get(topic, []),
            })
        return repo_list

    # ── Helpers ──────────────────────────────────────────────

    @staticmethod
    def _esc(text: str) -> str:
        return html_module.escape(str(text)) if text else ''

    @staticmethod
    def _fmt_num(n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.1f}k"
        return str(n)

    def _head(self, title: str, depth: int = 0) -> str:
        p = '../' * depth
        return f"""<!DOCTYPE html>
<html lang="zh-CN" data-lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="Global GitHub repository rankings and AI research frontiers.">
  <title>{self._esc(title)}</title>
  <link rel="stylesheet" href="{p}assets/css/style.css">
</head>
<body>
<div id="sidebar-overlay" class="sidebar-overlay"></div>
<div class="layout">"""

    def _sidebar(self, depth: int = 0) -> str:
        p = '../' * depth
        home = f"{p}index.html"

        general_links = ""
        for r in self.repo_list[:2]:
            general_links += f"""
      <a href="{home}#{r['id']}" class="nav-link" data-section="{r['id']}">
        {r['icon']}&nbsp;<span class="text-en">{self._esc(r['title_en'])}</span
        ><span class="text-zh">{self._esc(r['title_zh'])}</span>
      </a>"""

        topic_links = ""
        for r in self.repo_list[2:]:
            topic_links += f"""
      <a href="{home}#{r['id']}" class="nav-link" data-section="{r['id']}">
        {r['icon']}&nbsp;<span class="text-en">{self._esc(r['title_en'])}</span
        ><span class="text-zh">{self._esc(r['title_zh'])}</span>
      </a>"""

        return f"""
<aside class="sidebar" id="sidebar">
  <div class="sidebar-header">
    <a href="{home}" class="brand">
      <span class="brand-icon">🏆</span>
      <span class="brand-text">Github Ranking</span>
    </a>
  </div>
  <nav class="sidebar-nav">
    <div class="nav-group">
      <div class="nav-group-title">
        <span class="text-en">General</span><span class="text-zh">综合排行</span>
      </div>{general_links}
    </div>
    <div class="nav-group">
      <div class="nav-group-title">
        <span class="text-en">AI Research</span><span class="text-zh">AI 研究领域</span>
      </div>{topic_links}
    </div>
  </nav>
</aside>"""

    def _main_open(self) -> str:
        date_str = self.write_time[:10]
        return f"""
<div class="main">
  <header class="topbar">
    <button class="sidebar-toggle" onclick="toggleSidebar()">☰</button>
    <div class="topbar-center">
      <span class="text-en">Global GitHub Rankings &amp; AI Research Frontiers</span>
      <span class="text-zh">全球 GitHub 仓库排行榜 &amp; AI 研究前沿</span>
      <span class="update-badge">{date_str}</span>
    </div>
    <button class="lang-btn" id="lang-btn" onclick="toggleLang()">中文</button>
  </header>
  <main class="content">"""

    def _foot(self, depth: int = 0) -> str:
        p = '../' * depth
        return f"""
  </main>
</div>
</div>
<button class="back-to-top" id="back-to-top" onclick="scrollToTop()">↑</button>
<script src="{p}assets/js/main.js"></script>
</body>
</html>"""

    def _rank_badge(self, idx: int) -> str:
        cls = ''
        if idx == 1: cls = ' top1'
        elif idx == 2: cls = ' top2'
        elif idx == 3: cls = ' top3'
        return f'<span class="rank-badge{cls}">{idx}</span>'

    def _repo_row(self, idx: int, repo: dict) -> str:
        en_desc = self._esc(repo.get('description') or '')
        zh_desc = self._esc(repo.get('zh_description') or '')
        lang    = repo.get('language') or 'N/A'
        lang_attr = f' data-lang="{self._esc(lang)}"' if lang != 'N/A' else ''
        stars   = self._fmt_num(repo['stargazers_count'])
        forks   = self._fmt_num(repo['forks_count'])
        date    = repo.get('pushed_at', '')
        date_display = date[:10] if date else ''

        desc_html = f'<span class="text-en">{en_desc}</span>'
        if zh_desc:
            desc_html += f'<span class="text-zh">{zh_desc}</span>'

        return f"""    <tr>
      <td class="col-rank">{self._rank_badge(idx)}</td>
      <td class="col-repo">
        <a href="{self._esc(repo['html_url'])}" target="_blank" rel="noopener noreferrer"
           class="repo-name-link">{self._esc(repo['name'])}</a>
        <span class="repo-owner">{self._esc(repo['owner']['login'])}</span>
      </td>
      <td class="col-stars"><span class="stars-val">⭐ {stars}</span></td>
      <td class="col-forks"><span class="forks-val">🍴 {forks}</span></td>
      <td class="col-language"><span class="lang-badge"{lang_attr}>{self._esc(lang)}</span></td>
      <td class="col-issues">{repo['open_issues_count']}</td>
      <td class="col-desc">{desc_html}</td>
      <td class="col-commit" data-date="{self._esc(date)}">{date_display}</td>
    </tr>"""

    def _table(self, repos: list) -> str:
        rows = '\n'.join(self._repo_row(i + 1, r) for i, r in enumerate(repos))
        return f"""<div class="table-wrapper">
  <table class="ranking-table">
    <thead>
      <tr>
        <th class="col-rank">#</th>
        <th class="col-repo">
          <span class="text-en">Repository</span><span class="text-zh">仓库</span>
        </th>
        <th class="col-stars">Stars</th>
        <th class="col-forks">Forks</th>
        <th class="col-language">
          <span class="text-en">Language</span><span class="text-zh">语言</span>
        </th>
        <th class="col-issues">Issues</th>
        <th class="col-desc">
          <span class="text-en">Description</span><span class="text-zh">描述</span>
        </th>
        <th class="col-commit">
          <span class="text-en">Last Commit</span><span class="text-zh">最后提交</span>
        </th>
      </tr>
    </thead>
    <tbody>
{rows}
    </tbody>
  </table>
</div>"""

    # ── Page generators ──────────────────────────────────────

    def _write(self, path: str, content: str) -> None:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def write_index(self) -> None:
        total_sections = len(self.repo_list)
        hero = f"""<div class="hero">
  <h1 class="hero-title">🏆 Github Ranking</h1>
  <p class="hero-sub">
    <span class="text-en">Global GitHub Repository Rankings &amp; AI Research Frontiers</span>
    <span class="text-zh">全球 GitHub 仓库排行榜 &amp; AI 研究前沿</span>
  </p>
  <div class="hero-meta">
    <span class="hero-stat">📊 <span class="text-en">{total_sections} Categories</span><span class="text-zh">{total_sections} 个分类</span></span>
    <span class="hero-stat">🕐 <span class="text-en">Updated {self.write_time[:10]}</span><span class="text-zh">更新于 {self.write_time[:10]}</span></span>
    <span class="hero-stat">🤖 <span class="text-en">AI Research Focus</span><span class="text-zh">聚焦 AI 研究领域</span></span>
  </div>
</div>"""

        sections = []
        for r in self.repo_list:
            top100_link = f"Top100/{r['file']}"
            section = f"""<section id="{r['id']}" class="ranking-section">
  <div class="section-header">
    <h2 class="section-title">
      <span class="section-icon">{r['icon']}</span>
      <span class="text-en">{self._esc(r['title_en'])}</span>
      <span class="text-zh">{self._esc(r['title_zh'])}</span>
    </h2>
    <a href="{top100_link}" class="see-all">
      <span class="text-en">See all 100 →</span>
      <span class="text-zh">查看全部 100 →</span>
    </a>
  </div>
  {self._table(r['data'][:10])}
</section>"""
            sections.append(section)

        content = (
            self._head("Github Ranking — Global Rankings & AI Research", depth=0) +
            self._sidebar(depth=0) +
            self._main_open() +
            hero + '\n' +
            '\n'.join(sections) +
            self._foot(depth=0)
        )
        self._write('../index.html', content)
        print("Generated index.html")

    def write_top100(self) -> None:
        os.makedirs('../Top100', exist_ok=True)
        for r in self.repo_list:
            count     = len(r['data'])
            title_en  = f"Top 100 · {r['title_en']}"
            title_zh  = f"前 100 · {r['title_zh']}"
            page_header = f"""<div class="page-header">
  <a href="../index.html#{r['id']}" class="back-link">
    ← <span class="text-en">Back to Rankings</span><span class="text-zh">返回排行榜</span>
  </a>
  <h1 class="page-title">
    {r['icon']} <span class="text-en">{self._esc(title_en)}</span
    ><span class="text-zh">{self._esc(title_zh)}</span>
  </h1>
  <p class="page-subtitle">
    <span class="text-en">Showing top {count} repositories sorted by {r['title_en'].lower()}</span>
    <span class="text-zh">按 {r['title_zh']} 排序，共展示 {count} 个仓库</span>
  </p>
  <div class="page-stats">
    <span class="page-stat">📦 {count} <span class="text-en">repositories</span><span class="text-zh">个仓库</span></span>
    <span class="page-stat">🕐 <span class="text-en">Updated {self.write_time[:10]}</span><span class="text-zh">更新于 {self.write_time[:10]}</span></span>
  </div>
</div>"""
            content = (
                self._head(title_en, depth=1) +
                self._sidebar(depth=1) +
                self._main_open() +
                page_header +
                self._table(r['data']) +
                self._foot(depth=1)
            )
            self._write(f"../Top100/{r['file']}", content)
            print(f"Generated Top100/{r['file']}")

    def write_all(self) -> None:
        self.write_index()
        self.write_top100()

# ── Entry point ──────────────────────────────────────────────────────────────

def run_by_gql():
    ROOT_PATH = os.path.abspath(os.path.join(__file__, "../../"))
    os.chdir(os.path.join(ROOT_PATH, 'source'))

    processor = ProcessorGQL()
    repos_stars, repos_forks, repos_topics = processor.get_all_repos()

    # ── Translate descriptions ────────────────────────────────
    try:
        from translate import load_cache, save_cache, enrich_with_translations
        cache = load_cache()
        all_lists = [repos_stars, repos_forks] + list(repos_topics.values())
        cache = enrich_with_translations(all_lists, cache)
        save_cache(cache)
    except Exception as e:
        print(f"Translation skipped ({e}). HTML will show English descriptions only.")

    write_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # ── Generate Markdown (README + Top100/*.md for GitHub display) ──
    wt_obj = WriteFile(repos_stars, repos_forks, repos_topics)
    wt_obj.write_head_contents()
    wt_obj.write_readme_lang_md()
    wt_obj.save_to_csv()

    # ── Generate HTML (GitHub Pages) ─────────────────────────
    html_obj = WriteHTML(repos_stars, repos_forks, repos_topics, write_time)
    html_obj.write_all()


if __name__ == "__main__":
    run_by_gql()
