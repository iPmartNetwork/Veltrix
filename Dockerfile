FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OUTPANEL_HOST=0.0.0.0 \
    OUTPANEL_PORT=8000 \
    OUTPANEL_DB=/app/data/veltrix.db \
    OUTPANEL_BACKUP_DIR=/app/backups \
    OUTPANEL_MONITOR_INTERVAL=30

WORKDIR /app

RUN addgroup --system veltrix \
    && adduser --system --ingroup veltrix --home /app --no-create-home veltrix

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && if [ -s /app/requirements.txt ]; then pip install --no-cache-dir -r /app/requirements.txt; fi

COPY --chown=veltrix:veltrix outpanel /app/outpanel
COPY --chown=veltrix:veltrix web /app/web
COPY --chown=veltrix:veltrix docs /app/docs
COPY --chown=veltrix:veltrix README.md /app/README.md

RUN mkdir -p /app/data /app/backups /app/logs \
    && chown -R veltrix:veltrix /app

USER veltrix

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"

CMD ["python", "-m", "outpanel.app"]
