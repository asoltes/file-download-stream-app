# Use a lightweight Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY app.py .
COPY templates/ ./templates/

# Expose Flask default port
EXPOSE 5000

# Start the app
CMD ["python", "app.py"]
