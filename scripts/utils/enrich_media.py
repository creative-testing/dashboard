#!/usr/bin/env python3
"""
Media enrichment utilities for Creative Testing Dashboard.

Extracted from turbo_fix_creatives with improvements:
- Wider creative fields
- Fallback to story permalinks
- Last-resort thumbnail_url

Usage (as library):
    from utils.enrich_media import enrich_media_urls
    enrich_media_urls(base_dir='data/current', periods=[3,7,14,30,90])
"""
import os
import json
import time
from typing import Dict, List, Iterable
from concurrent.futures import ThreadPoolExecutor

import requests
from dotenv import load_dotenv

load_dotenv()

GRAPH_URL = "https://graph.facebook.com/v23.0"


def _get_token() -> str:
    token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    if not token:
        raise SystemExit("FACEBOOK_ACCESS_TOKEN not set. Define it in .env")
    return token


def _fetch_chunk_creatives(ad_ids: Iterable[str], token: str) -> Dict[str, dict]:
    ad_ids = [i for i in ad_ids if i]
    if not ad_ids:
        return {}
    params = {
        "ids": ",".join(ad_ids),
        "fields": (
            "creative{"  # widen for fallbacks
            "id,video_id,image_url,instagram_permalink_url,"
            "effective_object_story_id,object_story_id,object_type,thumbnail_url"
            "}"
        ),
        "access_token": token,
    }
    try:
        resp = requests.get(f"{GRAPH_URL}/", params=params, timeout=12)
        if resp.status_code == 200:
            return resp.json() or {}
    except Exception:
        pass
    return {}


