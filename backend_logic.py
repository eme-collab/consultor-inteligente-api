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
        self.model = genai.GenerativeModel(
            'models/gemini-2.5-pro'
        )
        print("Modelo ConsultorInteligente inicializado com sucesso.")

    def _extrair_json_da_resposta(self, text: str) -> Any:
        try:
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
        response = self.model.generate_content(prompt)
        print("Produtos encontrados (JSON):", response.text)
        return self._extrair_json_da_resposta(response.text) or []

    def gerar_link_afiliado(self, loja: str, produto: str) -> str:
        """
        Gera link de afiliado com base na loja e no nome do produto.
        """
        loja = loja.lower()
        produto_slug = produto.replace(" ", "+").lower()

        if "amazon" in loja:
            return f"https://www.amazon.com.br/q={produto_slug}&tag=bomdemarca007-20"
        elif "magazine" in loja:
            return f"https://www.magazinevoce.com.br/magazinerefrigerador/busca/{produto_slug}"
        elif "mercado" in loja:
            return f"https://mercadolivre.com/sec/1NiRmMA?keywords={produto_slug}"
        elif "casas" in loja:
            return f"https://www.casasbahia.com.br/{produto_slug}"
        else:
            return "#"

    def apresentar_resultados(self, produtos: list[dict], query_original: str) -> str:
        """
        Gera uma resposta em HTML com cards comparativos em um carrossel horizontal.
        """
        print("\n--- 3. Formatando a Apresentação Final (HTML) ---")

        # Container do carrossel: flex, rolagem horizontal, com "snap"
        # A classe 'card-carousel' será usada no CSS do index.html para customização
        html = "<div class='card-carousel flex overflow-x-auto snap-x snap-mandatory space-x-4 py-2'>"

        for p in produtos:
            marca_modelo = p.get("marca_modelo", "Modelo desconhecido")
            beneficios = "".join([f"<li>✅ {b}</li>" for b in p.get("beneficios", [])])

            precos = ""
            for loja in p.get("precos_referencia", []):
                nome_loja = loja.get("loja", "")
                preco = loja.get("preco", "")
                link_afiliado = self.gerar_link_afiliado(nome_loja, marca_modelo)
                precos += f"""
                    <a href="{link_afiliado}" target="_blank" class="block bg-blue-600/20 hover:bg-blue-600/40 rounded-lg px-3 py-2 my-1 transition">
                        🛒 <strong>{nome_loja}</strong>: {preco}
                    </a>
                """
            
            # Card individual: não encolhe, ocupa 91% da largura (w-11/12), e centraliza no snap
            html += f"""
            <div class="flex-shrink-0 w-11/12 snap-center bg-[#2a2a46] text-white p-4 rounded-xl shadow-md border border-gray-700/50">
                <h3 class="text-lg font-semibold mb-2 text-blue-400">{marca_modelo}</h3>
                <ul class="text-sm space-y-1 mb-3">{beneficios}</ul>
                <div>{precos}</div>
            </div>
            """

        html += "</div>"
        html += "<p class='text-xs text-gray-400 mt-3 text-center'> arraste para o lado para ver mais opções.</p>"
        return html


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
            print(f"ERRO DETALHADO NA LÓGICA DO BACKEND: {e}")
            return f"Erro no servidor: {str(e)}"
