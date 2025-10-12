# -*- coding: utf-8 -*-

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend_logic import ConsultorInteligente
import logging
from datetime import datetime # <-- NOVO: Import para registrar a data e hora

# Configuração do logging
logging.basicConfig(level=logging.INFO)

# --- Modelos de Dados (Pydantic) ---
class UserQuery(BaseModel):
    query: str

class ApiResponse(BaseModel):
    response: str

# --- Inicialização da API ---
app = FastAPI(
    title="API do Consultor Inteligente",
    description="API para receber consultas de usuários e retornar recomendações de celulares com base em um banco de dados JSON local.",
    version="2.0.0"
)

# --- Configuração de CORS (Cross-Origin Resource Sharing) ---
origins = [
    "https://consultor-inteligente-frontend.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Carregamento do Modelo de IA e Banco de Dados ---
consultor = None
try:
    consultor = ConsultorInteligente()
except Exception as e:
    logging.critical(f"ERRO CRÍTICO AO INICIALIZAR O CONSULTOR: {e}", exc_info=True)

# --- Endpoints da API ---
@app.get("/")
def read_root():
    """Endpoint inicial para verificar se a API está funcionando."""
    return {"status": "API do Consultor Inteligente v2.0 está no ar!"}

@app.post("/consultar", response_model=ApiResponse)
async def consultar_celular(user_query: UserQuery):
    """
    Recebe a consulta do usuário, passa para o método principal do consultor
    e retorna a recomendação completa em HTML.
    """
    if not consultor:
        logging.error("O endpoint /consultar foi chamado, mas o modelo de IA não foi carregado.")
        raise HTTPException(status_code=503, detail="Serviço indisponível: O modelo de IA não pôde ser inicializado.")

    logging.info(f"Recebida consulta via API: \"{user_query.query}\"")
    
    # <-- NOVO: Bloco para registrar a consulta do usuário em um arquivo -->
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open("consultas_usuarios.log", "a", encoding="utf-8") as f:
            f.write(f"{timestamp} | {user_query.query}\n")
    except Exception as e:
        logging.error(f"Falha ao registrar a consulta do usuário no arquivo de log: {e}")
    # <-- Fim do bloco de registro -->

    try:
        recomendacao = consultor.gerar_recomendacao_completa(user_query.query)
        return {"response": recomendacao}
        
    except Exception as e:
        logging.error(f"Erro inesperado ao processar a consulta '{user_query.query}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ocorreu um erro interno no servidor ao processar sua solicitação.")