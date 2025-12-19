# Playwright in Docker: A Complete Setup Guide

This guide documents a production-tested Playwright setup in Docker that solves common environment issues. Use this as a reference for your own projects.

## Overview

Playwright in Docker can be challenging due to:

* Browser dependency management
* File permissions with non-root users
* Persistent browser profiles
* System library requirements
* Volume mount complexities

Our setup successfully addresses all these issues.

## The Working Dockerfile

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1. Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Python dependencies (including playwright package)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Install Playwright browsers with system deps AS ROOT
# This is the critical step that many setups get wrong
RUN playwright install --with-deps chromium && \
    # Move browsers to shared location accessible by all users
    mkdir -p /ms-playwright && \
    cp -r /root/.cache/ms-playwright/* /ms-playwright/ && \
    chmod -R 755 /ms-playwright

# 4. Copy application code
COPY app ./app

# 5. Create directories for outputs and browser profile
RUN mkdir -p /app/app/jobs_output /app/app/test_output

# 6. Create symlinks for easier path handling
RUN ln -s /app/app/jobs_output /app/jobs_output && \
    ln -s /app/app/test_output /app/test_output

# 7. Create non-root user and set permissions
# CRITICAL: Ensure browser profile directory is writable
RUN useradd -m appuser && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app/app/mcp-chrome

# 8. Switch to non-root user for security
USER appuser

# 9. Tell Playwright where to find browsers
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Key Concepts Explained

### 1. Install Browsers as Root, Then Share

**The Problem:** By default, `playwright install` installs browsers to `~/.cache/ms-playwright`. When you switch to a non-root user, they can't access `/root/.cache/`.

**The Solution:**

```dockerfile
# Install as root (has permissions)
RUN playwright install --with-deps chromium && \
    # Create shared location
    mkdir -p /ms-playwright && \
    # Copy browsers to shared location
    cp -r /root/.cache/ms-playwright/* /ms-playwright/ && \
    # Make readable by all users
    chmod -R 755 /ms-playwright
```

**Why it works:** Browsers are installed once with all system dependencies, then moved to a location accessible to your non-root user.

### 2. Set PLAYWRIGHT\_BROWSERS\_PATH

```dockerfile
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
```

This environment variable tells Playwright where to find browsers. Without this, Playwright will look in `~/.cache/ms-playwright` and fail when running as non-root user.

### 3. The `--with-deps` Flag is Essential

```dockerfile
RUN playwright install --with-deps chromium
```

**What it does:** Installs all system dependencies required by Chromium (fonts, graphics libraries, etc.)

**Without it:** You'll get cryptic errors like:

```
Error: browserType.launch: Executable doesn't exist at /ms-playwright/chromium-1234/chrome-linux/chrome
╔═══════════════════════════════════════════════════════╗
║ Looks like Playwright Test or Playwright was just    ║
║ installed or updated.                                  ║
║ Please run the following command to download new      ║
║ browsers:                                              ║
║                                                        ║
║     playwright install --with-deps                    ║
╚═══════════════════════════════════════════════════════╝
```

### 4. Persistent Browser Profiles

For maintaining cookies and session state between runs:

```python
# In your browser setup code
browser_context = browser.new_context(
    user_agent="...",
    viewport={"width": 1920, "height": 1080},
    storage_state="app/mcp-chrome/storage_state.json"  # Persistent storage
)
```

**Docker considerations:**

```dockerfile
# Ensure profile directory is writable by non-root user
RUN useradd -m appuser && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app/app/mcp-chrome
```

**In docker-compose.yaml:**

```yaml
services:
  api:
    volumes:
      # Persist browser profile across container restarts
      - ./app/mcp-chrome:/app/app/mcp-chrome
```

### 5. Volume Mounts and Symlinks

**The Challenge:** Code uses relative paths, but Docker volumes need absolute paths.

**The Solution:** Create symlinks during build

```dockerfile
# Create output directories inside app folder
RUN mkdir -p /app/app/jobs_output /app/app/test_output

# Create symlinks at /app level pointing to /app/app directories
RUN ln -s /app/app/jobs_output /app/jobs_output && \
    ln -s /app/app/test_output /app/test_output
```

**In docker-compose.yaml:**

```yaml
volumes:
  - ./jobs_output:/app/app/jobs_output
  - ./test_output:/app/app/test_output
```

Now code can use paths like `jobs_output/file.txt` and it works both locally and in Docker.

### 6. Security: Non-Root User

**Why:** Running as root in containers is a security risk.

**How to do it right:**

```dockerfile
# Create user
RUN useradd -m appuser

# Set ownership of ALL directories the app needs to write to
RUN chown -R appuser:appuser /app

# Ensure specific writable directories have correct permissions
RUN chmod -R 755 /app/app/mcp-chrome

# Switch to non-root user
USER appuser
```

**Common mistake:** Forgetting to set ownership before switching users. The non-root user won't be able to write to directories owned by root.

## Complete docker-compose.yaml Example

```yaml
version: '3.8'

services:
  api:
    build: .
    container_name: playwright-api
    environment:
      - PYTHONUNBUFFERED=1
      # Add any other env vars your app needs
    volumes:
      # Persist browser profile
      - ./app/mcp-chrome:/app/app/mcp-chrome
      # Persist outputs
      - ./jobs_output:/app/app/jobs_output
      - ./test_output:/app/app/test_output
    ports:
      - "8000:8000"
    restart: unless-stopped
    # Optional: increase shared memory for browser stability
    shm_size: '2gb'
```

## Python Requirements

```txt
# requirements.txt
playwright==1.55.0
# ... other dependencies
```

## Common Issues and Solutions

### Issue 1: "Executable doesn't exist" Error

**Symptom:**

```
Error: browserType.launch: Executable doesn't exist at /ms-playwright/chromium-*/chrome-linux/chrome
```

**Solutions:**

1. Ensure you ran `playwright install --with-deps chromium` in Dockerfile
2. Verify `PLAYWRIGHT_BROWSERS_PATH=/ms-playwright` is set
3. Check that `/ms-playwright` has proper permissions (755)
4. Confirm you're installing browsers before switching to non-root user

### Issue 2: Permission Denied on Browser Profile

**Symptom:**

```
Error: EACCES: permission denied, open '/app/app/mcp-chrome/storage_state.json'
```

**Solutions:**

1. Set ownership: `chown -R appuser:appuser /app/app/mcp-chrome`
2. Set permissions: `chmod -R 755 /app/app/mcp-chrome`
3. Do this BEFORE switching to non-root user with `USER appuser`

### Issue 3: Missing System Dependencies

**Symptom:**

```
Error: Failed to launch chromium because executable doesn't exist
...
error while loading shared libraries: libgbm.so.1
```

**Solution:** Use `--with-deps` flag:

```dockerfile
RUN playwright install --with-deps chromium
```

### Issue 4: Timeout on Page Load

**Symptom:** Browser launches but pages timeout during navigation

**Solutions:**

1. Increase shared memory in docker-compose.yaml:
   ```yaml
   shm_size: '2gb'
   ```
2. Adjust timeouts in your Playwright code:
   ```python
   page.goto(url, timeout=60000)  # 60 seconds
   ```

### Issue 5: Volume Mount Path Confusion

**Symptom:** Files aren't where you expect them, or "file not found" errors

**Solution:** Use the symlink approach:

```dockerfile
# In Dockerfile
RUN ln -s /app/app/jobs_output /app/jobs_output

