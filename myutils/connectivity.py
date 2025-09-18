import socket
import subprocess
import platform
import threading

# ------------------------------
# Result wrapper class
# ------------------------------
class ReachabilityResult:
    def __init__(self, reachable, method):
        self.reachable = reachable
        self.method = method

    def __bool__(self):
        return self.reachable

    def __iter__(self):
        yield self.reachable
        yield self.method

    def __repr__(self):
        return f"ReachabilityResult(reachable={self.reachable}, method={self.method})"

# ------------------------------
# Low-level checks
# ------------------------------
def is_port_open(host, port, timeout=1):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except ConnectionRefusedError:
        return True  # Host is up, port is closed
    except Exception:
        return False

def is_tc_port_open(host):
    return is_port_open(host, 48898)

def is_ssh_port_open(host):
    return is_port_open(host, 20022)

def is_http_port_open(host):
    return is_port_open(host, 80)

def is_https_port_open(host):
    return is_port_open(host, 443)



def ping_to_host(host, timeout=1):
    
    system = platform.system().lower()
    if "windows" in system:
        cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), host]
        creation_flags = subprocess.CREATE_NO_WINDOW
    else:
        cmd = ["ping", "-c", "1", "-W", str(timeout), host]
        creation_flags = 0

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout + 1,
            # check=True,
            creationflags=creation_flags,
            text=True
        )

        output = result.stdout.lower()

        # Check for common unreachable indicators
        if (
            "unreachable" in output or
            "timed out" in output or
            "could not find host" in output or
            r"100% loss" in output
        ):
            return False

        return True
    except subprocess.TimeoutExpired:
        # print(f"Ping to {host} timed out.")
        return False
    except subprocess.CalledProcessError:
        # print(f"Ping to {host} failed.")
        return False
    

# ------------------------------
# Hybrid threaded reachability check
# ------------------------------
def is_host_reachable(host):
    """
    Return ReachabilityResult:
        - Truthy if reachable
        - Unpacks as (reachable, method)
    """

    checks = {
        "ping":  lambda: ping_to_host(host),
        # "ads": lambda: is_tc_port_open(host),
        # "ssh": lambda: is_ssh_port_open(host),
        "http":  lambda: is_http_port_open(host),
        "https": lambda: is_https_port_open(host),
    }

    result = {"reachable": False, "method": None}
    event = threading.Event()

    def check(name, func):
        if func():
            if not event.is_set():
                result["reachable"] = True
                result["method"] = name
                event.set()

    threads = [
        threading.Thread(target=check, args=(name, func))
        for name, func in checks.items()
    ]

    for thread in threads:
        thread.start()

    event.wait(timeout=0.5)
    for thread in threads:
        thread.join(timeout=0.1)

    return ReachabilityResult(result["reachable"], result["method"])
