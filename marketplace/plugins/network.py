"""
Plugin communautaire : OUTILS RESEAU (ping, DNS, IP info, port scan, HTTP check, traceroute).

Utilise la stdlib + APIs gratuites (ip-api.com, ipinfo.io) sans cle API.
"""

OUTIL = {
    "name": "network_tool",
    "description": (
        "Network utilities: ping, DNS lookup, IP info, port scan, HTTP check, "
        "traceroute, and get your public IP. Uses stdlib + free APIs (ip-api.com, ipinfo.io)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["ping", "dns", "ipinfo", "portscan", "http", "traceroute", "myip"],
                "description": "Action to perform"
            },
            "target": {
                "type": "string",
                "description": "Target host, IP, or URL (required for ping, dns, ipinfo, portscan, http, traceroute)"
            },
            "port": {
                "type": "integer",
                "description": "Port number (for portscan or http)",
                "minimum": 1,
                "maximum": 65535
            },
            "ports": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "List of ports to scan (for portscan)"
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 5)",
                "default": 5
            },
            "count": {
                "type": "integer",
                "description": "Number of pings (for ping)",
                "default": 4
            },
            "record_type": {
                "type": "string",
                "enum": ["A", "AAAA", "MX", "NS", "TXT", "CNAME"],
                "description": "DNS record type (for dns)",
                "default": "A"
            },
            "follow_redirects": {
                "type": "boolean",
                "description": "Follow HTTP redirects (for http)",
                "default": True
            }
        },
        "required": ["action"]
    },
}

DANGEREUX = False  # Read-only network ops, no auth, no writes


# ─── Helpers ────────────────────────────────────────────────────────────────

def _run_cmd(cmd: list, timeout: int) -> tuple[int, str, str]:
    """Run command, return (code, stdout, stderr)."""
    import subprocess
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


def _get_my_ip(timeout: int) -> str:
    """Get public IP via free API."""
    import json
    import urllib.request
    import urllib.error
    for url in ("http://ip-api.com/json/", "https://ipinfo.io/json"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BAZIZ.IA-network/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.load(resp)
                return data.get("query") or data.get("ip") or "unknown"
        except Exception:
            continue
    return "unknown"


def _ping(target: str, count: int, timeout: int) -> str:
    """Cross-platform ping."""
    import platform
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000), target]
    else:
        cmd = ["ping", "-c", str(count), "-W", str(timeout), target]
    code, out, err = _run_cmd(cmd, timeout * count + 5)
    if code == 0:
        return f"Ping OK ({count} packets)\n{out.strip()}"
    else:
        return f"Ping failed (code {code})\n{err or out}"


def _dns_lookup(target: str, record_type: str, timeout: int) -> str:
    """DNS lookup using stdlib."""
    import socket
    try:
        socket.setdefaulttimeout(timeout)
        if record_type == "A":
            addrs = socket.getaddrinfo(target, None, socket.AF_INET)
            ips = sorted({a[4][0] for a in addrs})
            return f"A records for {target}:\n" + "\n".join(f"  A   {ip}" for ip in ips)
        elif record_type == "AAAA":
            addrs = socket.getaddrinfo(target, None, socket.AF_INET6)
            ips = sorted({a[4][0] for a in addrs})
            return f"AAAA records for {target}:\n" + "\n".join(f"  AAAA {ip}" for ip in ips)
        else:
            # For MX, NS, TXT, CNAME try dig if available
            if record_type in ("MX", "NS", "TXT", "CNAME"):
                code, out, err = _run_cmd(["dig", "+short", record_type, target], timeout)
                if code == 0 and out.strip():
                    return f"{record_type} records for {target}:\n{out.strip()}"
                return f"{record_type} lookup failed (dig not available or no records)\n{err}"
            return f"Unsupported record type: {record_type}"
    except socket.gaierror as e:
        return f"DNS lookup failed: {e}"
    except Exception as e:
        return f"DNS error: {e}"


