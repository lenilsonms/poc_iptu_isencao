FROM python:3.11-slim

# Evita que o Python grave arquivos .pyc no disco e desativa o buffer de saída
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependências do sistema
# CORREÇÃO: libgl1-mesa-glx substituído por libgl1 para compatibilidade com Debian atual
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libstdc++6 \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia o arquivo de dependências primeiro para aproveitar o cache de camadas do Docker
COPY requirements.txt .

# Atualiza o pip e instala as dependências
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação e as pastas de configuração estruturadas
COPY config/ ./config/
COPY poc_iptu/ ./poc_iptu/
COPY frontend/ ./frontend/

# Expõe a porta nativa do Streamlit
EXPOSE 8501

# Comando para rodar a aplicação mapeando porta e endereço corretos para o container
CMD ["uvicorn", "poc_iptu.api.main:app", "--host", "0.0.0.0", "--port", "8000"]