# -*- coding: utf-8 -*-
"""
Translation utility with file-based cache.
Uses deep_translator (Google Translate free endpoint) to translate
repo descriptions to Chinese. Caches results to avoid redundant calls.
"""
import json
import os
import time

CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'translations_cache.json')
_RATE_DELAY = 0.25   # seconds between API calls
_MAX_CHARS  = 500    # truncate very long descriptions


def load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cache(cache: dict) -> None:
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)


def _translate_one(text: str, target: str = 'zh-CN') -> str:
    """Translate a single string. Returns original on failure."""
    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source='auto', target=target).translate(text[:_MAX_CHARS])
        return result if result else text
    except Exception as e:
        print(f"  [translate] failed: {e}")
        return text


def enrich_with_translations(all_repo_lists: list, cache: dict) -> dict:
    """
    For every repo in the provided lists, add a 'zh_description' field.
    New descriptions are translated and stored in cache.
    Returns the (possibly updated) cache.
    """
    # Collect unique descriptions not yet in cache
    pending = []
    for repos in all_repo_lists:
        for repo in repos:
            desc = (repo.get('description') or '').strip()
            if desc and desc not in cache and desc not in pending:
                pending.append(desc)

    if pending:
        print(f"Translating {len(pending)} new descriptions to Chinese...")
        for i, desc in enumerate(pending, 1):
            cache[desc] = _translate_one(desc)
            if i % 20 == 0:
                print(f"  Progress: {i}/{len(pending)}")
            time.sleep(_RATE_DELAY)
        print("Translation complete.")

    # Attach zh_description to every repo
    for repos in all_repo_lists:
        for repo in repos:
            desc = (repo.get('description') or '').strip()
            if desc:
                zh = cache.get(desc, desc)
                # Only store zh if it's actually different (avoid repeating English)
                repo['zh_description'] = zh if zh != desc else ''
            else:
                repo['zh_description'] = ''

    return cache
