# -*- coding: utf-8 -*-

import os
import json
import time
import logging
import random # <-- NOVO: Import para o sorteio das lojas
from typing import Dict, Any, List
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)

try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    raise RuntimeError("A variável de ambiente 'GEMINI_API_KEY' não foi definida.")

class ConsultorInteligente:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.5-pro')
        self.database_celulares = []
        self.lojas_ancora = [] # <-- NOVO
        self.lojas_rotativas = [] # <-- NOVO
        try:
            with open('celulares.json', 'r', encoding='utf-8') as f:
                self.database_celulares = json.load(f)
            logging.info(f"Banco de dados de celulares carregado com {len(self.database_celulares)} itens.")
            
            # <-- NOVO: Carrega o arquivo de lojas na inicialização -->
            with open('lojas.json', 'r', encoding='utf-8') as f:
                lojas_data = json.load(f)
                self.lojas_ancora = lojas_data.get("ancoras", [])
                self.lojas_rotativas = lojas_data.get("rotativas", [])
            logging.info(f"Banco de dados de lojas carregado. {len(self.lojas_ancora)} âncoras, {len(self.lojas_rotativas)} rotativas.")

        except FileNotFoundError as e:
            logging.error(f"ERRO CRÍTICO: O arquivo '{e.filename}' não foi encontrado.")
            raise
        except json.JSONDecodeError as e:
            logging.error(f"ERRO CRÍTICO: Um arquivo JSON contém um erro de formatação: {e}")
            raise

    # <-- ALTERADO: A classe principal continua daqui, com as funções de lógica -->
    # ... (as funções _extrair_json_da_resposta, captar_intencao, filtrar_celulares_localmente,
    # e classificar_e_recomendar continuam EXATAMENTE IGUAIS ao que você já tem) ...
    def _extrair_json_da_resposta(self, text: str) -> Any:
        try:
            json_start = text.find('```json')
            if json_start == -1: return json.loads(text)
            json_start += len('```json')
            json_end = text.find('```', json_start)
            json_block = text[json_start:json_end if json_end != -1 else len(text)].strip()
            return json.loads(json_block)
        except (json.JSONDecodeError, AttributeError):
            logging.warning(f"Não foi possível decodificar o JSON: {text}")
            return None

    def captar_intencao(self, query_usuario: str) -> Dict[str, Any]:
        prompt = f"""Analise a consulta: "{query_usuario}". Extraia a intenção em um JSON com "faixa_preco_categoria" (["Entrada", "Intermediário", "Intermediário Premium", "Premium", "Super Premium"]) e "caracteristicas_foco" (lista com ["câmera", "bateria", "desempenho", "custo-benefício", "design", "tela"]). Retorne APENAS o JSON."""
        response = self.model.generate_content(prompt)
        return self._extrair_json_da_resposta(response.text) or {}

    def filtrar_celulares_localmente(self, intencao: Dict[str, Any]) -> List[Dict[str, Any]]:
        faixa_preco_desejada = intencao.get("faixa_preco_categoria")
        caracteristicas_foco = intencao.get("caracteristicas_foco", [])
        candidatos = [c for c in self.database_celulares if c.get("ativo")]
        if faixa_preco_desejada:
            candidatos = [c for c in candidatos if c["compra"]["faixa_preco_categoria"] == faixa_preco_desejada]
        if not caracteristicas_foco or not candidatos: return candidatos[:10]
        def calcular_pontuacao(celular):
            pontuacao = 0
            for foco in caracteristicas_foco:
                if foco == "câmera": pontuacao += celular["avaliacoes"]["notas_detalhadas"].get("camera_principal", 0)
                elif foco == "bateria": pontuacao += celular["avaliacoes"]["notas_detalhadas"].get("bateria", 0)
                elif foco == "desempenho": pontuacao += celular["avaliacoes"]["notas_detalhadas"].get("desempenho", 0)
                elif foco == "custo-benefício": pontuacao += celular["avaliacoes"].get("custo_beneficio", 0)
                elif foco == "tela": pontuacao += celular["avaliacoes"]["notas_detalhadas"].get("tela", 0)
                elif foco == "design": pontuacao += celular["avaliacoes"]["notas_detalhadas"].get("design", 0)
            return pontuacao
        candidatos.sort(key=calcular_pontuacao, reverse=True)
        top_candidatos = candidatos[:7]
        if len(top_candidatos) > 5: return random.sample(top_candidatos, 5)
        return top_candidatos

    def classificar_e_recomendar(self, candidatos: List[Dict[str, Any]], intencao: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not candidatos: return []
        prompt = f"""Você é um consultor especialista. A intenção do usuário é: {json.dumps(intencao, ensure_ascii=False)}. Eu pré-selecionei estes {len(candidatos)} celulares: {json.dumps(candidatos, ensure_ascii=False, indent=2)}. Analise os dados e retorne uma lista JSON ordenada com as 3 melhores recomendações. Retorne APENAS a lista JSON com os 3 objetos escolhidos e ordenados."""
        generation_config = {"temperature": 0.7}
        response = self.model.generate_content(prompt, generation_config=generation_config)
        return self._extrair_json_da_resposta(response.text) or []

    def gerar_recomendacao_completa(self, query_usuario: str) -> str:
        start_time_total = time.perf_counter()
        intencao = self.captar_intencao(query_usuario)
        logging.info(f"Intenção captada: {intencao}")
        if not intencao: return "Desculpe, não consegui entender o que você precisa."
        candidatos = self.filtrar_celulares_localmente(intencao)
        logging.info(f"Candidatos pré-filtrados: {len(candidatos)}")
        produtos_recomendados = self.classificar_e_recomendar(candidatos, intencao)
        if not produtos_recomendados: return "Puxa, não encontrei uma combinação ideal para o seu pedido."
        resultado_html = self.apresentar_resultados(produtos_recomendados)
        logging.info(f"--- Tempo TOTAL: {(time.perf_counter() - start_time_total) * 1000:.2f} ms ---")
        return resultado_html

    # <-- NOVO: Função para selecionar as lojas com a Estratégia 3 -->
    def selecionar_lojas(self) -> List[Dict[str, str]]:
        """Seleciona 1 loja âncora e 2 rotativas, e embaralha a ordem final."""
        lojas_selecionadas = []
        
        # Seleciona 1 âncora aleatoriamente, se houver
        if self.lojas_ancora:
            lojas_selecionadas.append(random.choice(self.lojas_ancora))
            
        # Seleciona 2 rotativas aleatoriamente, se houver
        if len(self.lojas_rotativas) >= 2:
            lojas_selecionadas.extend(random.sample(self.lojas_rotativas, 2))
        else: # Fallback se tiver menos de 2 lojas rotativas
            lojas_selecionadas.extend(self.lojas_rotativas)

        # Embaralha a lista final para que a âncora não seja sempre a primeira
        random.shuffle(lojas_selecionadas)
        
        return lojas_selecionadas[:3] # Garante que retornará no máximo 3 lojas

    # <-- REMOVIDO: A função gerar_link_afiliado não é mais necessária -->

    # <-- ALTERADO: A função apresentar_resultados agora usa a nova lógica de lojas -->
    def apresentar_resultados(self, produtos: list[dict]) -> str:
        if not produtos: return ""

        # A sub-função interna para gerar os detalhes de cada produto permanece a mesma
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
            # A geração de links de preço foi removida daqui
            return f"""{avaliacao_html}{perfil_html}<div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs mb-3"><div><h4 class='font-semibold mb-1'>Pontos Positivos</h4><ul class='space-y-1'>{positivos_html}</ul></div><div><h4 class='font-semibold mb-1'>Pontos a Considerar</h4><ul class='space-y-1'>{negativos_html}</ul></div></div>"""

        # Construção do HTML dos produtos (carrossel e acordeão)
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
        
        # --- NOVO: Geração do bloco de lojas dinâmicas ---
        lojas_selecionadas = self.selecionar_lojas()
        lojas_html = "<div class='mt-4 text-center'><h4 class='text-sm font-semibold text-white mb-2'>Confira os preços e promoções nas lojas a seguir:</h4><div class='flex flex-wrap justify-center gap-2'>"
        for loja in lojas_selecionadas:
            lojas_html += f"""<a href="{loja['url']}" target="_blank" class="block bg-gray-700 hover:bg-gray-600 rounded-lg px-4 py-2 transition text-sm text-white font-semibold">🛒 {loja['nome']}</a>"""
        lojas_html += "</div></div>"
        
        # Concatena tudo na resposta final
        return f"""<div class="interactive-results">{toggle_buttons_html}{carousel_html}{accordion_html}{lojas_html}</div>"""