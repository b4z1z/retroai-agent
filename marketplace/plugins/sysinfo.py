import platform
import os

OUTIL = {
    "name": "sysinfo",
    "description": "Informations système (CPU, RAM, disque, réseau, processus)",
    "parameters": {
        "type": "object",
        "properties": {
            "type": {"type": "string", "description": "Type d'info: cpu, memory, disk, network, processes, all", "default": "all"}
        }
    }
}

DANGEREUX = False

def executer(args, config):
    try:
        import psutil
    except ImportError:
        return ("Error: this plugin needs the 'psutil' "
                "package. Install it with: pip install psutil")
    info_type = args.get("type", "all")
    out = []
    
    if info_type in ("cpu", "all"):
        cpu = psutil.cpu_percent(interval=0.5, percpu=True)
        out.append(f"CPU: {sum(cpu)/len(cpu):.1f}% total ({len(cpu)} cœurs)")
        out.append(f"  Par cœur: {', '.join(f'{c:.1f}%' for c in cpu)}")
        freq = psutil.cpu_freq()
        if freq:
            out.append(f"  Fréquence: {freq.current:.0f} MHz (max {freq.max:.0f})")
    
    if info_type in ("memory", "ram", "all"):
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        out.append(f"RAM: {mem.percent:.1f}% utilisé ({mem.used//1024**3}GB / {mem.total//1024**3}GB)")
        out.append(f"  Dispo: {mem.available//1024**3}GB | Swap: {swap.percent:.1f}% ({swap.used//1024**3}GB/{swap.total//1024**3}GB)")
    
    if info_type in ("disk", "all"):
        out.append("Disques:")
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                out.append(f"  {part.device} ({part.mountpoint}): {usage.percent:.1f}% ({usage.used//1024**3}GB/{usage.total//1024**3}GB) [{part.fstype}]")
            except PermissionError:
                out.append(f"  {part.device} ({part.mountpoint}): Accès refusé")
    
    if info_type in ("network", "net", "all"):
        net = psutil.net_io_counters()
        out.append(f"Réseau: ↑ {net.bytes_sent//1024**2}MB ↓ {net.bytes_recv//1024**2}MB | Paquets: ↑{net.packets_sent} ↓{net.packets_recv}")
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == 2:  # AF_INET
                    out.append(f"  {iface}: {addr.address}")
    
    if info_type in ("processes", "proc", "ps", "all"):
        procs = sorted(psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']), 
                       key=lambda p: p.info['cpu_percent'] or 0, reverse=True)[:10]
        out.append("Top 10 processus (CPU):")
        for p in procs:
            out.append(f"  {p.info['pid']:>6}  {p.info['cpu_percent']:>5.1f}%  {p.info['memory_percent']:>5.1f}%  {p.info['name']}")
    
    if info_type in ("system", "sys", "all"):
        out.insert(0, f"Système: {platform.system()} {platform.release()} ({platform.machine()})")
        out.insert(1, f"Python: {platform.python_version()} | Boot: {psutil.boot_time()}")
    
    return "\n".join(out)