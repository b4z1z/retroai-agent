import requests
import re
from urllib.parse import quote_plus

OUTIL = {
    "name": "web_search",
    "description": "Recherche web via DuckDuckGo (HTML scraping, sans clé API)",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Terme de recherche"},
            "max_results": {"type": "integer", "description": "Nombre max de résultats", "default": 5}
        },
        "required": ["query"]
    }
}

DANGEREUX = False

def executer(args, config):
    query = args.get("query", "")
    max_results = args.get("max_results", 5)
    
    if not query:
        return "Erreur: query requis"
    
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return f"Erreur réseau: {e}"
    
    # Parse des résultats
    results = []
    # Pattern pour les snippets
    snippet_pattern = r'class="result__snippet">(.*?)</a>'
    snippets = re.findall(snippet_pattern, resp.text, re.DOTALL)
    
    url_pattern = r'class="result__url">(.*?)</a>'
    urls = re.findall(url_pattern, resp.text, re.DOTALL)
    
    title_pattern = r'class="result__title">.*?>(.*?)</a>'
    titles = re.findall(title_pattern, resp.text, re.DOTALL)
    
    for i in range(min(max_results, len(snippets))):
        title = re.sub(r'<[^>]+>', '', titles[i] if i < len(titles) else "").strip()
        snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()[:200]
        url = re.sub(r'<[^>]+>', '', urls[i] if i < len(urls) else "").strip()
        results.append(f"{i+1}. {title}\n   {snippet}\n   {url}")
    
    if not results:
        return "Aucun résultat trouvé"
    
    return f"Résultats pour '{query}':\n\n" + "\n\n".join(results)