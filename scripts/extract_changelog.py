#!/usr/bin/env python3
"""Extract changelog section for a given version.

Usage: python3 scripts/extract_changelog.py v1.2.0
"""
import sys, os

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/extract_changelog.py <version>", file=sys.stderr)
        sys.exit(1)
    version = sys.argv[1]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    changelog = os.path.join(root, "CHANGELOG.md")

    with open(changelog) as f:
        content = f.read()

    # Find section ## v1.2.0
    marker = f"## {version}"
    start = content.find(marker)
    if start == -1:
        print(f"Section '{marker}' not found in CHANGELOG.md", file=sys.stderr)
        sys.exit(1)

    # Find next ## section
    next_section = content.find("\n## ", start + len(marker))
    if next_section == -1:
        section = content[start:]
    else:
        section = content[start:next_section]

    print(section.strip())

if __name__ == "__main__":
    main()
