FROM python:3.11-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY ui ./ui
COPY start-space.sh .
RUN chmod +x start-space.sh
EXPOSE 8000 8501 7860
CMD ["./start-space.sh"]
