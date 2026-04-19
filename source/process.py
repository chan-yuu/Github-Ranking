# -*- coding: utf-8 -*-
from datetime import datetime
import os
import pandas as pd
import json
from common import get_graphql_data, write_text, write_ranking_repo
import inspect
import html as _html

# ── Topic metadata ───────────────────────────────────────────────────────────

TOPIC_COLORS = {
    "top-100-stars":          "#fbbf24",
    "top-100-forks":          "#60a5fa",
    "Autonomous-Driving":     "#22d3ee",
    "Embodied-AI":            "#34d399",
    "ROS-ROS2":               "#fb923c",
    "Robotics":               "#38bdf8",
    "Humanoid":               "#c084fc",
    "LLM":                    "#a78bfa",
    "AI-Agents":              "#818cf8",
    "Coding-Agents":          "#60a5fa",
    "World-Models":           "#2dd4bf",
    "Multimodal":             "#f472b6",
    "Generative-AI":          "#e879f9",
    "Stable-Diffusion":       "#fb7185",
    "Diffusion-Models":       "#c4b5fd",
    "Video-Generation":       "#f87171",
    "Reinforcement-Learning": "#4ade80",
    "RLHF":                   "#a3e635",
    "VLM":                    "#fbbf24",
    "Foundation-Models":      "#fb923c",
    "AI-Infrastructure":      "#94a3b8",
    "SWE-Agent":              "#7dd3fc",
}

TOPIC_ICONS = {
    "top-100-stars":          "⭐",
    "top-100-forks":          "🍴",
    "Autonomous-Driving":     "🚗",
    "Embodied-AI":            "🦾",
    "ROS-ROS2":               "🤖",
    "Robotics":               "⚙️",
    "Humanoid":               "🧑‍🤖",
    "LLM":                    "💬",
    "AI-Agents":              "🧠",
    "Coding-Agents":          "💻",
    "World-Models":           "🌍",
    "Multimodal":             "👁️",
    "Generative-AI":          "✨",
    "Stable-Diffusion":       "🎨",
    "Diffusion-Models":       "🌊",
    "Video-Generation":       "🎬",
    "Reinforcement-Learning": "🎮",
    "RLHF":                   "⚖️",
    "VLM":                    "👀",
    "Foundation-Models":      "🏗️",
    "AI-Infrastructure":      "🔧",
    "SWE-Agent":              "🛠️",
}


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ── Load configs ─────────────────────────────────────────────────────────────

def load_topics():
    root_path = os.path.abspath(os.path.join(__file__, "../../"))
    with open(os.path.join(root_path, 'topics.json'), 'r', encoding='utf-8') as f:
        return json.load(f)

def load_filters():
    root_path = os.path.abspath(os.path.join(__file__, "../../"))
    fp = os.path.join(root_path, 'filters.json')
    if os.path.exists(fp):
        with open(fp, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"blocked_repos": [], "blocked_keywords": []}

TOPICS_CONFIG     = load_topics()
topics            = [item['id']               for item in TOPICS_CONFIG]
topics_display    = [item['name']             for item in TOPICS_CONFIG]
topics_display_zh = [item.get('name_zh', item['name']) for item in TOPICS_CONFIG]
SAFETY_FILTERS    = load_filters()

table_of_contents = """
* [Most Stars](#most-stars)
* [Most Forks](#most-forks)
""" + "\n".join(
    [f"* [{d}](#{d.lower().replace(' ','-').replace('/','').replace('_','-')})"
     for d in topics_display]
)

# ── GQL Processor ────────────────────────────────────────────────────────────

