FROM ai-talent-runtime:dev
WORKDIR /app/backend
COPY backend/app ./app
COPY backend/tests ./tests
COPY backend/pytest.ini ./pytest.ini
RUN useradd --create-home --uid 10001 talent
USER talent
CMD ["uvicorn","app.main:build_app","--factory","--host","0.0.0.0","--port","8000"]
