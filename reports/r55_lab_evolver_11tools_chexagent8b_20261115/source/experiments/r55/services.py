"""Actual external tools: PubMed/MedRAG retrieval and image-capable LLM critic/verifier.

Nothing here imports or opens the private GT file. No fake/mock tool returns are used.
"""
from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .common import atomic_json, parse_json_object


class ModelService:
    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None,
                 temperature: float = 0.2, max_tokens: int = 1024, timeout: float = 90):
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError('pip install -r requirements-r55.txt') from e
        key = api_key or os.environ.get('R55_API_KEY') or os.environ.get('DASHSCOPE_API_KEY') or os.environ.get('OPENAI_API_KEY')
        if not key:
            raise RuntimeError('Set R55_API_KEY or DASHSCOPE_API_KEY (never commit a real key)')
        self.client = OpenAI(api_key=key, base_url=base_url or os.getenv('R55_BASE_URL') or 'https://dashscope.aliyuncs.com/compatible-mode/v1', timeout=timeout, max_retries=1)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def ask_json(self, *, role: str, payload: dict, images: list[Path] | None = None) -> tuple[dict, dict]:
        msgs: list[dict] = [{'role': 'system', 'content': role}]
        content: list[dict] = [{'type': 'text', 'text': json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}]
        for i, path in enumerate(images or []):
            mime = mimetypes.guess_type(path.name)[0] or 'image/png'
            if mime not in ('image/png', 'image/jpeg', 'image/webp'):
                raise ValueError(f'Unsupported image MIME: {path.name} {mime}')
            b64 = base64.b64encode(path.read_bytes()).decode('ascii')
            content.append({'type': 'text', 'text': f'Original image {i + 1} (unaltered): {path.name}'})
            content.append({'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{b64}'}})
        msgs.append({'role': 'user', 'content': content})
        kw = {'model': self.model, 'messages': msgs, 'max_tokens': self.max_tokens, 'temperature': self.temperature, 'top_p': 0.95}
        try:
            out = self.client.chat.completions.create(**kw, response_format={'type': 'json_object'})
        except Exception as e:
            # Only retry if the endpoint does not support the JSON format parameter.
            if 'response_format' not in str(e).lower():
                raise
            out = self.client.chat.completions.create(**kw)
        raw = out.choices[0].message.content
        if not isinstance(raw, str):
            raise ValueError('Empty/nontext model response')
        obj = parse_json_object(raw)
        usage = getattr(out, 'usage', None)
        meta = {'model': self.model, 'usage': usage.model_dump() if hasattr(usage, 'model_dump') else {}, 'response_id': getattr(out, 'id', None)}
        return obj, meta


def _http_json(url: str, *, data: dict | None = None, headers: dict | None = None, timeout: int = 25) -> dict:
    body = json.dumps(data).encode('utf-8') if data is not None else None
    req = urllib.request.Request(url, data=body, headers={**(headers or {}), **({'Content-Type': 'application/json'} if data is not None else {})})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def _http_xml(url: str, *, timeout: int = 30) -> ET.Element:
    req = urllib.request.Request(url, headers={'User-Agent': f'R55-MedicalResearch/1.0 ({os.getenv("NCBI_EMAIL", "research-user")})'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(7 * 1024 * 1024)
    return ET.fromstring(raw)


class MedicalRetriever:
    def __init__(self, cache_dir: Path, provider: str = 'pubmed', medrag_url: str | None = None,
                 top_k: int = 3):
        if provider not in {'pubmed', 'medrag_http'}:
            raise ValueError('provider must be pubmed or medrag_http')
        self.cache_dir = cache_dir
        self.provider = provider
        self.medrag_url = medrag_url
        self.top_k = top_k
        cache_dir.mkdir(parents=True, exist_ok=True)

    def search(self, query: str) -> dict:
        query = ' '.join(query.strip().split())[:180]
        if not query or len(query.split()) > 22:
            return {'status': 'invalid_query', 'query': query, 'evidence': []}
        digest = hashlib.sha256(json.dumps([self.provider, self.medrag_url, self.top_k, query]).encode()).hexdigest()
        cfile = self.cache_dir / (digest + '.json')
        if cfile.exists():
            value = json.loads(cfile.read_text(encoding='utf-8'))
            value['cache_hit'] = True
            return value
        if self.provider == 'pubmed':
            output = self._pubmed(query)
        else:
            output = self._medrag(query)
        output['cache_hit'] = False
        if output['status'] == 'ok':
            atomic_json(cfile, output)
        return output

    def _pubmed(self, query: str) -> dict:
        root = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
        params = {'db': 'pubmed', 'term': query, 'retmode': 'json', 'retmax': str(self.top_k), 'sort': 'relevance'}
        if os.getenv('NCBI_EMAIL'):
            params['email'] = os.getenv('NCBI_EMAIL', '')
        if os.getenv('NCBI_API_KEY'):
            params['api_key'] = os.getenv('NCBI_API_KEY', '')
        info = _http_json(root + 'esearch.fcgi?' + urllib.parse.urlencode(params))
        pmids = info.get('esearchresult', {}).get('idlist', [])
        if not pmids:
            return {'status': 'empty', 'query': query, 'evidence': []}
        time.sleep(0.36)  # be polite to NCBI public API without an API key
        fparams = {'db': 'pubmed', 'id': ','.join(pmids), 'rettype': 'xml', 'retmode': 'xml'}
        if os.getenv('NCBI_API_KEY'):
            fparams['api_key'] = os.getenv('NCBI_API_KEY', '')
        doc = _http_xml(root + 'efetch.fcgi?' + urllib.parse.urlencode(fparams))
        refs = []
        for article in doc.findall('.//PubmedArticle'):
            pmid = article.findtext('.//MedlineCitation/PMID')
            title_node = article.find('.//Article/ArticleTitle')
            title = ''.join(title_node.itertext()) if title_node is not None else ''
            parts = article.findall('.//Article/Abstract/AbstractText')
            abstract = ' '.join(' '.join(p.itertext()) for p in parts)
            year = (article.findtext('.//PubDate/Year') or article.findtext('.//ArticleDate/Year') or '')
            if pmid:
                refs.append({'pmid': pmid, 'title': title[:350], 'abstract': abstract[:1900], 'year': year,
                             'url': 'https://pubmed.ncbi.nlm.nih.gov/' + str(pmid) + '/'})
        return {'status': 'ok' if refs else 'empty', 'query': query, 'provider': 'pubmed', 'evidence': refs[:self.top_k]}

    def _medrag(self, query: str) -> dict:
        if not self.medrag_url:
            return {'status': 'unconfigured', 'query': query, 'evidence': []}
        # Contract: POST {query, top_k} -> {documents:[{title, content, source/url, pmid}]}
        obj = _http_json(self.medrag_url, data={'query': query, 'top_k': self.top_k}, timeout=40)
        documents = obj.get('documents', [])
        if not isinstance(documents, list):
            raise ValueError('medrag_http expects {"documents": [...]}')
        evidence = []
        for d in documents[:self.top_k]:
            if not isinstance(d, dict):
                continue
            evidence.append({'title': str(d.get('title', ''))[:350], 'abstract': str(d.get('content', d.get('text', '')))[:1900],
                             'year': str(d.get('year', '')), 'url': str(d.get('url', d.get('source', '')))[:500], 'pmid': str(d.get('pmid', ''))})
        return {'status': 'ok' if evidence else 'empty', 'provider': 'medrag_http', 'query': query, 'evidence': evidence}