# In docker-compose.yaml
volumes:
  - ./jobs_output:/app/app/jobs_output

# In your code, use relative paths
output_path = "jobs_output/file.txt"  # Works!
```

## Python Code Examples

### Basic Browser Setup

```python
from playwright.sync_api import sync_playwright

def get_browser_context():
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=True,
        args=[
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu'
        ]
    )
    
    context = browser.new_context(
        user_agent="Mozilla/5.0 ...",
        viewport={"width": 1920, "height": 1080},
        # Optional: persistent profile
        storage_state="app/mcp-chrome/storage_state.json"
    )
    
    return playwright, browser, context
```

### With Persistent Session

```python
import os
from pathlib import Path

def setup_persistent_browser():
    profile_dir = Path("app/mcp-chrome")
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    storage_state_file = profile_dir / "storage_state.json"
    
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    
    # Load existing session if available
    if storage_state_file.exists():
        context = browser.new_context(
            storage_state=str(storage_state_file)
        )
    else:
        context = browser.new_context()
    
    # Save session on close
    # In your cleanup code:
    # context.storage_state(path=str(storage_state_file))
    
    return playwright, browser, context
```

## Testing Your Setup

### 1. Test Script

```python
# test_playwright.py
from playwright.sync_api import sync_playwright

def test_playwright():
    print("Starting Playwright test...")
    
    with sync_playwright() as p:
        print(f"Browser path: {p.chromium.executable_path}")
        
        browser = p.chromium.launch(headless=True)
        print("✓ Browser launched successfully")
        
        page = browser.new_page()
        print("✓ Page created")
        
        page.goto("https://example.com", timeout=30000)
        print(f"✓ Page loaded: {page.title()}")
        
        browser.close()
        print("✓ Test completed successfully!")

