# -*- coding: utf-8 -*-

import os
import json
import time
import logging
import requests  # <-- NOVO IMPORT
import google.generativeai as genai
from typing import Dict, Any, List

# --- Configuração da API ---
try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    raise RuntimeError("A variável de ambiente 'GEMINI_API_KEY' não foi definida.")

class ConsultorInteligente:
    def __init__(self):
        # Carrega o modelo Gemini Pro
        self.model = genai.GenerativeModel('gemini-2.5-pro')
        
        # Carrega as novas credenciais da Search API a partir das variáveis de ambiente
        try:
            self.search_api_key = os.environ["GOOGLE_SEARCH_API_KEY"]
            self.search_cx = os.environ["GOOGLE_SEARCH_CX"]
        except KeyError as e:
            raise RuntimeError(f"Variável de ambiente não encontrada: {e}. Certifique-se de que GOOGLE_SEARCH_API_KEY e GOOGLE_SEARCH_CX estão configuradas no Render.")
        
        logging.info("ConsultorInteligente inicializado com Gemini Pro e Google Search API.")

    def _extrair_json_da_resposta(self, text: str) -> Any:
        try:
            json_block = text.strip().replace("```json", "").replace("```", "")
            return json.loads(json_block)
        except json.JSONDecodeError:
            logging.warning(f"Não foi possível decodificar o JSON da resposta: {text}")
            return None

    # ====================================================================
    # ETAPA 1: Captar a intenção do usuário (NENHUMA MUDANÇA AQUI)
    # ====================================================================
    def captar_intencao(self, query_usuario: str) -> Dict[str, Any]:
        prompt = f"""
        Você é um sistema especialista em análise de intenção de busca para um comparador de celulares.
        Analise a seguinte consulta: "{query_usuario}"
        Extraia as informações em um formato JSON com os campos "uso_principal", "caracteristicas_chave" (lista) e "faixa_preco".
        Retorne APENAS o objeto JSON.
        """
        response = self.model.generate_content(prompt)
        return self._extrair_json_da_resposta(response.text) or {}

    # ====================================================================
    # ETAPA 2 (NOVA): Buscar dados brutos usando a Google Search API
    # ====================================================================
    def realizar_busca_google(self, intencao: Dict[str, Any]) -> str:
        # Constrói uma query de busca a partir da intenção
        termos_busca = intencao.get('caracteristicas_chave', [])
        uso_principal = intencao.get('uso_principal', '')
        query = f"{uso_principal} {' '.join(termos_busca)} celular review"
        
        logging.info(f"Realizando busca no Google com a query: '{query}'")
        
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': self.search_api_key,
            'cx': self.search_cx,
            'q': query,
            'num': 5  # Pedimos 5 resultados para ter mais contexto
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Lança um erro para respostas ruins (4xx ou 5xx)
            search_results = response.json()
            
            # Formata os resultados como um texto simples para o Gemini
            contexto = ""
            for item in search_results.get('items', []):
                contexto += f"Título: {item.get('title')}\n"
                contexto += f"Snippet: {item.get('snippet')}\n---\n"
            return contexto
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro ao chamar a Google Search API: {e}")
            return "" # Retorna string vazia em caso de erro

    # ====================================================================
    # ETAPA 3 (NOVA): Sintetizar os resultados da busca com o Gemini
    # ====================================================================
    def sintetizar_resultados(self, contexto_busca: str, intencao: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not contexto_busca:
            logging.warning("Contexto da busca está vazio. Pulando a síntese.")
            return []

        prompt = f"""
        Você é um especialista em tecnologia. Sua tarefa é analisar os seguintes resultados de busca e a intenção de um usuário para recomendar 3 celulares.

        Intenção do usuário: {json.dumps(intencao, ensure_ascii=False)}

        Resultados da busca:
        ---
        {contexto_busca}
        ---

        Com base nos resultados da busca e na intenção, selecione os 3 melhores modelos.
        Para cada modelo, forneça as informações em uma lista de objetos JSON com os campos:
        - "marca_modelo": A marca e o nome do modelo.
        - "beneficios": Uma lista de 3 a 4 strings curtas com os principais benefícios.
        - "precos_referencia": Uma lista de 2 objetos com "loja" e "preco".
        Retorne APENAS a lista de objetos JSON.
        """
        response = self.model.generate_content(prompt)
        return self._extrair_json_da_resposta(response.text) or []

    # ====================================================================
    # ORQUESTRADOR PRINCIPAL (MODIFICADO)
    # ====================================================================
    def obter_recomendacao(self, query_usuario: str) -> str:
        start_time_total = time.perf_counter()
        
        # Etapa 1: Captar Intenção
        start_time_intencao = time.perf_counter()
        intencao = self.captar_intencao(query_usuario)
        end_time_intencao = time.perf_counter()
        logging.info(f"Tempo para 'captar_intencao': {(end_time_intencao - start_time_intencao) * 1000:.2f} ms")

        if not intencao:
            return "Desculpe, não consegui entender o que você precisa."

        # Etapa 2: Realizar Busca
        start_time_busca = time.perf_counter()
        contexto_busca = self.realizar_busca_google(intencao)
        end_time_busca = time.perf_counter()
        logging.info(f"Tempo para 'realizar_busca_google': {(end_time_busca - start_time_busca) * 1000:.2f} ms")
        
        # Etapa 3: Sintetizar Resultados
        start_time_sintese = time.perf_counter()
        produtos = self.sintetizar_resultados(contexto_busca, intencao)
        end_time_sintese = time.perf_counter()
        logging.info(f"Tempo para 'sintetizar_resultados': {(end_time_sintese - start_time_sintese) * 1000:.2f} ms")

        if not produtos:
            return "Puxa, fiz uma busca mas não encontrei celulares com essas especificações."

        # Etapa 4: Apresentar Resultados (HTML)
        resultado_html = self.apresentar_resultados(produtos, query_usuario)
        
        end_time_total = time.perf_counter()
        logging.info(f"--- Tempo TOTAL de processamento no backend: {(end_time_total - start_time_total) * 1000:.2f} ms ---")

        return resultado_html

    def gerar_link_afiliado(self, loja: str, produto: str) -> str:
        """
        Gera link de afiliado com base na loja e no nome do produto.
        """
        loja = loja.lower()
        produto_slug = produto.replace(" ", "+").lower()

        if "amazon" in loja:
            return f"https://www.amazon.com.br/s?k={produto_slug}&tag=bomdemarca007-20"
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
        Gera uma resposta HTML com múltiplas visualizações (Carrossel e Acordeão).
        """
        print("\n--- 3. Formatando a Apresentação Final (HTML) ---")

        # 1. Botões de alternância de visualização
        toggle_buttons_html = """
        <div class="flex items-center justify-center gap-2 mb-3">
            <button data-view="carousel" class="view-toggle-button active-view-button text-xs px-3 py-1 rounded-full">Carrossel</button>
            <button data-view="accordion" class="view-toggle-button inactive-view-button text-xs px-3 py-1 rounded-full">Lista</button>
        </div>
        """

        # 2. Visualização em Carrossel
        carousel_html = "<div id='view-carousel' class='card-carousel flex overflow-x-auto snap-x snap-mandatory space-x-4 py-2'>"
        for p in produtos:
            marca_modelo = p.get("marca_modelo", "Modelo desconhecido")
            beneficios = "".join([f"<li>✅ {b}</li>" for b in p.get("beneficios", [])])
            precos = ""
            for loja in p.get("precos_referencia", []):
                nome_loja = loja.get("loja", "")
                preco = loja.get("preco", "")
                link_afiliado = self.gerar_link_afiliado(nome_loja, marca_modelo)
                precos += f"""<a href="{link_afiliado}" target="_blank" class="block bg-blue-600/20 hover:bg-blue-600/40 rounded-lg px-3 py-2 my-1 transition">🛒 <strong>{nome_loja}</strong>: {preco}</a>"""
            carousel_html += f"""
            <div class="flex-shrink-0 w-11/12 snap-center bg-[#2a2a46] text-white p-4 rounded-xl shadow-md border border-gray-700/50">
                <h3 class="text-lg font-semibold mb-2 text-blue-400">{marca_modelo}</h3>
                <ul class="text-sm space-y-1 mb-3">{beneficios}</ul>
                <div>{precos}</div>
            </div>"""
        carousel_html += "</div>"
        carousel_html += "<p class='text-xs text-gray-400 mt-1 text-center md:hidden'> arraste para o lado para ver mais opções.</p>"

        # 3. Visualização em Acordeão (Lista)
        accordion_html = "<div id='view-accordion' class='hidden space-y-2'>"
        for p in produtos:
            marca_modelo = p.get("marca_modelo", "Modelo desconhecido")
            beneficios = "".join([f"<li>✅ {b}</li>" for b in p.get("beneficios", [])])
            precos = ""
            for loja in p.get("precos_referencia", []):
                nome_loja = loja.get("loja", "")
                preco = loja.get("preco", "")
                link_afiliado = self.gerar_link_afiliado(nome_loja, marca_modelo)
                precos += f"""<a href="{link_afiliado}" target="_blank" class="block bg-blue-600/20 hover:bg-blue-600/40 rounded-lg px-3 py-2 my-1 transition">🛒 <strong>{nome_loja}</strong>: {preco}</a>"""
            accordion_html += f"""
            <div class="bg-[#2a2a46] rounded-lg border border-gray-700/50 overflow-hidden">
                <button class="accordion-toggle w-full text-left p-3 flex justify-between items-center transition hover:bg-gray-700/30">
                    <span class="font-semibold text-blue-400">{marca_modelo}</span>
                    <svg class="accordion-icon w-5 h-5 text-gray-400 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                </button>
                <div class="accordion-content hidden p-3 pt-0 border-t border-gray-700/50">
                    <ul class="text-sm space-y-1 my-3">{beneficios}</ul>
                    <div>{precos}</div>
                </div>
            </div>"""
        accordion_html += "</div>"

        # 4. Combina tudo em um container principal
        final_html = f"""
        <div class="interactive-results">
            {toggle_buttons_html}
            {carousel_html}
            {accordion_html}
        </div>
        """
        return final_html
