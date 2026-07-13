import requests

OUTIL = {
    "name": "crypto",
    "description": "Prix crypto en temps réel via CoinGecko (gratuit, sans clé API)",
    "parameters": {
        "type": "object",
        "properties": {
            "coins": {"type": "string", "description": "IDs CoinGecko séparés par virgules (ex: bitcoin,ethereum,solana)", "default": "bitcoin,ethereum"},
            "vs_currency": {"type": "string", "description": "Devise de référence (usd, eur, btc, eth...)", "default": "usd"},
            "include_24h_change": {"type": "boolean", "description": "Inclure variation 24h", "default": True},
            "include_market_cap": {"type": "boolean", "description": "Inclure market cap", "default": True},
            "include_volume": {"type": "boolean", "description": "Inclure volume 24h", "default": False}
        }
    }
}

DANGEREUX = False

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

def executer(args, config):
    coins = args.get("coins", "bitcoin,ethereum").strip()
    vs_currency = args.get("vs_currency", "usd").lower()
    include_24h = args.get("include_24h_change", True)
    include_mcap = args.get("include_market_cap", True)
    include_vol = args.get("include_volume", False)
    
    coin_list = [c.strip().lower() for c in coins.split(",") if c.strip()]
    if not coin_list:
        return "Erreur: au moins un coin requis"
    
    params = {
        "ids": ",".join(coin_list),
        "vs_currencies": vs_currency,
        "include_24hr_change": "true" if include_24h else "false",
        "include_market_cap": "true" if include_mcap else "false",
        "include_24hr_vol": "true" if include_vol else "false"
    }
    
    try:
        resp = requests.get(COINGECKO_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        return "Erreur: timeout CoinGecko"
    except requests.exceptions.RequestException as e:
        return f"Erreur réseau: {e}"
    except Exception as e:
        return f"Erreur: {e}"
    
    if not data:
        return "Aucune donnée (vérifiez les IDs CoinGecko)"
    
    lines = [f"Prix crypto ({vs_currency.upper()})", "=" * 50]
    
    for coin_id in coin_list:
        if coin_id not in data:
            lines.append(f"{coin_id}: introuvable")
            continue
        
        d = data[coin_id]
        price = d.get(vs_currency)
        if price is None:
            lines.append(f"{coin_id}: pas de prix en {vs_currency.upper()}")
            continue
        
        # Format prix
        if price >= 1:
            price_str = f"{price:,.2f}"
        elif price >= 0.01:
            price_str = f"{price:.4f}"
        else:
            price_str = f"{price:.8f}"
        
        line = f"{coin_id.capitalize():<12} {price_str:>15} {vs_currency.upper()}"
        
        if include_24h:
            change = d.get(f"{vs_currency}_24h_change")
            if change is not None:
                sign = "+" if change > 0 else ""
                line += f"  ({sign}{change:.2f}%)"
        
        if include_mcap:
            mcap = d.get(f"{vs_currency}_market_cap")
            if mcap:
                if mcap >= 1e12:
                    mcap_str = f"{mcap/1e12:.2f}T"
                elif mcap >= 1e9:
                    mcap_str = f"{mcap/1e9:.2f}B"
                elif mcap >= 1e6:
                    mcap_str = f"{mcap/1e6:.2f}M"
                else:
                    mcap_str = f"{mcap:,.0f}"
                line += f"  MC: {mcap_str}"
        
        if include_vol:
            vol = d.get(f"{vs_currency}_24h_vol")
            if vol:
                if vol >= 1e9:
                    vol_str = f"{vol/1e9:.2f}B"
                elif vol >= 1e6:
                    vol_str = f"{vol/1e6:.2f}M"
                else:
                    vol_str = f"{vol:,.0f}"
                line += f"  Vol: {vol_str}"
        
        lines.append(line)
    
    return "\n".join(lines)