# Release Process

## Requirements
- Git tag on `main` branch (e.g. `v1.2.0`)
- GitHub repository: `github.com/regalf/OpenCasa`
- Python 3 to run `make_release.py`

## Steps

### 1. Update version
Edit `backend/webui/__init__.py`:
```python
__version__ = "1.2.0"
```

### 2. Update CHANGELOG.md
Add a new section under `## Unreleased` or at the top:
```markdown
## v1.2.0 (2026-MM-DD)
### Features
- ...
### Bug Fixes
- ...
```

### 3. Create release artifact
```sh
python3 scripts/make_release.py v1.2.0
```
This produces `OpenCasa-v1.2.0.tar.gz` in the project root.

### 4. Commit, tag, push
```sh
git add -A
git commit -m "v1.2.0"
git tag v1.2.0
git push origin main --tags
```

### 5. Publish GitHub Release
```sh
gh release create v1.2.0 \
  --title "v1.2.0" \
  --notes "$(python3 scripts/extract_changelog.py v1.2.0)" \
  OpenCasa-v1.2.0.tar.gz
```

### 6. Install from release
```sh
# One-liner (auto-downloads latest release)
doas sh -c "$(curl -sL https://raw.githubusercontent.com/regalf/OpenCasa/main/scripts/install-release.sh)"

# Or with a specific tarball
doas sh scripts/install-release.sh /path/to/OpenCasa-v1.2.0.tar.gz
```

## Version numbering
- **Stable** (`v1.2.0`): full semver, pushed to GitHub Releases
- **Nightly** (`main` branch): no tag, installed via `git clone`, updates via `git pull`