class ProcessorGQL(object):
    def __init__(self):
        self.gql_format = """query{
    search(query: "%s", type: REPOSITORY, first:%d %s) {
      pageInfo { endCursor }
                edges {
                    node {
                        ...on Repository {
                            id name url forkCount stargazerCount
                            owner { login }
                            description pushedAt
                            primaryLanguage { name }
                            openIssues: issues(states: OPEN) { totalCount }
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

    @staticmethod
    def is_safe(repo_data):
        owner = repo_data['owner']['login'].lower()
        name  = repo_data['name'].lower()
        full  = f"{owner}/{name}"
        for blocked in SAFETY_FILTERS["blocked_repos"]:
            if blocked.lower() in full:
                return False
        desc = repo_data['description'] or ""
        check = f"{name} {desc}".lower()
        for kw in SAFETY_FILTERS["blocked_keywords"]:
            if kw.lower() in check:
                return False
        if "卐" in check or "卍" in check:
            return False
        return True

    def parse_gql_result(self, result):
        res = []
        if not result or "data" not in result or "search" not in result["data"]:
            return res
        for repo in result["data"]["search"]["edges"]:
            rd = repo['node']
            if not self.is_safe(rd):
                continue
            res.append({
                'name':               rd['name'],
                'stargazers_count':   rd['stargazerCount'],
                'forks_count':        rd['forkCount'],
                'language':           rd['primaryLanguage']['name'] if rd['primaryLanguage'] else None,
                'html_url':           rd['url'],
                'owner':              {'login': rd['owner']['login']},
                'open_issues_count':  rd['openIssues']['totalCount'],
                'pushed_at':          rd['pushedAt'],
                'description':        rd['description'],
            })
        return res

    def get_repos(self, qql):
        cursor, repos = '', []
        for _ in range(self.bulk_count):
            res = get_graphql_data(qql % cursor)
            if not res:
                break
            if "data" not in res or not res["data"]["search"]["pageInfo"]["endCursor"]:
                repos += self.parse_gql_result(res)
                break
            cursor = ', after:"' + res["data"]["search"]["pageInfo"]["endCursor"] + '"'
            repos += self.parse_gql_result(res)
        return repos

    def get_all_repos(self):
        print("Get repos of most stars...")
        rs = self.get_repos(self.gql_stars)
        print("Done. Get repos of most forks...")
        rf = self.get_repos(self.gql_forks)
        print("Done.")
        rt = {}
        for topic in topics:
            print(f"Get research repos of {topic}...")
            rt[topic] = self.get_repos(self.gql_topic % (topic, '%s'))
        return rs, rf, rt

# ── Markdown Writer ───────────────────────────────────────────────────────────

class WriteFile(object):
    def __init__(self, repos_stars, repos_forks, repos_topics):
        self.repos_stars  = repos_stars
        self.repos_forks  = repos_forks
        self.repos_topics = repos_topics
        self.col = ['rank','item','repo_name','stars','forks','language','repo_url',
                    'username','issues','last_commit','description']
        self.repo_list = []
        self.repo_list.extend([
            {"title_readme":"Most Stars","title_100":"Top 100 Stars",
             "file_100":"Top-100-stars.md","data":repos_stars,"item":"top-100-stars"},
            {"title_readme":"Most Forks","title_100":"Top 100 Forks",
             "file_100":"Top-100-forks.md","data":repos_forks,"item":"top-100-forks"},
        ])
        for i, topic in enumerate(topics):
            d = topics_display[i]
            self.repo_list.append({
                "title_readme": d,
                "title_100": f"Top 100 Stars in {d}",
                "file_100": f"{topic}.md",
                "data": repos_topics[topic],
                "item": topic,
            })

    @staticmethod
    def write_head_contents():
        wt = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        head = inspect.cleandoc("""[Github Ranking](./README.md)
            ==========

            **Global Github Repository Rankings & AI Research Frontiers.**

            *Last Automatic Update Time: {wt}*

            ## Table of Contents
            """.format(wt=wt)) + "\n" + table_of_contents
        write_text("../README.md", 'w', head)

    def write_readme_lang_md(self):
        os.makedirs('../Top100', exist_ok=True)
        for r in self.repo_list:
            write_text('../README.md', 'a',
                f"\n## {r['title_readme']}\n\nTop 10 repositories, for more click "
                f"**[{r['title_100']}](Top100/{r['file_100']})**\n\n")
            write_ranking_repo('../README.md', 'a', r['data'][:10])
            print(f"Updated {r['title_readme']} section.")
            write_text(f"../Top100/{r['file_100']}", "w",
                f"[Github Ranking](../README.md)\n==========\n\n## {r['title_100']}\n\n")
            write_ranking_repo(f"../Top100/{r['file_100']}", 'a', r['data'])

    def save_to_csv(self):
        dfs = []
        for r in self.repo_list:
            rows = []
            for idx, repo in enumerate(r['data']):
                rows.append([idx+1, r['item'], repo['name'], repo['stargazers_count'],
                             repo['forks_count'], repo['language'], repo['html_url'],
                             repo['owner']['login'], repo['open_issues_count'],
                             repo['pushed_at'], repo['description']])
            if rows:
                dfs.append(pd.DataFrame(rows, columns=self.col))
        if dfs:
            df = pd.concat(dfs, ignore_index=True)
            d  = datetime.utcnow().strftime("%Y-%m-%d")
            os.makedirs('../Data', exist_ok=True)
            df.to_csv(f'../Data/github-ranking-{d}.csv', index=False, encoding='utf-8')

# ── HTML Writer ───────────────────────────────────────────────────────────────

class WriteHTML(object):
    """Generates a modern, bilingual (EN/ZH) static HTML site."""

    def __init__(self, repos_stars, repos_forks, repos_topics, write_time: str):
        self.write_time = write_time
        self.repo_list  = self._build_repo_list(repos_stars, repos_forks, repos_topics)

    @staticmethod
    def _build_repo_list(repos_stars, repos_forks, repos_topics):
        def mk(key, title_en, title_zh, anchor_id, filename, data):
            color  = TOPIC_COLORS.get(key, "#22d3ee")
            return {
                "title_en":     title_en,
                "title_zh":     title_zh,
                "icon":         TOPIC_ICONS.get(key, "📌"),
                "id":           anchor_id,
                "file":         filename,
                "data":         data,
                "color":        color,
                "color_bg":     _hex_to_rgba(color, 0.1),
                "color_border": _hex_to_rgba(color, 0.22),
            }

        repo_list = [
            mk("top-100-stars", "Most Stars",  "最多 Star", "most-stars",  "Top-100-stars.html", repos_stars),
            mk("top-100-forks", "Most Forks",  "最多 Fork", "most-forks",  "Top-100-forks.html", repos_forks),
        ]
        for i, topic in enumerate(topics):
            d  = topics_display[i]
            dz = topics_display_zh[i]
            aid = d.lower().replace(' ', '-').replace('/', '').replace('_', '-')
            repo_list.append(mk(topic, d, dz, aid, f"{topic}.html", repos_topics.get(topic, [])))
        return repo_list

    # ── Utilities ────────────────────────────────────────

    @staticmethod
    def _e(text) -> str:
        return _html.escape(str(text)) if text else ''

    @staticmethod
    def _n(n: int) -> str:
        if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
        if n >= 1_000:     return f"{n/1_000:.1f}k"
        return str(n)

    def _css_vars(self, r: dict) -> str:
        return (f"--section-color:{r['color']};"
                f"--section-bg:{r['color_bg']};"
                f"--section-border:{r['color_border']}")

    # ── Page skeleton ────────────────────────────────────

    def _head(self, title: str, depth: int = 0, section_color: str = None) -> str:
        p    = '../' * depth
        body_style = f' style="--section-color:{section_color}"' if section_color else ''
        return f"""<!DOCTYPE html>