def _fetch_permalinks_for_story_ids(story_ids: Iterable[str], token: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    ids = [i for i in story_ids if i]
    if not ids:
        return out
    for i in range(0, len(ids), 50):
        chunk = ids[i:i+50]
        try:
            resp = requests.get(
                f"{GRAPH_URL}/",
                params={
                    "ids": ",".join(chunk),
                    "fields": "permalink_url",
                    "access_token": token,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, dict) and v.get("permalink_url"):
                            out[k] = v["permalink_url"]
        except Exception:
            pass
    return out


def _process_period_json(path: str, token: str, max_workers: int = 20) -> Dict[str, int]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    ads: List[dict] = data.get("ads", [])
    chunks: List[tuple] = []
    for i in range(0, len(ads), 50):
        chunk = ads[i:i+50]
        ad_ids = [ad.get("ad_id") for ad in chunk if ad.get("ad_id")]
        if ad_ids:
            chunks.append((i, chunk, ad_ids))

    fixed_count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [(i, chunk, executor.submit(_fetch_chunk_creatives, ad_ids, token)) for i, chunk, ad_ids in chunks]
        for idx, (i, chunk, fut) in enumerate(futures):
            creatives_data = {}
            try:
                creatives_data = fut.result(timeout=30) or {}
            except Exception:
                pass

            unresolved_story_ids = set()
            for ad in chunk:
                ad_id = ad.get("ad_id")
                creative = (creatives_data.get(ad_id) or {}).get("creative", {})
                if not creative:
                    continue

                if creative.get("video_id"):
                    ad["format"] = "VIDEO"
                    ad["media_url"] = f"https://www.facebook.com/watch/?v={creative['video_id']}"
                    fixed_count += 1
                elif creative.get("image_url"):
                    ad["format"] = "IMAGE"
                    ad["media_url"] = creative["image_url"]
                    fixed_count += 1
                elif creative.get("instagram_permalink_url"):
                    ad["format"] = "INSTAGRAM"
                    ad["media_url"] = creative["instagram_permalink_url"]
                    fixed_count += 1
                else:
                    sid = creative.get("effective_object_story_id") or creative.get("object_story_id")
                    if sid:
                        unresolved_story_ids.add(sid)
                    elif creative.get("thumbnail_url"):
                        ad["format"] = ad.get("format") or "IMAGE"
                        ad["media_url"] = creative["thumbnail_url"]
                        fixed_count += 1

            if unresolved_story_ids:
                sid_to_permalink = _fetch_permalinks_for_story_ids(unresolved_story_ids, token)
                if sid_to_permalink:
                    for ad in chunk:
                        if ad.get("media_url"):
                            continue
                        ad_id = ad.get("ad_id")
                        creative = (creatives_data.get(ad_id) or {}).get("creative", {})
                        sid = creative.get("effective_object_story_id") or creative.get("object_story_id")
                        if sid and sid in sid_to_permalink:
                            ad["format"] = ad.get("format", "POST")
                            ad["media_url"] = sid_to_permalink[sid]
                            fixed_count += 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    with_url = sum(1 for ad in ads if ad.get("media_url"))
    return {"total": len(ads), "with_media": with_url, "fixed": fixed_count}


def enrich_media_urls(base_dir: str = "data/current", periods: List[int] = None, max_workers: int = 20) -> Dict[str, Dict[str, int]]:
    """Populate media_url for hybrid_data JSONs in base_dir.

    Returns per-period stats: {period: {total, with_media, fixed}}
    """
    token = _get_token()
    if periods is None:
        periods = [3, 7, 14, 30, 90]
    results: Dict[str, Dict[str, int]] = {}
    start = time.time()
    for p in periods:
        path = os.path.join(base_dir, f"hybrid_data_{p}d.json")
        if os.path.exists(path):
            stats = _process_period_json(path, token, max_workers=max_workers)
            results[str(p)] = stats
    elapsed = time.time() - start
    results["_summary"] = {"elapsed_sec": round(elapsed, 1)}
    return results


def _request_with_backoff(method, url, **kwargs):
    import time, random
    max_attempts = 5
    backoff = 1.0
    for attempt in range(max_attempts):
        try:
            r = requests.request(method, url, timeout=kwargs.pop('timeout', 12), **kwargs)
            try:
                data = r.json()
            except Exception:
                data = None
            if r.status_code == 200:
                return r
            # handle rate limits
            msg = str(data) if data else r.text
            if r.status_code in (429, 400) and ('#80004' in msg or 'too many calls' in msg.lower()):
                delay = min(30, backoff) + random.random()
                time.sleep(delay)
                backoff *= 2
                continue
            # other error: break
            return r
        except Exception:
            delay = min(10, backoff) + random.random()
            time.sleep(delay)
            backoff *= 2
    # last try
    return requests.request(method, url, timeout=12, **kwargs)


def enrich_media_urls_union(base_dir: str = "data/current", periods: List[int] = None, max_workers: int = 10, only_missing: bool = True) -> Dict[str, Dict[str, int]]:
    """One-pass creatives fetch using the union of ad_ids across periods, then apply back.

    Returns per-period stats: {period: {total, with_media, fixed}}
    """
    token = _get_token()
    if periods is None:
        periods = [3, 7, 14, 30, 90]

    # Load all periods and collect union of ad_ids
    datasets: Dict[int, dict] = {}
    union_ids = set()
    for p in periods:
        path = os.path.join(base_dir, f"hybrid_data_{p}d.json")
        if not os.path.exists(path):
            continue
        with open(path, 'r', encoding='utf-8') as f:
            datasets[p] = json.load(f)
        for ad in datasets[p].get('ads', []):
            if only_missing and ad.get('media_url'):
                continue
            aid = ad.get('ad_id')
            if aid:
                union_ids.add(aid)

    if not union_ids:
        return {"_summary": {"elapsed_sec": 0, "note": "no ids"}}

    # Fetch creatives in chunks once
    ids = list(union_ids)
    creative_map: Dict[str, dict] = {}
    unresolved_story_ids = set()

    def fetch_ids_chunk(chunk: List[str]):
        params = {
            "ids": ",".join(chunk),
            "fields": (
                "creative{"
                "id,video_id,image_url,instagram_permalink_url,"
                "effective_object_story_id,object_story_id,object_type,thumbnail_url"
                "}"
            ),
            "access_token": token,
        }
        r = _request_with_backoff('GET', f"{GRAPH_URL}/", params=params)
        if r.status_code == 200:
            try:
                return r.json() or {}
            except Exception:
                return {}
        return {}

    start = time.time()
    chunks = [ids[i:i+50] for i in range(0, len(ids), 50)]
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(fetch_ids_chunk, ch) for ch in chunks]
        for fut in futs:
            data = fut.result()
            for ad_id, obj in (data or {}).items():
                c = obj.get('creative') if isinstance(obj, dict) else None
                if c:
                    creative_map[ad_id] = c
                    sid = c.get("effective_object_story_id") or c.get("object_story_id")
                    if not (c.get('video_id') or c.get('image_url') or c.get('instagram_permalink_url')) and sid:
                        unresolved_story_ids.add(sid)

    # Resolve story permalinks once
    sid_to_permalink: Dict[str, str] = {}
    if unresolved_story_ids:
        for i in range(0, len(unresolved_story_ids), 50):
            chunk = list(unresolved_story_ids)[i:i+50]
            r = _request_with_backoff('GET', f"{GRAPH_URL}/", params={
                'ids': ",".join(chunk),
                'fields': 'permalink_url',
                'access_token': token,
            })
            if r.status_code == 200:
                try:
                    data = r.json()
                    for k, v in (data or {}).items():
                        if isinstance(v, dict) and v.get('permalink_url'):
                            sid_to_permalink[k] = v['permalink_url']
                except Exception:
                    pass

    # Apply to all datasets and write back
    results: Dict[str, Dict[str, int]] = {}
    for p, payload in datasets.items():
        fixed = 0
        ads = payload.get('ads', [])
        for ad in ads:
            if ad.get('media_url'):
                continue
            aid = ad.get('ad_id')
            c = creative_map.get(aid)
            if not c:
                continue
            if c.get('video_id'):
                ad['format'] = 'VIDEO'
                ad['media_url'] = f"https://www.facebook.com/watch/?v={c['video_id']}"
                fixed += 1
            elif c.get('image_url'):
                ad['format'] = 'IMAGE'
                ad['media_url'] = c['image_url']
                fixed += 1
            elif c.get('instagram_permalink_url'):
                ad['format'] = 'INSTAGRAM'
                ad['media_url'] = c['instagram_permalink_url']
                fixed += 1
            else:
                sid = c.get('effective_object_story_id') or c.get('object_story_id')
                if sid and sid in sid_to_permalink:
                    ad['format'] = ad.get('format', 'POST')
                    ad['media_url'] = sid_to_permalink[sid]
                    fixed += 1
                elif c.get('thumbnail_url'):
                    ad['format'] = ad.get('format') or 'IMAGE'
                    ad['media_url'] = c['thumbnail_url']
                    fixed += 1

        with open(os.path.join(base_dir, f"hybrid_data_{p}d.json"), 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        results[str(p)] = {
            'total': len(ads),
            'with_media': sum(1 for a in ads if a.get('media_url')),
            'fixed': fixed,
        }

    results['_summary'] = {'elapsed_sec': round(time.time() - start, 1), 'union_ids': len(union_ids)}
    return results


__all__ = ["enrich_media_urls", "enrich_media_urls_union"]
