# Sales Analytics ETL (Polars) — container image
#
# Installs ODBC Driver 17 for SQL Server on top of python:3.13-slim (Debian
# 12/bookworm), following Microsoft's documented apt steps, then installs
# the project's Python dependencies.

FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

# ── ODBC Driver 17 for SQL Server ──────────────────────────
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg2 ca-certificates \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list \
        | sed 's#\[arch=amd64#[signed-by=/usr/share/keyrings/microsoft-prod.gpg arch=amd64#' \
        > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql17 unixodbc-dev \
    && apt-get purge -y curl gnupg2 \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# sales_analytics_etl.ini is intentionally NOT baked into the image —
# mount it as a volume at runtime (see docker-compose.yml).
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
