# -*- coding: utf-8 -*-

import os
import json
import time
import logging
import requests
import google.generativeai as genai
from typing import Dict, Any, List

# Configuração do logging
logging.basicConfig(level=logging.INFO)

# --- Configuração da API do Gemini ---
try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    raise RuntimeError("A variável de ambiente 'GEMINI_API_KEY' não foi definida.")

class ConsultorInteligente:
    """
    Classe que encapsula a lógica do chatbot consultor, utilizando uma arquitetura
    de busca e síntese para otimizar velocidade, custo e qualidade da resposta.
    """
    def __init__(self):
        """Inicializa o modelo de IA e as chaves de API para os serviços do Google."""
        self.model = genai.GenerativeModel('gemini-2.5-pro')
        try:
            self.search_api_key = os.environ["GOOGLE_SEARCH_API_KEY"]
            self.search_cx = os.environ["GOOGLE_SEARCH_CX"]
        except KeyError as e:
            raise RuntimeError(f"Variável de ambiente não encontrada: {e}. Certifique-se de que GOOGLE_SEARCH_API_KEY e GOOGLE_SEARCH_CX estão configuradas.")
        logging.info("ConsultorInteligente inicializado com Gemini Pro e Google Search API.")

    def _extrair_json_da_resposta(self, text: str) -> Any:
        """Tenta extrair um bloco de código JSON de uma string de texto."""
        try:
            # Encontra o início e o fim do bloco JSON
            json_start = text.find('```json')
            if json_start == -1:
                return json.loads(text) # Tenta carregar o texto diretamente se não houver marcador

            json_start += len('```json')
            json_end = text.find('```', json_start)
            json_block = text[json_start:json_end].strip()
            return json.loads(json_block)
        except (json.JSONDecodeError, AttributeError):
            logging.warning(f"Não foi possível decodificar o JSON da resposta: {text}")
            return None

    def captar_intencao(self, query_usuario: str) -> Dict[str, Any]:
        """
        ETAPA 1: Usa o Gemini para analisar a consulta do usuário e extrair
        suas necessidades em um formato JSON estruturado.
        """
        prompt = f"""
        Você é um sistema especialista em análise de intenção de busca para um comparador de celulares.
        Analise a seguinte consulta de um usuário: "{query_usuario}"
        Extraia as seguintes informações em um formato JSON:
        1.  "uso_principal": Qual o principal objetivo do usuário com o celular? (Ex: 'fotos', 'jogos', 'trabalho', 'uso_geral', 'bateria').
        2.  "caracteristicas_chave": Uma lista de até 3 características específicas mencionadas. (Ex: ['câmera boa', 'bateria duradoura', 'tela grande', 'barato']).
        3.  "faixa_preco": Qual a faixa de preço implícita? (Ex: 'básico', 'intermediário', 'top de linha', 'custo-benefício').
        Retorne APENAS o objeto JSON.
        """
        response = self.model.generate_content(prompt)
        return self._extrair_json_da_resposta(response.text) or {}

    def realizar_busca_ampla(self, intencao: Dict[str, Any]) -> str:
        """
        ETAPA 2 (Busca): Realiza múltiplas buscas na Google Search API para
        coletar um contexto rico de informações com base na intenção do usuário.
        """
        termos_chave = ' '.join(intencao.get('caracteristicas_chave', []))
        uso_principal = intencao.get('uso_principal', '')
        
        queries = [
            f"melhores celulares {uso_principal} {termos_chave} Brasil",
            f"celulares {termos_chave} prós e contras",
            f"reclamações comuns celular {uso_principal} {termos_chave}"
        ]
        
        contexto_total = ""
        for query in queries:
            logging.info(f"Realizando busca no Google com a query: '{query}'")
            url = "https://www.googleapis.com/customsearch/v1"
            params = {'key': self.search_api_key, 'cx': self.search_cx, 'q': query, 'num': 3}
            
            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                search_results = response.json()
                for item in search_results.get('items', []):
                    contexto_total += f"Título: {item.get('title')}\nSnippet: {item.get('snippet')}\n---\n"
            except requests.exceptions.RequestException as e:
                logging.error(f"Erro ao chamar a Google Search API para query '{query}': {e}")
        
        return contexto_total

    def sintetizar_relatorio_completo(self, contexto_busca: str, intencao: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        ETAPA 2 (Síntese): Usa o Gemini com um "super prompt" para analisar o contexto
        da busca e gerar um relatório JSON detalhado sobre os celulares recomendados.
        """
        if not contexto_busca:
            logging.warning("Contexto da busca está vazio. Pulando a síntese.")
            return []

        prompt = f"""
        Você é um especialista em análise de celulares. Sua tarefa é analisar os seguintes resultados de busca e a intenção de um usuário para criar um relatório detalhado sobre os 3 melhores celulares.

        **Intenção do usuário:** {json.dumps(intencao, ensure_ascii=False)}

        **Resultados brutos da busca (títulos e snippets de sites confiáveis):**
        ---
        {contexto_busca}
        ---

        Com base exclusivamente nas informações acima e na intenção do usuário, retorne uma lista de 3 objetos JSON. Para cada objeto, preencha os seguintes campos:
        - "marca_modelo": O nome completo da marca e do modelo.
        - "avaliacao_media": Uma nota numérica estimada de 0 a 5.0 (pode ser um número quebrado, como 4.7).
        - "pontos_positivos": Uma lista de 2 a 3 strings curtas com os principais pontos positivos mencionados.
        - "pontos_negativos": Uma lista de 2 a 3 strings curtas com os principais pontos negativos ou reclamações mencionadas.
        - "perfil_ideal": Uma frase curta descrevendo para qual tipo de usuário este celular é mais indicado.
        - "precos_referencia": Uma lista de 1 a 2 objetos com "loja" e "preco" inferidos dos resultados.

        Se uma informação (como a avaliação média) não puder ser extraída do texto fornecido, retorne null para aquele campo.
        Seja conciso e direto ao ponto nos textos. Retorne APENAS a lista de objetos JSON.
        """
        response = self.model.generate_content(prompt)
        return self._extrair_json_da_resposta(response.text) or []

    def gerar_recomendacao_sem_cache(self, intencao: Dict[str, Any]) -> str:
        """
        Orquestra o fluxo de geração de recomendação (busca, síntese e apresentação)
        para uma intenção que não foi encontrada no cache.
        """
        start_time_total = time.perf_counter()
        
        contexto_busca = self.realizar_busca_ampla(intencao)
        logging.info(f"Tempo para 'realizar_busca_ampla': {(time.perf_counter() - start_time_total) * 1000:.2f} ms")
        
        produtos = self.sintetizar_relatorio_completo(contexto_busca, intencao)
        logging.info(f"Tempo para 'sintetizar_relatorio_completo': {(time.perf_counter() - start_time_total) * 1000:.2f} ms")

        if not produtos:
            return "Puxa, fiz uma busca detalhada mas não encontrei nenhum celular que se encaixe perfeitamente no seu pedido. Que tal tentarmos outros termos?"

        resultado_html = self.apresentar_resultados(produtos)
        
        logging.info(f"--- Tempo TOTAL de processamento (sem cache): {(time.perf_counter() - start_time_total) * 1000:.2f} ms ---")
        return resultado_html

    def gerar_link_afiliado(self, loja: str, produto: str) -> str:
        """Gera um link de afiliado com base na loja e no nome do produto."""
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
        """
        ETAPA 3: Gera uma resposta HTML rica com múltiplas visualizações
        (Carrossel e Lista/Acordeão), incluindo os novos dados detalhados.
        """
        if not produtos: return ""

        # --- Sub-funções para gerar HTML e evitar repetição ---
        def gerar_html_detalhes(p: dict) -> str:
            """Gera o bloco de HTML com os detalhes ricos de um produto."""
            # Avaliação Média
            avaliacao_html = ""
            avaliacao = p.get('avaliacao_media')
            if avaliacao:
                avaliacao_html = f"""
                <div class="flex items-center gap-1 text-sm text-amber-400 mb-2">
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"></path></svg>
                    <span>{avaliacao}/5.0</span>
                </div>
                """
            # Perfil Ideal
            perfil_html = f"<p class='text-xs text-gray-300 mb-3 italic'>👤 {p.get('perfil_ideal', '')}</p>" if p.get('perfil_ideal') else ""
            
            # Pontos Positivos e Negativos
            # Correção
            positivos_html = "".join([f"<li...>{b}</span></li>" for b in p.get("pontos_positivos") or []])
            negativos_html = "".join([f"<li...>{b}</span></li>" for b in p.get("pontos_negativos") or []])
            
            # Preços
            precos_html = ""
            for loja in p.get("precos_referencia", []):
                link = self.gerar_link_afiliado(loja.get("loja", ""), p.get("marca_modelo", ""))
                precos_html += f"""<a href="{link}" target="_blank" class="block bg-blue-600/20 hover:bg-blue-600/40 rounded-lg px-3 py-2 my-1 transition text-sm">🛒 <strong>{loja.get("loja", "")}</strong>: {loja.get("preco", "")}</a>"""

            return f"""
                {avaliacao_html}
                {perfil_html}
                <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs mb-3">
                    <div><h4 class='font-semibold mb-1'>Pontos Positivos</h4><ul class='space-y-1'>{positivos_html}</ul></div>
                    <div><h4 class='font-semibold mb-1'>Pontos a Considerar</h4><ul class='space-y-1'>{negativos_html}</ul></div>
                </div>
                <div>{precos_html}</div>
            """

        # --- Construção do HTML Final ---
        toggle_buttons_html = """
        <div class="flex items-center justify-center gap-2 mb-3">
            <button data-view="carousel" class="view-toggle-button active-view-button text-xs px-3 py-1 rounded-full">Carrossel</button>
            <button data-view="accordion" class="view-toggle-button inactive-view-button text-xs px-3 py-1 rounded-full">Lista</button>
        </div>
        """
        
        carousel_html = "<div id='view-carousel' class='card-carousel flex overflow-x-auto snap-x snap-mandatory space-x-4 py-2'>"
        for p in produtos:
            detalhes_produto_html = gerar_html_detalhes(p)
            carousel_html += f"""
            <div class="flex-shrink-0 w-11/12 snap-center bg-[#2a2a46] text-white p-4 rounded-xl shadow-md border border-gray-700/50">
                <h3 class="text-lg font-semibold mb-1 text-blue-400">{p.get("marca_modelo", "Modelo desconhecido")}</h3>
                {detalhes_produto_html}
            </div>"""
        carousel_html += "</div><p class='text-xs text-gray-400 mt-1 text-center md:hidden'> arraste para o lado para ver mais opções.</p>"

        accordion_html = "<div id='view-accordion' class='hidden space-y-2'>"
        for p in produtos:
            detalhes_produto_html = gerar_html_detalhes(p)
            accordion_html += f"""
            <div class="bg-[#2a2a46] rounded-lg border border-gray-700/50 overflow-hidden">
                <button class="accordion-toggle w-full text-left p-3 flex justify-between items-center transition hover:bg-gray-700/30">
                    <span class="font-semibold text-blue-400">{p.get("marca_modelo", "Modelo desconhecido")}</span>
                    <svg class="accordion-icon w-5 h-5 text-gray-400 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                </button>
                <div class="accordion-content hidden p-3 pt-0 border-t border-gray-700/50">
                    {detalhes_produto_html}
                </div>
            </div>"""
        accordion_html += "</div>"
        
        return f"""
        <div class="interactive-results">
            {toggle_buttons_html}
            {carousel_html}
            {accordion_html}
        </div>
        """