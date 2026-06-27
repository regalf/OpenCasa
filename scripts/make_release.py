#!/usr/bin/env python3
"""Create a release tarball for OpenCasa.

Usage: python3 scripts/make_release.py v1.2.0
"""
import sys, os, tarfile, io, json, subprocess

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/make_release.py <version>", file=sys.stderr)
        sys.exit(1)
    version = sys.argv[1]
    if not version.startswith("v"):
        print("Version must start with 'v' (e.g. v1.2.0)", file=sys.stderr)
        sys.exit(1)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root)

    # verify version matches __init__.py
    init_py = os.path.join(root, "backend", "webui", "__init__.py")
    with open(init_py) as f:
        if f'__version__ = "{version}"' not in f.read():
            print(f"ERROR: __version__ in __init__.py does not match {version}", file=sys.stderr)
            sys.exit(1)

    # verify git tag
    try:
        tags = subprocess.check_output(["git", "tag", "--points-at", "HEAD"], text=True).strip().split()
        if version not in tags:
            print(f"WARNING: tag {version} not on HEAD. Continue? [y/N] ", end="", file=sys.stderr)
            if input().lower() != "y":
                sys.exit(1)
    except subprocess.CalledProcessError:
        pass

    include_patterns = [
        "backend/",
        "frontend/dist/",
        "scripts/",
        "examples/apps/",
        "opencasa.json.example",
        "README.md",
        "CHANGELOG.md",
        "LICENSE",
    ]

    out_name = f"OpenCasa-{version}.tar.gz"
    with tarfile.open(out_name, "w:gz") as tar:
        for pattern in include_patterns:
            if os.path.isfile(pattern):
                tar.add(pattern, arcname=f"OpenCasa-{version}/{pattern}")
            elif os.path.isdir(pattern):
                for dirpath, dirnames, filenames in os.walk(pattern):
                    for fn in filenames:
                        fp = os.path.join(dirpath, fn)
                        tar.add(fp, arcname=f"OpenCasa-{version}/{fp}")
            else:
                print(f"WARNING: {pattern} not found", file=sys.stderr)

    size = os.path.getsize(out_name)
    print(f"Created {out_name} ({size / 1024:.0f} KB)")

if __name__ == "__main__":
    main()
