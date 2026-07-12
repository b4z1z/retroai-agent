"""
Plugin communautaire : INFOS SYSTEME (OS, CPU, RAM approx, disque).

Sans dependance externe : uniquement la bibliotheque standard.
"""

OUTIL = {
    "name": "system_info",
    "description": (
        "Get basic system information: OS, machine, Python version, CPU "
        "count and free disk space. Use it when the user asks about their "
        "machine or before heavy operations."
    ),
    "parameters": {"type": "object", "properties": {}},
}

DANGEREUX = False


def executer(args: dict, config) -> str:
    import os
    import platform
    import shutil
    import sys

    try:
        disque = shutil.disk_usage(os.getcwd())
        libre = f"{disque.free / (1024**3):.1f} GB free / " \
                f"{disque.total / (1024**3):.1f} GB total"
    except OSError:
        libre = "unknown"
    return (
        f"OS: {platform.system()} {platform.release()} ({platform.machine()})\n"
        f"Python: {sys.version.split()[0]}\n"
        f"CPU cores: {os.cpu_count()}\n"
        f"Disk ({os.getcwd()}): {libre}"
    )