if __name__ == "__main__":
    test_playwright()
```

### 2. Run Test in Docker

```bash
# Build container
docker compose build

# Run test
docker compose run --rm api python test_playwright.py
```

Expected output:

```
Starting Playwright test...
Browser path: /ms-playwright/chromium-1234/chrome-linux/chrome
✓ Browser launched successfully
✓ Page created
✓ Page loaded: Example Domain
✓ Test completed successfully!
```

## Best Practices

### 1. Pin Playwright Version

```txt
# requirements.txt
playwright==1.55.0  # Not just "playwright" or "playwright>=1.0"
```

**Why:** Playwright updates frequently. Pinning prevents breaking changes.

### 2. Use Slim Base Images

```dockerfile
FROM python:3.12-slim
```

**Why:** Full Python images are 900MB+, slim images are ~150MB. Playwright adds ~300MB, so final image is ~450MB instead of 1.2GB+.

### 3. Clean Up APT Cache

```dockerfile
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*
```

**Why:** Reduces image size by ~100MB.

### 4. Use .dockerignore

```
# .dockerignore
**/__pycache__
**/*.pyc
**/.pytest_cache
**/.venv
.git
.env
jobs_output/
test_output/
```

**Why:** Prevents copying unnecessary files into image, speeds up builds.

### 5. Multi-Stage Builds (Optional)

For even smaller images:

```dockerfile
# Stage 1: Install browsers
FROM python:3.12-slim AS browser-installer
RUN apt-get update && apt-get install -y wget gnupg
COPY requirements.txt .
RUN pip install playwright
RUN playwright install --with-deps chromium

# Stage 2: Final image
FROM python:3.12-slim
COPY --from=browser-installer /ms-playwright /ms-playwright
# ... rest of Dockerfile
```

## Debugging Tips

### 1. Check Browser Installation

```bash
docker compose run --rm api python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); print(p.chromium.executable_path)"
```

Expected output: `/ms-playwright/chromium-1234/chrome-linux/chrome`

### 2. Check Permissions

```bash
docker compose run --rm api ls -la /ms-playwright/
docker compose run --rm api ls -la /app/app/mcp-chrome/
```

Look for `drwxr-xr-x` (755) or better.

### 3. Run Browser in Debug Mode

```python
browser = playwright.chromium.launch(
    headless=False,  # Show browser window
    slow_mo=1000,    # Slow down operations by 1s
    devtools=True    # Open DevTools
)
```

Note: `headless=False` won't work in Docker without X11 forwarding, but changing it will show you if the issue is browser launch vs rendering.

### 4. Check Environment Variables

```bash
docker compose run --rm api env | grep PLAYWRIGHT
```

Expected: `PLAYWRIGHT_BROWSERS_PATH=/ms-playwright`

## Architecture Decisions

Our setup makes these specific choices:

1. **Chromium only** - Installs only `chromium`, not all browsers, to save ~600MB
2. **Shared browser location** - `/ms-playwright` accessible to all users
3. **Non-root user** - `appuser` for security
4. **Persistent profiles** - Volume mount for `mcp-chrome` directory
5. **Symlinks for paths** - Bridges relative/absolute path gap
6. **Synchronous API** - Uses `sync_playwright()` (simpler for our use case)

## Performance Considerations

### Browser Launch Time

* Cold start: ~2-3 seconds
* With persistent context: ~1-2 seconds
* Consider keeping browser instance alive for multiple operations

### Memory Usage

* Chromium baseline: ~200-300MB
* Per page: ~50-100MB
* Recommend: 1GB RAM minimum, 2GB+ for production

### Shared Memory

```yaml
# docker-compose.yaml
shm_size: '2gb'
```

**Why:** Browsers use `/dev/shm` for shared memory. Default is 64MB, which can cause crashes on complex pages.

## Alternatives Considered

### 1. Playwright Official Docker Image

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy
```

