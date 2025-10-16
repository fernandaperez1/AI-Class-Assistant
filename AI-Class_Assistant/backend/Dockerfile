FROM python:3.11-slim

# Install system dependencies (LibreOffice for pptx → png)
RUN apt-get update && apt-get install -y \
    libreoffice \
    fonts-dejavu \
    && apt-get clean

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
CMD ["python", "app.py"]
