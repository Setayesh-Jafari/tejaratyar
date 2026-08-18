FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=7860 APP_TIMEZONE=Asia/Tehran
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd -m -u 1000 user \
    && chown -R user:user /app
COPY --chown=user:user . .
USER user
EXPOSE 7860
CMD gunicorn app:app --bind 0.0.0.0:${PORT} --workers 1 --threads 8 --timeout 180