**Pros:** Pre-configured, works out of box
**Cons:**

* Much larger (~2GB vs ~450MB)
* Less control over configuration
* Runs as root by default

### 2. Installing Browsers at Runtime

```dockerfile
CMD ["sh", "-c", "playwright install chromium && uvicorn app.main:app"]
```

**Pros:** Simpler Dockerfile
**Cons:**

* Slower container start (~30s delay)
* Unreliable (network issues = container fails)
* Wastes bandwidth on every container restart

### 3. Volume Mount for Browsers

```yaml
volumes:
  - playwright-browsers:/ms-playwright
```

**Pros:** Browsers persist across rebuilds
**Cons:**

* Adds complexity
* Volume must be initialized
* Not needed if using proper layer caching

## Migration Guide

If you're migrating from an existing Playwright setup:

### From Local to Docker

1. Copy your Playwright code as-is
2. Use our Dockerfile as template
3. Add volume mounts for any directories your code writes to
4. Test with `docker compose run --rm api python test_playwright.py`

### From Official Playwright Image

1. Update Dockerfile to use slim base image
2. Add the browser installation steps from our guide
3. Create non-root user
4. Set `PLAYWRIGHT_BROWSERS_PATH`
5. Rebuild and test

### From Root User to Non-Root

1. Add after installing browsers:
   ```dockerfile
   RUN useradd -m appuser && \
       chown -R appuser:appuser /app && \
       chmod -R 755 /ms-playwright
   USER appuser
   ```
2. Ensure all writable directories are owned by `appuser`
3. Test write operations (browser profile, output files)

## Checklist for New Projects

Use this checklist when setting up Playwright in Docker:

* \[ ] Install system dependencies (`wget`, `gnupg`)
* \[ ] Install Playwright Python package
* \[ ] Run `playwright install --with-deps chromium` as root
* \[ ] Copy browsers to `/ms-playwright`
* \[ ] Set permissions on `/ms-playwright` (755)
* \[ ] Set `PLAYWRIGHT_BROWSERS_PATH=/ms-playwright`
* \[ ] Create non-root user
* \[ ] Set ownership on all app directories
* \[ ] Set permissions on writable directories (browser profile, outputs)
* \[ ] Switch to non-root user with `USER appuser`
* \[ ] Add volume mounts in docker-compose.yaml
* \[ ] Consider adding `shm_size: '2gb'`
* \[ ] Test with simple script
* \[ ] Test write operations (screenshots, downloads, profiles)

## Resources

* [Playwright Documentation](https://playwright.dev/python/docs/intro)
* [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
* [Playwright in Docker (Official Guide)](https://playwright.dev/python/docs/docker)

## Contributing

Found an issue with this guide or have improvements? This guide is based on our production setup at `/Users/jim/local-api-docker`. Check the actual Dockerfile and docker-compose.yaml for the most up-to-date configuration.

***

**Last Updated:** December 19, 2025\
**Playwright Version:** 1.55.0\
**Python Version:** 3.12\
**Status:** Production-tested ✅
