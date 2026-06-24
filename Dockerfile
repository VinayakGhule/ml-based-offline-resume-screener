FROM python:3.10-slim

WORKDIR /app

COPY requirements-demo.txt .
RUN pip install --no-cache-dir -r requirements-demo.txt

COPY . .

EXPOSE 7860

CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=7860", "--server.headless=true"]
