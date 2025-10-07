# -*- coding: utf-8 -*-

import os
import json
import google.generativeai as genai
from typing import Dict, Any, List
from google.generativeai.types import Tool, FunctionDeclaration, HarmCategory, HarmBlockThreshold

# --- Configuração da API ---
try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    raise RuntimeError("A variável de ambiente 'GEMINI_API_KEY' não foi definida ou não está acessível no servidor do Render.")

class ConsultorInteligente:
    def __init__(self):
        # --- CORREÇÃO FINAL E DEFINITIVA ---
        # O log de erro e a documentação confirmam que a API v1beta espera o caminho completo do modelo.
        # Estamos agora usando o caminho explícito "models/..." para garantir a compatibilidade.
        self.model = genai.GenerativeModel(
            'models/gemini-pro' 
        )
        print("Modelo ConsultorInteligente inicializado com sucesso.")

    def _extrair_json_da_resposta(self, text: str) -> Any:
        try:
            # Limpa qualquer formatação de markdown que a IA possa retornar
            json_block = text.strip().replace("```json", "").replace("```", "")
            return json.loads(json_block)
        except json.JSONDecodeError:
            print(f"Alerta: Não foi possível decodificar o JSON da resposta: {text}")
            return None

    def captar_intencao(self, query_usuario: str) -> Dict[str, Any]:
        prompt = f"""
        Você é um sistema especialista em análise de intenção de busca para um comparador de celulares.
        Analise a seguinte consulta de um usuário: "{query_usuario}"
        Extraia as seguintes informações em um formato JSON:
        1.  "uso_principal": Qual o principal objetivo do usuário com o celular? (Ex: 'fotos', 'jogos', 'trabalho', 'uso_geral', 'bateria').
        2.  "caracteristicas_chave": Uma lista de características específicas mencionadas. (Ex: ['câmera boa', 'bateria duradoura', 'tela grande', 'barato']).
        3.  "faixa_preco": Qual a faixa de preço implícita? (Ex: 'básico', 'intermediário', 'top de linha', 'custo-benefício').
        Retorne APENAS o objeto JSON.
        """
        print("--- 1. Captando Intenção do Usuário ---")
        response = self.model.generate_content(prompt)
        print("Intenção extraída (JSON):", response.text)
        return self._extrair_json_da_resposta(response.text) or {}

    def buscar_produtos(self, intencao: Dict[str, Any]) -> List[Dict[str, Any]]:
        prompt = f"""
        Você é um especialista em tecnologia que ajuda usuários a encontrar o celular ideal.
        Com base nos seguintes critérios de busca: {json.dumps(intencao, ensure_ascii=False)}
        Use a busca em tempo real para encontrar os 3 melhores modelos de celular disponíveis no mercado brasileiro que atendam a esses critérios.
        Para cada modelo, forneça as seguintes informações em um formato de lista de objetos JSON:
        - "marca_modelo": A marca e o nome do modelo (Ex: "Samsung Galaxy S24").
        - "beneficios": Uma lista de 3 a 4 strings curtas que traduzem especificações técnicas em benefícios claros para o usuário.
        - "precos_referencia": Uma lista de 2 a 3 objetos com a "loja" e o "preco".
        Retorne APENAS a lista de objetos JSON.
        """
        print("\n--- 2. Buscando Produtos com Base na Intenção ---")
        
        # Ativamos a ferramenta de busca do Google com a sintaxe correta
        from google.generativeai.types import Tool, FunctionDeclaration, HarmCategory, HarmBlockThreshold
        tools = [Tool(google_search_retrieval={})]
        response = self.model.generate_content(prompt, tools=tools)

        print("Produtos encontrados (JSON):", response.text)
        return self._extrair_json_da_resposta(response.text) or []

    def apresentar_resultados(self, produtos: List[Dict[str, Any]], query_original: str) -> str:
        prompt = f"""
        Você é o "Consultor Inteligente". Sua personalidade é amigável e prestativa.
        A consulta original do usuário foi: "{query_original}".
        Você encontrou os seguintes celulares: {json.dumps(produtos, ensure_ascii=False)}
        Apresente esses resultados em uma resposta conversacional.
        """
        print("\n--- 3. Formatando a Apresentação Final ---")
        response = self.model.generate_content(prompt)
        return response.text

    def obter_recomendacao(self, query_usuario: str) -> str:
        try:
            intencao = self.captar_intencao(query_usuario)
            if not intencao:
                return "Desculpe, não consegui entender o que você precisa. Poderia tentar de outra forma?"
            
            produtos = self.buscar_produtos(intencao)
            if not produtos:
                return "Puxa, fiz uma busca aqui mas não encontrei nenhum celular que se encaixe perfeitamente no seu pedido. Que tal tentarmos outros termos?"
            
            return self.apresentar_resultados(produtos, query_usuario)
        except Exception as e:
            # Captura qualquer erro que possa acontecer durante a chamada para a API do Google
            print(f"ERRO DETALHADO NA LÓGICA DO BACKEND: {e}")
            # Retorna a mensagem de erro específica para depuração no front-end
            return f"Erro no servidor: {str(e)}"

