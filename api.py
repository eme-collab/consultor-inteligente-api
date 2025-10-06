# -*- coding: utf-8 -*-

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend_logic import ConsultorInteligente
import traceback # Importamos a biblioteca para formatar o erro

# --- Modelos de Dados ---
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

# --- Carregamento do Modelo de IA ---
consultor = ConsultorInteligente()

# --- Endpoints da API ---
@app.get("/")
def read_root():
    return {"status": "API do Consultor Inteligente está no ar!"}

@app.post("/consultar", response_model=ApiResponse)
async def consultar_celular(user_query: UserQuery):
    print(f"Recebida consulta via API: \"{user_query.query}\"")
    
    try:
        # TENTAMOS EXECUTAR A LÓGICA PRINCIPAL
        recomendacao = consultor.obter_recomendacao(user_query.query)
        return {"response": recomendacao}
    
    except Exception as e:
        # SE QUALQUER ERRO ACONTECER, NÓS O CAPTURAMOS AQUI
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!!      UM ERRO INESPERADO OCORREU       !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        
        # Imprimimos o relatório completo do erro no log do Render
        error_traceback = traceback.format_exc()
        print(error_traceback)
        
        # Levantamos uma exceção HTTP 500 com a mensagem de erro exata
        raise HTTPException(
            status_code=500, 
            detail=f"Erro interno no servidor: {str(e)}"
        )

