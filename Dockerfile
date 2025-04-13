FROM python:3.11-slim

RUN apt-get update && apt-get install -y nginx curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./
COPY templates/ ./templates/
COPY nginx.conf /etc/nginx/sites-available/default
COPY start.sh .

EXPOSE 80

CMD ["./start.sh"]
