"""System introspection: CPU, memory, disks, mounts."""

import logging
import os
import subprocess
import time

from . import config


def _run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return r.stdout.splitlines()
    except Exception as e:
        logging.warning("command failed: %s -> %s", " ".join(cmd), e)
        return []


def _is_openbsd():
    p = config.get("system", {}).get("platform", "auto")
    if p == "openbsd":
        return True
    if p == "linux":
        return False
    if os.path.exists("/bsd") or os.path.exists("/bsd.mp") or os.path.exists("/bsd.sp"):
        return True
    try:
        return "openbsd" in subprocess.run(["uname", "-s"], capture_output=True, text=True).stdout.lower()
    except Exception:
        return False



def get_filesystems():
    obe = _is_openbsd()
    df_cmd = ["/bin/df", "-h"] if obe else ["df", "-h"]
    lines = _run(df_cmd)
    result = []
    for line in lines:
        if not line or line.startswith("Filesystem"):
            continue
        fields = line.split()
        if len(fields) < 6:
            continue
        dev = fields[0]
        if obe and dev.startswith("/dev/"):
            dev = dev[5:]
        cap_str = fields[4].rstrip("%")
        result.append({
            "device": dev,
            "total": fields[1],
            "used": fields[2],
            "avail": fields[3],
            "capacity": float(cap_str) if cap_str.replace(".", "", 1).replace("-", "", 1).isdigit() else 0,
            "mount": fields[5],
        })
    return result


def list_disks():
    obe = _is_openbsd()
    if obe:
        lines = _run(["/sbin/sysctl", "-n", "hw.disknames"])
        raw = "".join(lines).strip()
        if not raw:
            return []
        return [p.split(":")[0].strip() for p in raw.split(",") if p.strip()]
    else:
        try:
            names = os.listdir("/sys/block")
        except FileNotFoundError:
            return []
        skip = {"loop", "ram", "zram", "dm-", "md", "sr", "cdrom"}
        return [n for n in names if not any(n.startswith(s) for s in skip)]


def get_disk_info(name):
    obe = _is_openbsd()
    info = {"name": name, "type": "", "label": "", "partitions": []}
    if obe:
        lines = _run(["/sbin/disklabel", name])
        in_parts = False
        for line in lines:
            if line.startswith("type:"):
                info["type"] = line.split(":", 1)[1].strip()
            if line.startswith("label:"):
                info["label"] = line.split(":", 1)[1].strip()
            if "partitions:" in line:
                in_parts = True
                continue
            if in_parts:
                if not line.strip() or line.startswith("#"):
                    continue
                fields = line.split()
                if len(fields) < 4:
                    continue
                num = fields[0].rstrip(":")
                info["partitions"].append({
                    "number": int(num) if num.isdigit() else 0,
                    "size": fields[1],
                    "offset": fields[2],
                    "fstype": fields[3],
                })
    else:
        info["type"] = "disk"
    return info