<html lang="zh-CN" data-lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="Global GitHub repository rankings and AI research frontiers.">
  <title>{self._e(title)}</title>
  <link rel="stylesheet" href="{p}assets/css/style.css">
</head>
<body{body_style}>
<div class="bg-fx">
  <div class="bg-glow bg-g1"></div>
  <div class="bg-glow bg-g2"></div>
  <div class="bg-glow bg-g3"></div>
  <div class="bg-grid"></div>
</div>
<div id="sidebar-overlay" class="sidebar-overlay"></div>
<div class="layout">"""

    def _sidebar(self, depth: int = 0) -> str:
        p    = '../' * depth
        home = f"{p}index.html"

        gen_links = ''
        for r in self.repo_list[:2]:
            gen_links += f"""
      <a href="{home}#{r['id']}" class="nav-link" data-section="{r['id']}"
         style="--dot-color:{r['color']}">
        <span class="nav-dot"></span>
        <span class="text-en">{self._e(r['title_en'])}</span
        ><span class="text-zh">{self._e(r['title_zh'])}</span>
      </a>"""

        ai_links = ''
        for r in self.repo_list[2:]:
            ai_links += f"""
      <a href="{home}#{r['id']}" class="nav-link" data-section="{r['id']}"
         style="--dot-color:{r['color']}">
        <span class="nav-dot"></span>
        <span class="text-en">{self._e(r['title_en'])}</span
        ><span class="text-zh">{self._e(r['title_zh'])}</span>
      </a>"""

        return f"""
