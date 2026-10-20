# Imagem do Taldo Manager: API + frontend num container só.
FROM python:3.12-slim

WORKDIR /app/backend
COPY backend/requirements.txt .
# só as dependências de execução (pytest e httpx ficam de fora)
RUN grep -v -E "^(pytest|httpx)" requirements.txt > runtime.txt \
    && pip install --no-cache-dir -r runtime.txt

COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

# o banco fica num volume, fora da imagem: atualizar não apaga os saves
ENV TALDO_DB=/dados/taldo_manager.db \
    TALDO_COOKIE_SEGURO=1 \
    PYTHONUNBUFFERED=1
VOLUME /dados

EXPOSE 8000
# --proxy-headers: o IP do jogador vem do Caddy (para o freio de tentativas)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
