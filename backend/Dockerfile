FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x entrypoint.sh && useradd -m app && mkdir -p /srv/uploads && chown -R app /srv
USER app
EXPOSE 8000
CMD ["./entrypoint.sh"]