<aside class="sidebar" id="sidebar">
  <div class="sidebar-header">
    <a href="{home}" class="brand">
      <div class="brand-logo">GR</div>
      <span class="brand-name">Github Ranking</span>
    </a>
  </div>
  <div class="sidebar-search">
    <span class="sidebar-search-icon">⌕</span>
    <input type="search" class="nav-search" id="nav-search"
           placeholder="Jump to category…" aria-label="Search categories">
  </div>
  <div class="sidebar-scroll">
    <nav class="sidebar-nav">
      <div class="nav-group">
        <div class="nav-group-label">
          <span class="text-en">General</span><span class="text-zh">综合排行</span>
        </div>{gen_links}
      </div>
      <div class="nav-group">
        <div class="nav-group-label">
          <span class="text-en">AI Research</span><span class="text-zh">AI 研究领域</span>
        </div>{ai_links}
      </div>
    </nav>
  </div>
</aside>"""

    def _main_open(self) -> str:
        return f"""
<div class="main">
  <header class="topbar">
    <button class="sidebar-toggle" onclick="toggleSidebar()">☰</button>
    <div class="topbar-crumb">
      <span class="crumb-root">Github Ranking</span>
      <span class="crumb-sep"> / </span>
      <span class="crumb-cur" id="crumb-cur"></span>
    </div>
    <span class="live-chip">
      <span class="live-dot"></span>
      {self.write_time[:10]}
    </span>
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

    # ── Table components ─────────────────────────────────

    def _rank_badge(self, idx: int) -> str:
        cls = {1: ' gold', 2: ' silver', 3: ' bronze'}.get(idx, '')
        return f'<span class="rank-n{cls}">{idx}</span>'

    def _repo_row(self, idx: int, repo: dict) -> str:
        en  = self._e(repo.get('description') or '')
        zh  = self._e(repo.get('zh_description') or '')
        lang = repo.get('language') or 'N/A'
        la   = f' data-lang="{self._e(lang)}"' if lang != 'N/A' else ''
        stars = repo['stargazers_count']
        forks = repo['forks_count']
        date  = repo.get('pushed_at', '')

        desc = f'<span class="text-en">{en}</span>'
        if zh:
            desc += f'<span class="text-zh">{zh}</span>'

        row_cls = ' class="rank-first"' if idx == 1 else ''

        return f"""    <tr{row_cls}>
      <td class="col-rank">{self._rank_badge(idx)}</td>
      <td class="col-repo">
        <a href="{self._e(repo['html_url'])}" target="_blank" rel="noopener noreferrer"
           class="repo-link">{self._e(repo['name'])}</a>
        <span class="repo-owner">{self._e(repo['owner']['login'])}</span>
      </td>
      <td class="col-stars" data-val="{stars}"><span class="stars-val">{self._n(stars)}</span></td>
      <td class="col-forks" data-val="{forks}"><span class="forks-val">{self._n(forks)}</span></td>
      <td class="col-language"><span class="lang-badge"{la}>{self._e(lang)}</span></td>
      <td class="col-issues" data-val="{repo['open_issues_count']}">{repo['open_issues_count']}</td>
      <td class="col-desc">{desc}</td>
      <td class="col-commit" data-date="{self._e(date)}" data-val="{self._e(date)}">{date[:10]}</td>
    </tr>"""

    def _table(self, repos: list, table_id: str = 'tbl') -> str:
        rows = '\n'.join(self._repo_row(i + 1, r) for i, r in enumerate(repos))
        return f"""<div class="table-card">
  <table class="ranking-table" id="{table_id}">
    <thead>
      <tr>
        <th class="col-rank">#</th>
        <th class="col-repo">
          <span class="text-en">Repository</span><span class="text-zh">仓库</span>
        </th>
        <th class="col-stars  sortable" data-col="2">Stars</th>
        <th class="col-forks  sortable" data-col="3">Forks</th>
        <th class="col-language">
          <span class="text-en">Language</span><span class="text-zh">语言</span>
        </th>
        <th class="col-issues sortable" data-col="5">Issues</th>
        <th class="col-desc">
          <span class="text-en">Description</span><span class="text-zh">描述</span>
        </th>
        <th class="col-commit sortable" data-col="7">
          <span class="text-en">Last Commit</span><span class="text-zh">最后提交</span>
        </th>
      </tr>
    </thead>
    <tbody>
{rows}
    </tbody>
  </table>
  <div class="no-results">
    <span class="text-en">No repositories match your search</span>
    <span class="text-zh">没有匹配的仓库</span>
  </div>
</div>"""

    # ── Index page ───────────────────────────────────────

    def write_index(self) -> None:
        total = len(self.repo_list)
        est   = sum(min(len(r['data']), 100) for r in self.repo_list)

        hero = f"""<div class="hero">
  <p class="hero-eyebrow">GitHub Observatory</p>
  <h1 class="hero-title">
    <span class="grad-text">Discover</span> the World's<br>
    <span class="text-en">Top Open Source Projects</span
    ><span class="text-zh">顶尖开源项目</span>
  </h1>
  <p class="hero-sub">
    <span class="text-en">Global GitHub repository rankings &amp; AI research
      frontiers — curated and updated daily.</span>
    <span class="text-zh">全球 GitHub 仓库排行榜 &amp; AI 研究前沿，每日自动更新。</span>
  </p>
  <div class="hero-stats">
    <div class="hero-stat">
      <span class="hero-stat-num" data-count="{total}" data-suffix="">0</span>
      <span class="hero-stat-label text-en">Categories</span>
      <span class="hero-stat-label text-zh">分类</span>
    </div>
    <div class="hero-stat">
      <span class="hero-stat-num" data-count="{est}" data-suffix="+">0+</span>
      <span class="hero-stat-label text-en">Repositories</span>
      <span class="hero-stat-label text-zh">仓库</span>
    </div>
    <div class="hero-stat">
      <span class="hero-stat-num">{self.write_time[:10]}</span>
      <span class="hero-stat-label text-en">Last Updated</span>
      <span class="hero-stat-label text-zh">最后更新</span>
    </div>
  </div>
</div>"""

        sections = []
        for r in self.repo_list:
            tbl_id = f"tbl-{r['id']}"
            cvars  = self._css_vars(r)
            n      = min(len(r['data']), 10)
            section = f"""<section id="{r['id']}" class="ranking-section" style="{cvars}">
  <div class="section-hd">
    <div class="section-hd-left">
      <div class="section-icon">{r['icon']}</div>
      <div>
        <h2 class="section-title">
          <span class="text-en">{self._e(r['title_en'])}</span
          ><span class="text-zh">{self._e(r['title_zh'])}</span>
          <span class="section-pill">Top {n}</span>
        </h2>
        <p class="section-sub">
          <span class="text-en">Top {n} repos · updated {self.write_time[:10]}</span>
          <span class="text-zh">前 {n} 个仓库 · 更新于 {self.write_time[:10]}</span>
        </p>
      </div>
    </div>
    <div class="section-actions">
      <div class="search-wrap">
        <span class="search-icon">⌕</span>
        <input type="search" class="table-search"
               data-table="{tbl_id}" placeholder="Filter…" aria-label="Filter">
      </div>
      <a href="Top100/{r['file']}" class="see-all-btn">
        <span class="text-en">See all 100 →</span>
        <span class="text-zh">查看全部 100 →</span>
      </a>
    </div>
  </div>
  {self._table(r['data'][:10], tbl_id)}
</section>"""
            sections.append(section)

        html = (
            self._head("Github Ranking — Global Rankings & AI Research", depth=0) +
            self._sidebar(depth=0) +
            self._main_open() +
            hero + '\n' +
            '\n'.join(sections) +
            self._foot(depth=0)
        )
        with open('../index.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("Generated index.html")

    # ── Top100 pages ─────────────────────────────────────

    def write_top100(self) -> None:
        os.makedirs('../Top100', exist_ok=True)
        for r in self.repo_list:
            tbl_id = f"tbl-{r['id']}-100"
            cvars  = self._css_vars(r)
            n      = len(r['data'])

            page_hd = f"""<div class="page-hd" style="{cvars}">
  <a href="../index.html#{r['id']}" class="back-link">
    <span class="text-en">Back to Rankings</span
    ><span class="text-zh">返回排行榜</span>
  </a>
  <h1 class="page-title">
    <span class="page-icon">{r['icon']}</span>
    <span class="text-en">Top 100 · {self._e(r['title_en'])}</span
    ><span class="text-zh">前 100 · {self._e(r['title_zh'])}</span>
  </h1>
  <p class="page-sub">
    <span class="text-en">{n} repositories sorted by {r['title_en'].lower()}</span>
    <span class="text-zh">按 {r['title_zh']} 排序，共 {n} 个仓库</span>
  </p>
  <div class="page-meta">
    <div class="search-wrap">
      <span class="search-icon">⌕</span>
      <input type="search" class="table-search"
             data-table="{tbl_id}" placeholder="Filter…" aria-label="Filter">
    </div>
    <span class="page-stat">📦 {n} <span class="text-en">repos</span
      ><span class="text-zh">个仓库</span></span>
    <span class="page-stat">🕐 {self.write_time[:10]}</span>
  </div>
</div>
<div class="tbl-wrap" style="{cvars}">
  {self._table(r['data'], tbl_id)}
</div>"""

            html = (
                self._head(f"Top 100 · {r['title_en']}", depth=1,
                           section_color=r['color']) +
                self._sidebar(depth=1) +
                self._main_open() +
                page_hd +
                self._foot(depth=1)
            )
            with open(f"../Top100/{r['file']}", 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"Generated Top100/{r['file']}")

    def write_all(self) -> None:
        self.write_index()
        self.write_top100()

# ── Entry point ───────────────────────────────────────────────────────────────

def run_by_gql():
    ROOT_PATH = os.path.abspath(os.path.join(__file__, "../../"))
    os.chdir(os.path.join(ROOT_PATH, 'source'))

    processor = ProcessorGQL()
    repos_stars, repos_forks, repos_topics = processor.get_all_repos()

    # Translate descriptions
    try:
        from translate import load_cache, save_cache, enrich_with_translations
        cache = load_cache()
        all_lists = [repos_stars, repos_forks] + list(repos_topics.values())
        cache = enrich_with_translations(all_lists, cache)
        save_cache(cache)
    except Exception as e:
        print(f"Translation skipped ({e}). HTML will show English descriptions only.")

    write_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Markdown (for GitHub repo display)
    wt = WriteFile(repos_stars, repos_forks, repos_topics)
    wt.write_head_contents()
    wt.write_readme_lang_md()
    wt.save_to_csv()

    # HTML (for GitHub Pages)
    WriteHTML(repos_stars, repos_forks, repos_topics, write_time).write_all()


if __name__ == "__main__":
    run_by_gql()
