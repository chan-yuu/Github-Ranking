# -*- coding: utf-8 -*-
from datetime import datetime
import os
import pandas as pd
import json
from common import get_graphql_data, write_text, write_ranking_repo
import inspect

# 加载研究领域配置
def load_topics():
    root_path = os.path.abspath(os.path.join(__file__, "../../"))
    config_path = os.path.join(root_path, 'topics.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

# 加载过滤器配置
def load_filters():
    root_path = os.path.abspath(os.path.join(__file__, "../../"))
    filter_path = os.path.join(root_path, 'filters.json')
    if os.path.exists(filter_path):
        with open(filter_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"blocked_repos": [], "blocked_keywords": []}

TOPICS_CONFIG = load_topics()
topics = [item['id'] for item in TOPICS_CONFIG]
topics_display = [item['name'] for item in TOPICS_CONFIG]
SAFETY_FILTERS = load_filters()

table_of_contents = "\n".join([f"* [{display}](#{display.lower().replace(' ', '-').replace('/', '')})" for display in topics_display])


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
        self.bulk_size = 50
        self.bulk_count = 2
        self.gql_topic = self.gql_format % ("%s stars:>100 sort:stars", self.bulk_size, "%s")
        self.col = ['rank', 'item', 'repo_name', 'stars', 'forks', 'language', 'repo_url', 'username', 'issues',
                    'last_commit', 'description']

    @staticmethod
    def is_safe(repo_data):
        # 1. 检查黑名单仓库全名
        full_name = f"{repo_data['owner']['login']}/{repo_data['name']}".lower()
        for blocked in SAFETY_FILTERS["blocked_repos"]:
            if blocked.lower() in full_name:
                return False
        
        # 2. 检查名称和描述中的敏感词
        desc = repo_data['description'] if repo_data['description'] else ""
        content_to_check = f"{repo_data['name']} {desc}".lower()
        for keyword in SAFETY_FILTERS["blocked_keywords"]:
            if keyword.lower() in content_to_check:
                return False
        
        # 3. 排除过于明显的特殊符号
        if "卐" in content_to_check or "卍" in content_to_check:
            return False
            
        return True

    def parse_gql_result(self, result):
        res = []
        if not result or "data" not in result or "search" not in result["data"]:
            return res
        for repo in result["data"]["search"]["edges"]:
            repo_data = repo['node']
            
            # 执行安全过滤
            if not self.is_safe(repo_data):
                continue

            res.append({
                'name': repo_data['name'],
                'stargazers_count': repo_data['stargazerCount'],
                'forks_count': repo_data['forkCount'],
                'language': repo_data['primaryLanguage']['name'] if repo_data['primaryLanguage'] is not None else None,
                'html_url': repo_data['url'],
                'owner': {
                    'login': repo_data['owner']['login'],
                },
                'open_issues_count': repo_data['openIssues']['totalCount'],
                'pushed_at': repo_data['pushedAt'],
                'description': repo_data['description']
            })
        return res

    def get_repos(self, qql):
        cursor = ''
        repos = []
        for i in range(0, self.bulk_count):
            res = get_graphql_data(qql % cursor)
            if not res: break
            repos_gql = res
            if "data" not in repos_gql or not repos_gql["data"]["search"]["pageInfo"]["endCursor"]:
                repos += self.parse_gql_result(repos_gql)
                break
            cursor = ', after:"' + repos_gql["data"]["search"]["pageInfo"]["endCursor"] + '"'
            repos += self.parse_gql_result(repos_gql)
        return repos

    def get_all_repos(self):
        # 移除了全局 Most Stars/Forks 的抓取逻辑
        repos_topics = {}
        for topic in topics:
            print("Get research repos of {}...".format(topic))
            repos_topics[topic] = self.get_repos(self.gql_topic % (topic, '%s'))
        return repos_topics


class WriteFile(object):
    def __init__(self, repos_topics):
        self.repos_topics = repos_topics
        self.col = ['rank', 'item', 'repo_name', 'stars', 'forks', 'language', 'repo_url', 'username', 'issues',
                    'last_commit', 'description']
        self.repo_list = []
        for i in range(len(topics)):
            topic = topics[i]
            display = topics_display[i]
            self.repo_list.append({
                "desc": "Stars",
                "desc_md": "Stars",
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

            **AI & Robotics Research Frontier - Global Top Repositories.**

            *Last Automatic Update Time: {write_time}*

            *Note: This list focuses on research fields and technical innovation.*

            ## Table of Contents
            """.format(write_time=write_time)) + "\n" + table_of_contents
        write_text("../README.md", 'w', head_contents)

    def write_readme_lang_md(self):
        os.makedirs('../Top100', exist_ok=True)
        for repo in self.repo_list:
            title_readme, title_100, file_100, data = repo["title_readme"], repo["title_100"], repo["file_100"], repo["data"]
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
                df_repos.append([idx + 1, repo["item"], r['name'], r['stargazers_count'], r['forks_count'], r['language'],
                                r['html_url'], r['owner']['login'], r['open_issues_count'], r['pushed_at'],
                                r['description']])
            if df_repos:
                dfs.append(pd.DataFrame(df_repos, columns=self.col))
        
        if dfs:
            df_all = pd.concat(dfs, ignore_index=True)
            save_date = datetime.utcnow().strftime("%Y-%m-%d")
            os.makedirs('../Data', exist_ok=True)
            df_all.to_csv('../Data/github-ranking-' + save_date + '.csv', index=False, encoding='utf-8')


def run_by_gql():
    ROOT_PATH = os.path.abspath(os.path.join(__file__, "../../"))
    os.chdir(os.path.join(ROOT_PATH, 'source'))
    processor = ProcessorGQL()
    repos_topics = processor.get_all_repos()
    wt_obj = WriteFile(repos_topics)
    wt_obj.write_head_contents()
    wt_obj.write_readme_lang_md()
    wt_obj.save_to_csv()

if __name__ == "__main__":
    run_by_gql()
