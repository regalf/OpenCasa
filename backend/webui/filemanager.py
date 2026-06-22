"""File system: list, read, write, upload, download, delete, rename, mkdir."""

import datetime
import json
import mimetypes
import os
import re

from . import config, DATA_DIR, CONFIG_PATH


def _is_blocked(path):
    real = os.path.realpath(path)
    if CONFIG_PATH and real == os.path.realpath(CONFIG_PATH):
        return True
    return False


def _check_path(path, handler=None):
    path = os.path.realpath(path)
    if handler and getattr(handler, "_is_root", False):
        return True
    prefixes = config.get("filesystem", {}).get("allowed_prefixes", [])
    return any(path.startswith(os.path.realpath(p)) for p in prefixes)


def handle_list_files(handler, path):
    try:
        if not _check_path(path, handler):
            return handler._send_error(403, "access denied")
        items = []
        for entry in os.scandir(path):
            try:
                is_dir = entry.is_dir()
                st = entry.stat()
                items.append((not is_dir, entry.name.lower(), {
                    "name": entry.name,
                    "size": st.st_size,
                    "is_dir": is_dir,
                    "mode": oct(st.st_mode),
                    "mod_time": datetime.datetime.fromtimestamp(st.st_mtime).strftime(
                        "%Y-%m-%dT%H:%M:%S"
                    ),
                }))
            except (PermissionError, OSError):
                pass
        entries = [e for _, _, e in sorted(items)]
        return handler._send_json({"path": path, "entries": entries})
    except (FileNotFoundError, PermissionError) as e:
        return handler._send_error(404, str(e))
    except OSError as e:
        return handler._send_error(500, str(e))


def handle_read_file(handler, path):
    if not _check_path(path, handler) or _is_blocked(path):
        return handler._send_error(403, "access denied")
    try:
        with open(path) as f:
            content = f.read()
        return handler._send_json({"content": content})
    except (FileNotFoundError, PermissionError) as e:
        return handler._send_error(404, str(e))
    except OSError as e:
        return handler._send_error(500, str(e))


def handle_download(handler, path):
    if not _check_path(path, handler) or _is_blocked(path):
        return handler._send_error(403, "access denied")
    if not os.path.isfile(path):
        return handler._send_error(404, "file not found")
    handler.send_response(200)
    handler.send_header(
        "Content-Disposition",
        f'attachment; filename="{os.path.basename(path)}"',
    )
    mime, _ = mimetypes.guess_type(path)
    handler.send_header("Content-Type", mime or "application/octet-stream")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    with open(path, "rb") as f:
        handler.wfile.write(f.read())


def handle_upload(handler, params):
    content_type = handler.headers.get("Content-Type", "")
    if "multipart/form-data" not in content_type:
        return handler._send_error(400, "multipart/form-data required")
    if "boundary=" not in content_type:
        return handler._send_error(400, "missing boundary in Content-Type")
    boundary = content_type.split("boundary=", 1)[1].strip()
    body = handler._read_body()
    dest_path = ""
    file_data = b""
    filename = "uploaded"
    for part in body.split(("--" + boundary).encode()):
        if not part or part.strip() == b"--" or part.strip() == b"":
            continue
        header_end = part.find(b"\r\n\r\n")
        if header_end == -1:
            continue
        headers_raw = part[:header_end].decode("utf-8", errors="replace")
        data = part[header_end + 4:]
        while data.endswith(b"\r\n"):
            data = data[:-2]
        if data.endswith(b"--"):
            data = data[:-2]
        m_name = re.search(r'name="([^"]*)"', headers_raw)
        field_name = m_name.group(1) if m_name else ""
        if field_name == "path":
            dest_path = data.decode("utf-8", errors="replace").strip()
        elif re.search(r'filename="([^"]*)"', headers_raw):
            m_file = re.search(r'filename="([^"]*)"', headers_raw)
            filename = m_file.group(1)
            file_data = data
    if not dest_path:
        dest_path = params.get("path", filename)
    if not _check_path(dest_path, handler) or _is_blocked(dest_path):
        return handler._send_error(403, "access denied")
    if not file_data:
        return handler._send_error(400, "no file data received")
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(file_data)
    return handler._send_json({"name": filename, "size": os.path.getsize(dest_path), "path": dest_path})


def handle_write_file(handler):
    data = handler._json_body()
    if not data:
        return handler._send_error(400, "invalid body")
    if not _check_path(data["path"], handler) or _is_blocked(data["path"]):
        return handler._send_error(403, "access denied")
    try:
        os.makedirs(os.path.dirname(data["path"]), exist_ok=True)
        with open(data["path"], "w") as f:
            f.write(data["content"])
        return handler._send_json({"success": True})
    except (OSError, IOError) as e:
        return handler._send_error(500, str(e))


def handle_rename_file(handler):
    data = handler._json_body()
    if not data:
        return handler._send_error(400, "invalid body")
    for p in (data.get("old_path", ""), data.get("new_path", "")):
        if not _check_path(p, handler) or _is_blocked(p):
            return handler._send_error(403, "access denied")
    try:
        os.rename(data["old_path"], data["new_path"])
        return handler._send_json({"success": True})
    except OSError as e:
        return handler._send_error(500, str(e))


def handle_delete_file(handler):
    data = handler._json_body()
    if not data:
        return handler._send_error(400, "invalid body")
    path_to_remove = data.get("path", "")
    if not _check_path(path_to_remove, handler) or _is_blocked(path_to_remove):
        return handler._send_error(403, "access denied")
    try:
        if os.path.isdir(path_to_remove):
            import shutil
            shutil.rmtree(path_to_remove)
        else:
            os.remove(path_to_remove)
        return handler._send_json({"success": True})
    except OSError as e:
        return handler._send_error(500, str(e))


def handle_mkdir(handler):
    data = handler._json_body()
    if not data:
        return handler._send_error(400, "invalid body")
    if not _check_path(data["path"], handler) or _is_blocked(data["path"]):
        return handler._send_error(403, "access denied")
    try:
        os.makedirs(data["path"], exist_ok=True)
        return handler._send_json({"success": True})
    except OSError as e:
        return handler._send_error(500, str(e))


def handle_list_disks(handler):
    from .system import list_disks, get_disk_info
    names = list_disks()
    disks = []
    for name in names:
        info = get_disk_info(name)
        if info:
            disks.append(info)
    return handler._send_json({"disks": disks})
