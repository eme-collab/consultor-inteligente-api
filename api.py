# -*- coding: utf-8 -*-

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend_logic import ConsultorInteligente # Importa a classe do arquivo que já criamos

# --- Modelos de Dados (para validação) ---
# Define como o corpo da requisição deve ser (um JSON com a chave "query")
class UserQuery(BaseModel):
    query: str

# Define como a resposta será (um JSON com a chave "response")
class ApiResponse(BaseModel):
    response: str


# --- Inicialização da API ---
app = FastAPI(
    title="API do Consultor Inteligente",
    description="API para receber consultas de usuários e retornar recomendações de celulares.",
    version="1.0.0"
)

# --- Configuração de CORS ---
# Essencial para permitir que o seu site (front-end) possa fazer requisições para esta API.
origins = ["[https://consultor-inteligente-frontend.onrender.com](https://consultor-inteligente-frontend.onrender.com)"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Permitir todos os métodos
    allow_headers=["*"], # Permitir todos os cabeçalhos
)

# --- Carregamento do Modelo de IA ---
# Instanciamos o consultor uma única vez, quando a API é iniciada.
# Isso é eficiente, pois evita recarregar tudo a cada nova pergunta do usuário.
try:
    consultor = ConsultorInteligente()
except Exception as e:
    # Se a chave de API do Gemini não estiver configurada, a API não deve iniciar.
    print(f"Erro Crítico ao inicializar o ConsultorInteligente: {e}")
    consultor = None


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
        raise HTTPException(status_code=500, detail="Erro interno do servidor: O modelo de IA não foi carregado corretamente.")

    print(f"Recebida consulta via API: \"{user_query.query}\"")
    
    # Chama o método principal que orquestra todo o processo
    recomendacao = consultor.obter_recomendacao(user_query.query)
    
    return {"response": recomendacao}