def get_system_stats():
    cpu = {"user": 0, "nice": 0, "sys": 0, "idle": 0, "model": "", "freq_mhz": 0, "cores": 0}
    mem = {"total": 0, "used": 0, "free": 0, "buffers": 0, "page_size": 4096}
    uptime = 0

    obe = _is_openbsd()

    if obe:
        for line in _run(["/sbin/sysctl", "-n", "hw.model"]):
            cpu["model"] = line.strip(); break
        for line in _run(["/sbin/sysctl", "-n", "hw.cpuspeed"]):
            try: cpu["freq_mhz"] = int(line.strip())
            except ValueError: pass
            break
        for line in _run(["/sbin/sysctl", "-n", "hw.ncpu"]):
            try: cpu["cores"] = int(line.strip())
            except ValueError: pass
            break
        for line in _run(["/sbin/sysctl", "-n", "hw.pagesize"]):
            try: mem["page_size"] = int(line.strip())
            except ValueError: pass
            break
        for line in _run(["/sbin/sysctl", "-n", "kern.boottime"]):
            try: uptime = int(time.time()) - int(line.strip())
            except (ValueError, ImportError): pass
            break

        # Total physical memory from hw.physmem
        for line in _run(["/sbin/sysctl", "-n", "hw.physmem"]):
            try:
                mem["total"] = int(line.strip())
                logging.debug("hw.physmem = %d", mem["total"])
                break
            except ValueError:
                pass

        # Memory breakdown via sysctl vm.uvmexp (instant, no suffix)
        uvmexp_lines = _run(["/sbin/sysctl", "vm.uvmexp"])
        uvmexp_ok = False
        if uvmexp_lines:
            uvm = {}
            for line in uvmexp_lines:
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip().rsplit(".", 1)[-1]
                    try: uvm[k] = int(v.strip())
                    except ValueError: pass
            ps = uvm.get("pagesize") or mem.get("page_size") or 4096
            mem["page_size"] = ps
            total_pages = uvm.get("npages", 0)
            if total_pages > 0:
                uvmexp_ok = True
                active_pages = uvm.get("active", 0)
                wired_pages = uvm.get("wired", 0)
                mem["used"] = (active_pages + wired_pages) * ps
                mem["free"] = max(mem["total"] - mem["used"], 0)
                logging.debug("uvmexp: npages=%d active=%d wired=%d free=%d total=%d ps=%d",
                              total_pages, active_pages, wired_pages,
                              uvm.get("free", 0), mem["total"], ps)
        if not uvmexp_ok:
            logging.debug("uvmexp not available, using vmstat -s fallback")
            free_pages_u = 0
            managed_pages = 0
            inactive_pages_u = 0
            for line in _run(["/usr/bin/vmstat", "-s"]):
                parts = line.strip().split(None, 1)
                if len(parts) == 2:
                    try:
                        val = int(parts[0])
                        key = parts[1]
                        if key == "pages managed":
                            managed_pages = val
                        elif key == "pages free":
                            free_pages_u = val
                        elif key == "pages inactive":
                            inactive_pages_u = val
                    except ValueError:
                        pass
            ps = mem.get("page_size") or 4096
            if managed_pages > 0 and free_pages_u > 0:
                mem["total"] = managed_pages * ps
                # "Used" = active + wired (matches htop); inactive pages
                # are reclaimable and treated as available.
                used_pages = managed_pages - free_pages_u - inactive_pages_u
                mem["used"] = max(used_pages * ps, 0)
                mem["free"] = max(mem["total"] - mem["used"], 0)
                logging.debug("vmstat -s: managed=%d free=%d inactive=%d used=%d ps=%d",
                              managed_pages, free_pages_u, inactive_pages_u,
                              used_pages, ps)
            else:
                # Last-resort fallback: hw.usermem
                for line in _run(["/sbin/sysctl", "-n", "hw.usermem"]):
                    try:
                        mem["free"] = int(line.strip())
                        logging.debug("hw.usermem = %d", mem["free"])
                        break
                    except ValueError:
                        pass

        # CPU idle/sys/us still from vmstat (no suffixes on cpu columns)
        vmstat_lines = _run(["/usr/bin/vmstat", "1", "2"])
        logging.debug("vmstat lines: %d", len(vmstat_lines))
        if vmstat_lines:
            logging.debug("vmstat[0]=%r", vmstat_lines[0])
        if len(vmstat_lines) >= 3:
            header = vmstat_lines[1].split()
            data = vmstat_lines[-1].split()
            logging.debug("vmstat header: %s", header)
            logging.debug("vmstat data: %s", data)
            try:
                cpu["user"] = float(data[header.index("us")])
                cpu["sys"] = float(data[header.index("sy")])
                cpu["idle"] = float(data[header.index("id")])
            except (ValueError, IndexError, AttributeError) as e:
                logging.debug("vmstat cpu parse failed: %s", e)
        else:
            logging.debug("vmstat output too short, skipping")
    else:
        for line in _run(["uname", "-m"]):
            cpu["model"] = line.strip(); break
        for line in _run(["grep", "-m1", "cpu MHz", "/proc/cpuinfo"]):
            try:
                cpu["freq_mhz"] = int(float(line.split(":")[1].strip()))
            except (ValueError, IndexError):
                pass
            break
        for line in _run(["nproc"]):
            try: cpu["cores"] = int(line.strip())
            except ValueError: pass
            break
        for line in _run(["grep", "MemTotal", "/proc/meminfo"]):
            try: mem["total"] = int(line.split()[1]) * 1024
            except (ValueError, IndexError): pass
            break
        for line in _run(["grep", "MemAvailable", "/proc/meminfo"]):
            try: mem["free"] = int(line.split()[1]) * 1024
            except (ValueError, IndexError): pass
            break
        for line in _run(["getconf", "PAGE_SIZE"]):
            try: mem["page_size"] = int(line.strip())
            except ValueError: pass
            break
        for line in _run(["grep", "btime", "/proc/stat"]):
            try: uptime = int(time.time()) - int(line.split()[1])
            except (ValueError, IndexError, ImportError): pass
            break

        vmstat_lines = _run(["vmstat", "1", "2"])
        if len(vmstat_lines) >= 3:
            header = vmstat_lines[1].split()
            data = vmstat_lines[-1].split()
            try:
                cpu["user"] = float(data[header.index("us")])
                cpu["sys"] = float(data[header.index("sy")])
                cpu["idle"] = float(data[header.index("id")])
            except (ValueError, IndexError, AttributeError):
                pass

    mem["free"] = max(mem["free"], 0)
    mem["used"] = max(mem["total"] - mem["free"], 0)

    return {
        "cpu": cpu,
        "memory": mem,
        "uptime": uptime,
        "memory_unit": config.get("ui", {}).get("memory_unit", "GB"),
        "language": config.get("ui", {}).get("language", "en"),
    }


def get_system_info():
    info = {}
    obe = _is_openbsd()
    if obe:
        pairs = {
            "hostname": "kern.hostname", "ostype": "kern.ostype",
            "osrelease": "kern.osrelease", "osversion": "kern.osversion",
            "machine": "hw.machine", "model": "hw.model",
        }
        for key, oid in pairs.items():
            lines = _run(["/sbin/sysctl", "-n", oid])
            if lines:
                info[key] = lines[0].strip()
    else:
        for line in _run(["uname", "-n"]):
            info["hostname"] = line.strip(); break
        for line in _run(["uname", "-o"]):
            info["ostype"] = line.strip(); break
        for line in _run(["uname", "-r"]):
            info["osrelease"] = line.strip(); break
        for line in _run(["uname", "-m"]):
            info["machine"] = line.strip(); break
        if "ostype" in info:
            info["osversion"] = info["osrelease"]
        for line in _run(["uname", "-m"]):
            info["model"] = line.strip(); break
    return info


def mount_fs(device, mountpoint, fstype=""):
    obe = _is_openbsd()
    args = ["/sbin/mount"] if obe else ["mount"]
    if fstype:
        args += ["-t", fstype]
    args += [device, mountpoint]
    return subprocess.run(args, capture_output=True, text=True)


def umount_fs(mountpoint):
    obe = _is_openbsd()
    cmd = ["/sbin/umount"] if obe else ["umount"]
    return subprocess.run(cmd + [mountpoint], capture_output=True, text=True)
