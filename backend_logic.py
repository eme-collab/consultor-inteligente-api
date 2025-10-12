# -*- coding: utf-8 -*-

import os
import json
import time
import logging
import random
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
        self.lojas_ancora = []
        self.lojas_rotativas = []
        try:
            with open('celulares.json', 'r', encoding='utf-8') as f:
                self.database_celulares = json.load(f)
            logging.info(f"Banco de dados de celulares carregado com {len(self.database_celulares)} itens.")
            with open('lojas.json', 'r', encoding='utf-8') as f:
                lojas_data = json.load(f)
                self.lojas_ancora = lojas_data.get("ancoras", [])
                self.lojas_rotativas = lojas_data.get("rotativas", [])
            logging.info(f"Banco de dados de lojas carregado.")
        except FileNotFoundError as e:
            logging.error(f"ERRO CRÍTICO: O arquivo '{e.filename}' não foi encontrado.")
            raise
        except json.JSONDecodeError as e:
            logging.error(f"ERRO CRÍTICO: Um arquivo JSON contém um erro de formatação: {e}")
            raise

    # As funções de lógica principal (captar, filtrar, classificar) permanecem as mesmas
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

    def selecionar_lojas(self) -> List[Dict[str, str]]:
        lojas_selecionadas = []
        if self.lojas_ancora: lojas_selecionadas.append(random.choice(self.lojas_ancora))
        if len(self.lojas_rotativas) >= 2: lojas_selecionadas.extend(random.sample(self.lojas_rotativas, 2))
        else: lojas_selecionadas.extend(self.lojas_rotativas)
        random.shuffle(lojas_selecionadas)
        return lojas_selecionadas[:3]

    # --- NOVA LÓGICA DE APRESENTAÇÃO ---
    def apresentar_resultados(self, produtos: list[dict]) -> str:
        if not produtos or len(produtos) < 3: return "Não encontrei recomendações suficientes."

        # --- Sub-funções para gerar o HTML rico ---
        def _gerar_selo_destaque(p: dict) -> str:
            notas = p.get('avaliacoes', {}).get('notas_detalhadas', {})
            custo_beneficio = p.get('avaliacoes', {}).get('custo_beneficio', 0)
            
            # Mapeia a característica para o selo e a nota
            mapeamento_selos = {
                "🚀 Super Desempenho": notas.get("desempenho", 0),
                "📸 Câmera Pro": notas.get("camera_principal", 0),
                "🔋 Bateria Monstra": notas.get("bateria", 0),
                "👑 Rei do Custo-Benefício": custo_beneficio
            }
            # Encontra a característica com a maior nota
            melhor_caracteristica = max(mapeamento_selos, key=mapeamento_selos.get)
            maior_nota = mapeamento_selos[melhor_caracteristica]

            if maior_nota > 8.8: # Limiar para exibir o selo
                return f"<div class='absolute top-2 right-2 bg-blue-500 text-white text-xs font-bold px-2 py-1 rounded-full shadow-lg'>{melhor_caracteristica}</div>"
            return ""

        def _gerar_html_card(p: dict) -> str:
            selo_html = _gerar_selo_destaque(p)
            imagem_url = p.get('identificacao', {}).get('imagem_url', '[https://via.placeholder.com/150](https://via.placeholder.com/150)')
            avaliacao = p.get('avaliacoes', {}).get('avaliacao_geral')
            
            # Specs com Ícones
            specs_html = f"""
            <div class='grid grid-cols-2 gap-2 text-xs text-gray-300 my-3'>
                <span class='flex items-center gap-1'>📱 {p.get('especificacoes', {}).get('tela', {}).get('tamanho_polegadas', '?')}”</span>
                <span class='flex items-center gap-1'>🔋 {p.get('especificacoes', {}).get('bateria', {}).get('capacidade_mah', '?')} mAh</span>
                <span class='flex items-center gap-1'>📷 {p.get('especificacoes', {}).get('cameras', {}).get('principal', {}).get('megapixels', '?')} MP</span>
                <span class='flex items-center gap-1'>⚙️ {p.get('especificacoes', {}).get('desempenho', {}).get('memoria_ram_gb', ['?'])[0]} GB RAM</span>
            </div>
            """
            positivos = p.get('avaliacoes', {}).get("positivos_percebidos") or []
            positivos_html = "".join([f"<li class='flex items-start gap-2 text-xs'><span class='text-green-400'>✅</span><span>{b}</span></li>" for b in positivos[:2]]) # Mostra apenas 2 para economizar espaço
            
            return f"""
            <div class="relative flex-shrink-0 w-11/12 snap-center bg-[#2a2a46] text-white p-4 rounded-xl shadow-md border border-gray-700/50">
                {selo_html}
                <div class='flex gap-4'>
                    <img src='{imagem_url}' alt='{p.get("identificacao", {}).get("nome_completo", "")}' class='w-24 h-24 object-contain rounded-lg'/>
                    <div>
                        <h3 class="text-lg font-bold text-blue-400">{p.get("identificacao", {}).get("nome_completo", "Modelo desconhecido")}</h3>
                        <p class='text-xs text-gray-400 mb-2 italic'>👤 {p.get('avaliacoes', {}).get('perfil_ideal', '')}</p>
                        {'<span class="text-amber-400 font-bold">⭐ ' + str(avaliacao) + '/10</span>' if avaliacao else ''}
                    </div>
                </div>
                {specs_html}
                <h4 class='font-semibold text-xs mb-1'>Destaques:</h4>
                <ul class='space-y-1'>{positivos_html}</ul>
            </div>
            """

        def _gerar_html_tabela_comparativa(produtos: list[dict]) -> str:
            headers_html = "".join([f"<th class='p-2 text-sm font-semibold text-blue-400'>{p.get('identificacao',{}).get('modelo','?')}</th>" for p in produtos])
            
            def get_row(label, key_path):
                cells_html = ""
                for p in produtos:
                    value = p
                    try:
                        for key in key_path: value = value.get(key, {})
                    except (AttributeError, TypeError): value = "-"
                    cells_html += f"<td class='p-2 text-center'>{value}</td>"
                return f"<tr><td class='p-2 font-semibold text-left'>{label}</td>{cells_html}</tr>"

            tabela_html = f"""
            <div class='bg-[#2a2a46] text-white p-4 rounded-xl shadow-md border border-gray-700/50 overflow-x-auto'>
                <table class='w-full text-xs text-left'>
                    <thead><tr class='border-b border-gray-700'><th>Característica</th>{headers_html}</tr></thead>
                    <tbody class='divide-y divide-gray-700'>
                        {get_row("⭐ Avaliação Geral", ["avaliacoes", "avaliacao_geral"])}
                        {get_row("💰 Custo-Benefício", ["avaliacoes", "custo_beneficio"])}
                        {get_row("📱 Tela (pol)", ["especificacoes", "tela", "tamanho_polegadas"])}
                        {get_row("📷 Câmera (MP)", ["especificacoes", "cameras", "principal", "megapixels"])}
                        {get_row("🔋 Bateria (mAh)", ["especificacoes", "bateria", "capacidade_mah"])}
                        {get_row("⚙️ Processador", ["especificacoes", "desempenho", "processador"])}
                        {get_row("📈 Preço (R$)", ["compra", "preco_medio_lancamento_brl"])}
                    </tbody>
                </table>
            </div>
            """
            return tabela_html

        # --- Construção do HTML Final ---
        toggle_buttons_html = """
        <div class="flex items-center justify-center gap-2 mb-3">
            <button data-view="carousel" class="view-toggle-button active-view-button text-xs px-3 py-1 rounded-full">Resumo</button>
            <button data-view="accordion" class="view-toggle-button inactive-view-button text-xs px-3 py-1 rounded-full">Detalhes</button>
            <button data-view="table" class="view-toggle-button inactive-view-button text-xs px-3 py-1 rounded-full">Comparar</button>
        </div>
        """
        
        # Visão Carrossel (Resumo)
        carousel_html = "<div id='view-carousel' class='card-carousel flex overflow-x-auto snap-x snap-mandatory space-x-4 py-2'>"
        for p in produtos: carousel_html += _gerar_html_card(p)
        carousel_html += "</div><p class='text-xs text-gray-400 mt-1 text-center md:hidden'> arraste para o lado para ver mais opções.</p>"

        # Visão Acordeão (Detalhes) - Simplificada para usar o mesmo card, mas pode ser expandida
        accordion_html = "<div id='view-accordion' class='hidden space-y-2'>"
        for p in produtos: accordion_html += _gerar_html_card(p) # Reutilizando o card para simplicidade
        accordion_html += "</div>"
        
        # Visão Tabela (Comparar)
        table_html = f"<div id='view-table' class='hidden'>{_gerar_html_tabela_comparativa(produtos)}</div>"
        
        # Bloco de Lojas
        lojas_selecionadas = self.selecionar_lojas()
        lojas_html = "<div class='mt-6 text-center'><h4 class='text-sm font-semibold text-white mb-2'>Confira os preços e promoções nas lojas a seguir:</h4><div class='flex flex-wrap justify-center gap-2'>"
        for loja in lojas_selecionadas: lojas_html += f"""<a href="{loja['url']}" target="_blank" class="block bg-gray-700 hover:bg-gray-600 rounded-lg px-4 py-2 transition text-sm text-white font-semibold">🛒 {loja['nome']}</a>"""
        lojas_html += "</div></div>"
        
        return f"""<div class="interactive-results">{toggle_buttons_html}{carousel_html}{accordion_html}{table_html}{lojas_html}</div>"""