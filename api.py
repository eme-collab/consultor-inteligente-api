# -*- coding: utf-8 -*-

from fastapi import FastAPI, HTTPException, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend_logic import ConsultorInteligente
import logging
import os # <-- NOVO: Import para ler variáveis de ambiente
from datetime import datetime

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
    description="API para receber consultas de usuários e retornar recomendações.",
    version="2.1.0" # Versão com endpoint de log
)

# --- Configuração de CORS ---
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
    return {"status": "API do Consultor Inteligente v2.1 está no ar!"}

@app.post("/consultar", response_model=ApiResponse)
async def consultar_celular(user_query: UserQuery):
    if not consultor:
        raise HTTPException(status_code=503, detail="Serviço indisponível: Modelo de IA não inicializado.")

    logging.info(f"Recebida consulta via API: \"{user_query.query}\"")
    
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open("consultas_usuarios.log", "a", encoding="utf-8") as f:
            f.write(f"{timestamp} | {user_query.query}\n")
    except Exception as e:
        logging.error(f"Falha ao registrar a consulta do usuário no arquivo de log: {e}")

    try:
        recomendacao = consultor.gerar_recomendacao_completa(user_query.query)
        return {"response": recomendacao}
    except Exception as e:
        logging.error(f"Erro inesperado ao processar a consulta '{user_query.query}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ocorreu um erro interno no servidor.")


# <-- NOVO: Endpoint para visualizar o log de consultas -->
@app.get("/logs/consultas", response_class=Response)
def get_consultas_log(token: str = Query(...)):
    """
    Endpoint seguro para visualizar o arquivo de log de consultas.
    Requer um token de acesso passado como parâmetro na URL.
    """
    # Lê o token secreto das variáveis de ambiente
    correct_token = os.environ.get("LOG_ACCESS_TOKEN")

    # Verifica se o token fornecido é válido
    if not correct_token or token != correct_token:
        raise HTTPException(status_code=403, detail="Acesso negado: Token inválido.")

    try:
        # Tenta ler o arquivo de log
        with open("consultas_usuarios.log", "r", encoding="utf-8") as f:
            log_content = f.read()
        # Retorna o conteúdo como texto plano
        return Response(content=log_content, media_type="text/plain")
    except FileNotFoundError:
        return Response(content="Arquivo de log ainda não foi criado.", media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler o arquivo de log: {e}")