def _ip_info(target: str, timeout: int) -> str:
    """Get IP geolocation/info via ip-api.com (free, no key, 45 req/min)."""
    import json
    import urllib.request
    import urllib.parse
    import urllib.error
    try:
        url = f"http://ip-api.com/json/{urllib.parse.quote(target)}?fields=status,message,country,regionName,city,zip,lat,lon,timezone,isp,org,as,query"
        req = urllib.request.Request(url, headers={"User-Agent": "BAZIZ.IA-network/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        if data.get("status") != "success":
            return f"IP info failed: {data.get('message', 'unknown error')}"
        lines = [
            f"IP Info for {data['query']}",
            f"  Country:     {data.get('country', 'N/A')} ({data.get('countryCode', 'N/A')})",
            f"  Region:      {data.get('regionName', 'N/A')} ({data.get('region', 'N/A')})",
            f"  City:        {data.get('city', 'N/A')}",
            f"  ZIP:         {data.get('zip', 'N/A')}",
            f"  Coordinates: {data.get('lat', 'N/A')}, {data.get('lon', 'N/A')}",
            f"  Timezone:    {data.get('timezone', 'N/A')}",
            f"  ISP:         {data.get('isp', 'N/A')}",
            f"  Org:         {data.get('org', 'N/A')}",
            f"  AS:          {data.get('as', 'N/A')}",
        ]
        return "\n".join(lines)
    except urllib.error.HTTPError as e:
        return f"HTTP error: {e.code} {e.reason}"
    except Exception as e:
        return f"IP info error: {e}"


def _port_scan(target: str, ports: list[int], timeout: int) -> str:
    """TCP port scan using stdlib sockets."""
    import socket
    open_ports = []
    closed_ports = []
    filtered_ports = []
    
    for port in ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((target, port))
            sock.close()
            if result == 0:
                open_ports.append(port)
            else:
                closed_ports.append(port)
        except socket.timeout:
            filtered_ports.append(port)
        except Exception:
            filtered_ports.append(port)
    
    lines = [f"Port scan of {target} ({len(ports)} ports, timeout={timeout}s)"]
    if open_ports:
        lines.append(f"Open ports ({len(open_ports)}): {', '.join(map(str, sorted(open_ports)))}")
    if closed_ports:
        lines.append(f"Closed ports ({len(closed_ports)}): {', '.join(map(str, sorted(closed_ports)))}")
    if filtered_ports:
        lines.append(f"Filtered/timeout ({len(filtered_ports)}): {', '.join(map(str, sorted(filtered_ports)))}")
    return "\n".join(lines)


def _http_check(target: str, port: int | None, timeout: int, follow_redirects: bool) -> str:
    """HTTP/HTTPS check with headers."""
    import urllib.request
    import urllib.error
    import time
    if not target.startswith(("http://", "https://")):
        scheme = "https" if port == 443 else "http"
        target = f"{scheme}://{target}"
        if port and port not in (80, 443):
            target += f":{port}"
    
    try:
        req = urllib.request.Request(target, headers={"User-Agent": "BAZIZ.IA-network/1.0"})
        if not follow_redirects:
            class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
                def http_error_302(self, req, fp, code, msg, headers):
                    return fp
                http_error_301 = http_error_303 = http_error_307 = http_error_302
            opener = urllib.request.build_opener(NoRedirectHandler)
        else:
            opener = urllib.request.build_opener()
        
        start = time.time()
        with opener.open(req, timeout=timeout) as resp:
            elapsed = (time.time() - start) * 1000
            headers = dict(resp.headers)
            body_preview = resp.read(500).decode("utf-8", errors="replace")
        
        lines = [
            f"HTTP check: {target}",
            f"  Status:  {resp.status} {resp.reason}",
            f"  Time:    {elapsed:.0f} ms",
            f"  Headers: {len(headers)} headers",
        ]
        for k in ("server", "content-type", "content-length", "x-powered-by", "location"):
            if k in headers:
                lines.append(f"  {k.title()}: {headers[k]}")
        if body_preview.strip():
            lines.append(f"  Body preview: {body_preview[:200]}...")
        return "\n".join(lines)
    except urllib.error.HTTPError as e:
        return f"HTTP check: {target}\n  Status: {e.code} {e.reason}"
    except Exception as e:
        return f"HTTP check failed: {e}"


def _traceroute(target: str, timeout: int) -> str:
    """Traceroute using system command."""
    import platform
    system = platform.system().lower()
    if system == "windows":
        cmd = ["tracert", "-w", str(timeout * 1000), target]
    else:
        cmd = ["traceroute", "-w", str(timeout), "-q", "1", target]
    code, out, err = _run_cmd(cmd, timeout * 30)
    if code == 0:
        return f"Traceroute to {target}:\n{out.strip()}"
    else:
        # Fallback: try with -n (no DNS) on Unix
        if system != "windows":
            cmd = ["traceroute", "-n", "-w", str(timeout), "-q", "1", target]
            code, out, err = _run_cmd(cmd, timeout * 30)
            if code == 0:
                return f"Traceroute to {target} (no DNS):\n{out.strip()}"
        return f"Traceroute failed (code {code})\n{err or out}"


# ─── Main executor ──────────────────────────────────────────────────────────

def executer(args: dict, config: dict) -> str:
    action = args["action"]
    timeout = args.get("timeout", 5)
    
    if action == "myip":
        ip = _get_my_ip(timeout)
        return f"Your public IP: {ip}"
    
    target = args.get("target")
    if not target:
        return "Error: 'target' is required for this action"
    
    if action == "ping":
        count = args.get("count", 4)
        return _ping(target, count, timeout)
    
    elif action == "dns":
        record_type = args.get("record_type", "A")
        return _dns_lookup(target, record_type, timeout)
    
    elif action == "ipinfo":
        return _ip_info(target, timeout)
    
    elif action == "portscan":
        ports = args.get("ports")
        port = args.get("port")
        if ports:
            port_list = ports
        elif port:
            port_list = [port]
        else:
            # Common ports
            port_list = [21, 22, 23, 25, 53, 80, 110, 143, 443, 465, 587, 993, 995, 3306, 3389, 5432, 8080, 8443]
        return _port_scan(target, port_list, timeout)
    
    elif action == "http":
        port = args.get("port")
        follow = args.get("follow_redirects", True)
        return _http_check(target, port, timeout, follow)
    
    elif action == "traceroute":
        return _traceroute(target, timeout)
    
    return f"Unknown action: {action}"