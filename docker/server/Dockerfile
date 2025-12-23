FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CFPB_MCP_HOST=0.0.0.0

WORKDIR /app

# System deps for uvicorn[standard], general HTTP/TLS, and Playwright.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    ca-certificates \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast installer) in the image.
RUN pip install --no-cache-dir uv

# Copy dependency manifests first for better layer caching.
COPY pyproject.toml uv.lock ./

# Install runtime deps into the system interpreter.
# We intentionally exclude the dev group in the container.
RUN uv sync --frozen --no-dev

# Install Playwright browsers with system deps AS ROOT.
# This is critical: browsers must be installed before switching to non-root user.
RUN uv run playwright install --with-deps chromium && \
    # Move browsers to shared location accessible by all users
    mkdir -p /ms-playwright && \
    cp -r /root/.cache/ms-playwright/* /ms-playwright/ && \
    chmod -R 755 /ms-playwright

# Copy the app code last.
COPY server.py ./
COPY citations_mapping.py ./
COPY utils ./utils

# Create non-root user and set permissions.
RUN useradd -m appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user for security.
USER appuser

# Tell Playwright where to find browsers.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

EXPOSE 8000

CMD ["uv", "run", "python", "server.py"]
