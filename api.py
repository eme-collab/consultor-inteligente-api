# -*- coding: utf-8 -*-

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend_logic import ConsultorInteligente
import logging
import json # <-- NOVO IMPORT
from cachetools import TTLCache # <-- NOVO IMPORT

logging.basicConfig(level=logging.INFO)

# --- Modelos de Dados ---
class UserQuery(BaseModel):
    query: str
class ApiResponse(BaseModel):
    response: str

# --- Inicialização da API e Cache ---
app = FastAPI(title="API do Consultor Inteligente", version="1.0.0")

# <-- NOVO: Configuração do Cache -->
# Cache com no máximo 500 itens e tempo de vida de 1 hora (3600 segundos)
cache = TTLCache(maxsize=500, ttl=3600)
logging.info("Cache Inteligente inicializado.")

# --- Configuração de CORS ---
# ... (sem mudanças aqui) ...
origins = ["https://consultor-inteligente-frontend.onrender.com"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Carregamento do Modelo de IA ---
consultor = None
try:
    consultor = ConsultorInteligente()
except Exception as e:
    logging.critical(f"ERRO CRÍTICO AO INICIALIZAR O CONSULTOR: {e}", exc_info=True)

# --- Endpoints da API ---
@app.get("/")
def read_root():
    return {"status": "API do Consultor Inteligente está no ar!"}

# <-- MUDANÇA: O endpoint de consulta agora usa o cache -->
@app.post("/consultar", response_model=ApiResponse)
async def consultar_celular(user_query: UserQuery):
    if not consultor:
        raise HTTPException(status_code=503, detail="Serviço indisponível: Modelo de IA não inicializado.")

    logging.info(f"Recebida consulta via API: \"{user_query.query}\"")
    
    try:
        # Etapa 1: Captar intenção (sempre acontece)
        intencao = consultor.captar_intencao(user_query.query)
        if not intencao:
            return {"response": "Desculpe, não consegui entender o que você precisa."}

        # Cria uma chave de cache estável a partir da intenção
        # Ordenar as chaves garante que dicionários com a mesma info mas ordem diferente tenham a mesma chave
        cache_key = json.dumps(intencao, sort_keys=True)

        # Etapa 2: Verificar o cache
        if cache_key in cache:
            logging.info(f"Cache HIT para a intenção: {cache_key}")
            return {"response": cache[cache_key]}
        
        logging.info(f"Cache MISS para a intenção: {cache_key}. Gerando nova recomendação.")
        
        # Etapa 3: Se não está no cache, gera a recomendação
        recomendacao = consultor.gerar_recomendacao_sem_cache(intencao)
        
        # Etapa 4: Armazena o novo resultado no cache antes de retornar
        cache[cache_key] = recomendacao
        
        return {"response": recomendacao}
        
    except Exception as e:
        logging.error(f"Erro inesperado ao processar a consulta '{user_query.query}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ocorreu um erro interno no servidor.")