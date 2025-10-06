# -*- coding: utf-8 -*-

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend_logic import ConsultorInteligente
import logging

# Configuração do logging para ver detalhes no Render
logging.basicConfig(level=logging.INFO)

# --- Modelos de Dados (para validação) ---
class UserQuery(BaseModel):
    query: str

class ApiResponse(BaseModel):
    response: str

# --- Inicialização da API ---
app = FastAPI(
    title="API do Consultor Inteligente",
    description="API para receber consultas de usuários e retornar recomendações de celulares.",
    version="1.0.0"
)

# --- Configuração de CORS (VERSÃO CORRIGIDA E FINAL) ---
# Essencial para permitir que o seu site (front-end) possa fazer requisições para esta API.
origins = [
    "https://consultor-inteligente-frontend.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Permite todos os métodos (GET, POST, etc.)
    allow_headers=["*"], # Permite todos os cabeçalhos
)

# --- Carregamento do Modelo de IA ---
consultor = None
try:
    consultor = ConsultorInteligente()
except Exception as e:
    logging.critical(f"ERRO CRÍTICO AO INICIALIZAR O CONSULTOR: {e}", exc_info=True)
    # A API vai rodar, mas o endpoint /consultar retornará um erro.

# --- Endpoints da API ---
@app.get("/")
def read_root():
    """Endpoint inicial para verificar se a API está funcionando."""
    return {"status": "API do Consultor Inteligente está no ar!"}

@app.post("/consultar", response_model=ApiResponse)
async def consultar_celular(user_query: UserQuery):
    """
    Recebe a consulta do usuário, processa usando a classe ConsultorInteligente
    e retorna a recomendação formatada.
    """
    if not consultor:
        logging.error("O endpoint /consultar foi chamado, mas o modelo de IA não foi carregado.")
        raise HTTPException(status_code=503, detail="Serviço indisponível: O modelo de IA não pôde ser inicializado.")

    logging.info(f"Recebida consulta via API: \"{user_query.query}\"")
    
    try:
        recomendacao = consultor.obter_recomendacao(user_query.query)
        return {"response": recomendacao}
    except Exception as e:
        logging.error(f"Erro inesperado ao processar a consulta '{user_query.query}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno no servidor ao processar sua solicitação.")

