# -*- coding: utf-8 -*-

import os
import json
import time
import logging
from typing import Dict, Any, List
import google.generativeai as genai

# Configuração do logging
logging.basicConfig(level=logging.INFO)

# --- Configuração da API do Gemini ---
try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    raise RuntimeError("A variável de ambiente 'GEMINI_API_KEY' não foi definida.")

class ConsultorInteligente:
    """
    Classe que encapsula a lógica do chatbot consultor, utilizando uma base de dados
    JSON local com filtragem prévia para otimizar velocidade, custo e qualidade.
    """
    def __init__(self):
        """
        Inicializa o modelo de IA e carrega a base de dados de celulares do
        arquivo celulares.json para a memória.
        """
        self.model = genai.GenerativeModel('gemini-2.5-pro')
        self.database_celulares = []
        try:
            # O 'encoding="utf-8"' é importante para garantir a leitura correta de caracteres especiais
            with open('celulares.json', 'r', encoding='utf-8') as f:
                self.database_celulares = json.load(f)
            logging.info(f"Banco de dados carregado com sucesso. {len(self.database_celulares)} celulares na memória.")
        except FileNotFoundError:
            logging.error("ERRO CRÍTICO: O arquivo 'celulares.json' não foi encontrado.")
            raise
        except json.JSONDecodeError:
            logging.error("ERRO CRÍTICO: O arquivo 'celulares.json' contém um erro de formatação JSON.")
            raise

    def _extrair_json_da_resposta(self, text: str) -> Any:
        """Tenta extrair um bloco de código JSON de uma string de texto."""
        try:
            json_start = text.find('```json')
            if json_start == -1:
                # Se não encontrar o marcador, tenta decodificar o texto inteiro
                return json.loads(text)

            json_start += len('```json')
            json_end = text.find('```', json_start)
            if json_end == -1:
                # Se não encontrar o marcador de fim, pega tudo até o final
                json_block = text[json_start:].strip()
            else:
                json_block = text[json_start:json_end].strip()
            
            return json.loads(json_block)
        except (json.JSONDecodeError, AttributeError):
            logging.warning(f"Não foi possível decodificar o JSON da resposta final: {text}")
            return None

    def captar_intencao(self, query_usuario: str) -> Dict[str, Any]:
        """
        ETAPA 1: Usa o Gemini para analisar a consulta do usuário e extrair
        suas necessidades em um formato JSON estruturado.
        """
        prompt = f"""
        Analise a consulta de um usuário para um consultor de celulares: "{query_usuario}"
        Extraia a intenção em um JSON com os seguintes campos:
        - "faixa_preco_categoria": Inferir uma das seguintes categorias de preço: ["Entrada", "Intermediário", "Intermediário Premium", "Premium", "Super Premium"].
        - "caracteristicas_foco": Uma lista de até 3 focos principais do usuário. Use termos-chave como ["câmera", "bateria", "desempenho", "custo-benefício", "design", "tela"].
        Retorne APENAS o objeto JSON.
        """
        response = self.model.generate_content(prompt)
        return self._extrair_json_da_resposta(response.text) or {}

    def filtrar_celulares_localmente(self, intencao: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        ETAPA 2: Filtra a base de dados em memória para encontrar os melhores
        candidatos com base na intenção, sem custo de API.
        """
        faixa_preco_desejada = intencao.get("faixa_preco_categoria")
        caracteristicas_foco = intencao.get("caracteristicas_foco", [])
        
        candidatos = []
        if faixa_preco_desejada:
            candidatos = [cel for cel in self.database_celulares if cel.get("ativo") and cel["compra"]["faixa_preco_categoria"] == faixa_preco_desejada]
        else:
            # Se não especificou preço, considera todos
            candidatos = [cel for cel in self.database_celulares if cel.get("ativo")]

        if not caracteristicas_foco or not candidatos:
            return candidatos[:10] # Retorna até 10 celulares da faixa de preço se não houver foco

        # Atribui uma pontuação para cada candidato com base no foco do usuário
        def calcular_pontuacao(celular):
            pontuacao = 0
            for foco in caracteristicas_foco:
                if foco == "câmera":
                    pontuacao += celular["avaliacoes"]["notas_detalhadas"].get("camera_principal", 0)
                elif foco == "bateria":
                    pontuacao += celular["avaliacoes"]["notas_detalhadas"].get("bateria", 0)
                elif foco == "desempenho":
                    pontuacao += celular["avaliacoes"]["notas_detalhadas"].get("desempenho", 0)
                elif foco == "custo-benefício":
                    pontuacao += celular["avaliacoes"].get("custo_beneficio", 0)
                elif foco == "tela":
                    pontuacao += celular["avaliacoes"]["notas_detalhadas"].get("tela", 0)
                elif foco == "design":
                    pontuacao += celular["avaliacoes"]["notas_detalhadas"].get("design", 0)
            return pontuacao

        # Ordena os candidatos pela pontuação e retorna os 5 melhores
        candidatos.sort(key=calcular_pontuacao, reverse=True)
        return candidatos[:5]

    def classificar_e_recomendar(self, candidatos: List[Dict[str, Any]], intencao: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        ETAPA 3: Envia uma lista curta de candidatos para o Gemini fazer a
        análise final e a recomendação ordenada.
        """
        if not candidatos:
            return []

        prompt = f"""
        Você é um consultor especialista em celulares. Um usuário tem a seguinte intenção de compra: {json.dumps(intencao, ensure_ascii=False)}.
        Eu pré-selecionei os seguintes {len(candidatos)} celulares como os mais relevantes da minha base de dados:

        {json.dumps(candidatos, ensure_ascii=False, indent=2)}

        Sua tarefa é analisar os dados fornecidos para cada um e retornar uma lista JSON ordenada com as 3 melhores recomendações para este usuário, da melhor para a terceira melhor.
        No seu raciocínio, compare os pontos positivos e negativos de cada um em relação à necessidade do usuário.
        Retorne APENAS a lista JSON com os 3 objetos dos celulares escolhidos e ordenados. Não adicione nenhum celular que não esteja na lista que eu forneci.
        """
        response = self.model.generate_content(prompt)
        return self._extrair_json_da_resposta(response.text) or []

    def gerar_recomendacao_completa(self, query_usuario: str) -> str:
        """
        Orquestra o fluxo completo: captar intenção, filtrar localmente,
        classificar com a IA e, finalmente, apresentar em HTML.
        """
        start_time_total = time.perf_counter()

        # Etapa 1
        intencao = self.captar_intencao(query_usuario)
        logging.info(f"Intenção captada: {intencao}")
        logging.info(f"Tempo para 'captar_intencao': {(time.perf_counter() - start_time_total) * 1000:.2f} ms")
        if not intencao:
            return "Desculpe, não consegui entender o que você precisa. Poderia tentar de outra forma?"

        # Etapa 2
        start_filter_time = time.perf_counter()
        candidatos = self.filtrar_celulares_localmente(intencao)
        logging.info(f"Número de candidatos pré-filtrados: {len(candidatos)}")
        logging.info(f"Tempo para 'filtrar_celulares_localmente': {(time.perf_counter() - start_filter_time) * 1000:.2f} ms")

        # Etapa 3
        start_rank_time = time.perf_counter()
        produtos_recomendados = self.classificar_e_recomendar(candidatos, intencao)
        logging.info(f"Tempo para 'classificar_e_recomendar': {(time.perf_counter() - start_rank_time) * 1000:.2f} ms")

        if not produtos_recomendados:
            return "Puxa, após analisar nossa base, não encontrei uma combinação ideal para o seu pedido. Que tal tentarmos outros termos?"

        # Etapa 4
        resultado_html = self.apresentar_resultados(produtos_recomendados)
        logging.info(f"--- Tempo TOTAL de processamento da consulta: {(time.perf_counter() - start_time_total) * 1000:.2f} ms ---")
        return resultado_html

    def gerar_link_afiliado(self, loja: str, produto: str) -> str:
        # ... (sem mudanças aqui) ...
        loja_lower = loja.lower()
        produto_slug = produto.replace(" ", "+").lower()
        if "amazon" in loja_lower:
            return f"[https://www.amazon.com.br/s?k=](https://www.amazon.com.br/s?k=){produto_slug}&tag=seu_tag-20"
        elif "magazine" in loja_lower:
            return f"[https://www.magazinevoce.com.br/magazinesua_loja/busca/](https://www.magazinevoce.com.br/magazinesua_loja/busca/){produto_slug}"
        elif "mercado" in loja_lower:
            return f"[https://mercadolivre.com/sec/1NiRmMA?keywords=](https://mercadolivre.com/sec/1NiRmMA?keywords=){produto_slug}"
        else:
            return f"[https://www.google.com/search?q=](https://www.google.com/search?q=){produto_slug}+{loja_lower}"

    def apresentar_resultados(self, produtos: list[dict]) -> str:
        # ... (sem mudanças aqui, esta função já está pronta para os dados ricos) ...
        if not produtos: return ""

        def gerar_html_detalhes(p: dict) -> str:
            avaliacao_html = ""
            avaliacao = p.get('avaliacoes', {}).get('avaliacao_geral')
            if avaliacao:
                avaliacao_html = f"""<div class="flex items-center gap-1 text-sm text-amber-400 mb-2"><svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"></path></svg><span>{avaliacao}/10</span></div>"""
            perfil_html = f"<p class='text-xs text-gray-300 mb-3 italic'>👤 {p.get('avaliacoes', {}).get('perfil_ideal', '')}</p>" if p.get('avaliacoes', {}).get('perfil_ideal') else ""
            positivos = p.get('avaliacoes', {}).get("positivos_percebidos") or []
            negativos = p.get('avaliacoes', {}).get("negativos_percebidos") or []
            positivos_html = "".join([f"<li class='flex items-start gap-2'><span class='text-green-400'>✅</span><span>{b}</span></li>" for b in positivos])
            negativos_html = "".join([f"<li class='flex items-start gap-2'><span class='text-red-400'>❌</span><span>{b}</span></li>" for b in negativos])
            precos_html = ""
            for loja in p.get("compra", {}).get("links_afiliados") or []:
                link = self.gerar_link_afiliado(loja.get("loja", ""), p.get("identificacao", {}).get("nome_completo", ""))
                precos_html += f"""<a href="{link}" target="_blank" class="block bg-blue-600/20 hover:bg-blue-600/40 rounded-lg px-3 py-2 my-1 transition text-sm">🛒 <strong>{loja.get("loja", "")}</strong>: R$ {p.get("compra", {}).get("preco_medio_lancamento_brl")}</a>"""

            return f"""{avaliacao_html}{perfil_html}<div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs mb-3"><div><h4 class='font-semibold mb-1'>Pontos Positivos</h4><ul class='space-y-1'>{positivos_html}</ul></div><div><h4 class='font-semibold mb-1'>Pontos a Considerar</h4><ul class='space-y-1'>{negativos_html}</ul></div></div><div>{precos_html}</div>"""

        toggle_buttons_html = """<div class="flex items-center justify-center gap-2 mb-3"><button data-view="carousel" class="view-toggle-button active-view-button text-xs px-3 py-1 rounded-full">Carrossel</button><button data-view="accordion" class="view-toggle-button inactive-view-button text-xs px-3 py-1 rounded-full">Lista</button></div>"""
        carousel_html = "<div id='view-carousel' class='card-carousel flex overflow-x-auto snap-x snap-mandatory space-x-4 py-2'>"
        for p in produtos:
            detalhes_produto_html = gerar_html_detalhes(p)
            carousel_html += f"""<div class="flex-shrink-0 w-11/12 snap-center bg-[#2a2a46] text-white p-4 rounded-xl shadow-md border border-gray-700/50"><h3 class="text-lg font-semibold mb-1 text-blue-400">{p.get("identificacao", {}).get("nome_completo", "Modelo desconhecido")}</h3>{detalhes_produto_html}</div>"""
        carousel_html += "</div><p class='text-xs text-gray-400 mt-1 text-center md:hidden'> arraste para o lado para ver mais opções.</p>"
        accordion_html = "<div id='view-accordion' class='hidden space-y-2'>"
        for p in produtos:
            detalhes_produto_html = gerar_html_detalhes(p)
            accordion_html += f"""<div class="bg-[#2a2a46] rounded-lg border border-gray-700/50 overflow-hidden"><button class="accordion-toggle w-full text-left p-3 flex justify-between items-center transition hover:bg-gray-700/30"><span class="font-semibold text-blue-400">{p.get("identificacao", {}).get("nome_completo", "Modelo desconhecido")}</span><svg class="accordion-icon w-5 h-5 text-gray-400 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg></button><div class="accordion-content hidden p-3 pt-0 border-t border-gray-700/50">{detalhes_produto_html}</div></div>"""
        accordion_html += "</div>"
        return f"""<div class="interactive-results">{toggle_buttons_html}{carousel_html}{accordion_html}</div>"""