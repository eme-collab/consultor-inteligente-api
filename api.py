# -*- coding: utf-8 -*-

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend_logic import ConsultorInteligente

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

# --- Configuração de CORS (VERSÃO CORRIGIDA) ---
# Esta é a configuração correta e explícita para permitir a comunicação.
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

# --- Carregamento do Modelo de IA ---
try:
    consultor = ConsultorInteligente()
except Exception as e:
    print(f"Erro Crítico ao inicializar o ConsultorInteligente: {e}")
    consultor = None

# --- Endpoints da API ---
@app.get("/")
def read_root():
    return {"status": "API do Consultor Inteligente está no ar!"}

@app.post("/consultar", response_model=ApiResponse)
async def consultar_celular(user_query: UserQuery):
    if not consultor:
        raise HTTPException(status_code=500, detail="Erro interno do servidor: O modelo de IA não foi carregado corretamente.")

    print(f"Recebida consulta via API: \"{user_query.query}\"")
    
    recomendacao = consultor.obter_recomendacao(user_query.query)
    
    return {"response": recomendacao}

