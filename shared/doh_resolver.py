import socket
import urllib.request
import urllib.error
import json

_original_getaddrinfo = socket.getaddrinfo
_doh_cache = {}

def resolve_via_doh(host):
    if host in _doh_cache:
        return _doh_cache[host]
    try:
        url = f"https://1.1.1.1/dns-query?name={host}&type=A"
        req = urllib.request.Request(url, headers={"accept": "application/dns-json", "Host": "cloudflare-dns.com"})
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read().decode())
        ips = [ans["data"] for ans in data.get("Answer", []) if ans.get("type") == 1]
        if ips:
            _doh_cache[host] = ips
            print(f"[DoH Hook] Resolved {host} -> {ips} via Cloudflare")
            return ips
    except Exception:
        pass
    try:
        url = f"https://dns.google/resolve?name={host}&type=A"
        resp = urllib.request.urlopen(url, timeout=5)
        data = json.loads(resp.read().decode())
        ips = [ans["data"] for ans in data.get("Answer", []) if ans.get("type") == 1]
        if ips:
            _doh_cache[host] = ips
            print(f"[DoH Hook] Resolved {host} -> {ips} via Google")
            return ips
    except Exception:
        pass
    return None

def custom_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    try:
        return _original_getaddrinfo(host, port, family, type, proto, flags)
    except socket.gaierror as e:
        if host not in ["cloudflare-dns.com", "dns.google", "1.1.1.1", "8.8.8.8"]:
            ips = resolve_via_doh(host)
            if ips:
                results = []
                for ip in ips:
                    p = int(port) if isinstance(port, (int, str)) and str(port).isdigit() else 0
                    results.append((socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', (ip, p)))
                return results
        raise e

def patch_dns():
    """Patches socket.getaddrinfo to use DoH fallback."""
    socket.getaddrinfo = custom_getaddrinfo
