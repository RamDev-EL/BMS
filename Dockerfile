# Production image: API + built-in web admin (/app) + driver PWA (/driver)
FROM python:3.12-slim
WORKDIR /code
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY web /srv/web
COPY driver /srv/driver
ENV UPLOAD_DIR=/data/uploads
CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
