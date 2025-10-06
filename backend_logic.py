# -*- coding: utf-8 -*-

import os
import json
import google.generativeai as genai
from typing import Dict, Any, List

# --- Configuração da API ---
# Para executar este script, você precisa de uma chave de API do Google AI Studio.
# 1. Acesse https://aistudio.google.com/app/apikey
# 2. Crie uma nova chave de API.
# 3. Defina a chave como uma variável de ambiente chamada 'GEMINI_API_KEY'.
#    No Linux/macOS: export GEMINI_API_KEY='SUA_CHAVE_AQUI'
#    No Windows: set GEMINI_API_KEY='SUA_CHAVE_AQUI'
# Ou, descomente a linha abaixo e cole sua chave diretamente (não recomendado para produção).
# os.environ['GEMINI_API_KEY'] = 'SUA_CHAVE_AQUI'

try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    print("Erro: A variável de ambiente 'GEMINI_API_KEY' não foi definida.")
    print("Por favor, defina a chave de API para continuar.")
    exit()

class ConsultorInteligente:
    """
    Implementa a lógica de backend para o Consultor Inteligente, utilizando
    a API Gemini para processar as solicitações dos usuários e encontrar celulares.
    """

    def __init__(self):
        # Usamos o grounding com a busca do Google para obter informações em tempo real.
        self.model = genai.GenerativeModel(
            'gemini-1.5-flash-latest',
            tools=['google_search']
        )

    def _extrair_json_da_resposta(self, text: str) -> Any:
        """
        Tenta extrair um objeto JSON de uma string de texto, mesmo que esteja
        envolvido por marcadores de código.
        """
        try:
            # Procura por blocos de código JSON
            json_block = text.strip()
            if json_block.startswith("```json"):
                json_block = json_block[7:]
            if json_block.endswith("```"):
                json_block = json_block[:-3]
            
            return json.loads(json_block.strip())
        except json.JSONDecodeError:
            print(f"Alerta: Não foi possível decodificar o JSON da resposta: {text}")
            return None
        except Exception as e:
            print(f"Erro inesperado ao extrair JSON: {e}")
            return None

    def captar_intencao(self, query_usuario: str) -> Dict[str, Any]:
        """
        Passo 1: Usa a IA para analisar a consulta do usuário e extrair
        critérios de busca estruturados.
        """
        prompt = f"""
        Você é um sistema especialista em análise de intenção de busca para um comparador de celulares.
        Analise a seguinte consulta de um usuário: "{query_usuario}"

        Extraia as seguintes informações em um formato JSON:
        1.  "uso_principal": Qual o principal objetivo do usuário com o celular? (Ex: 'fotos', 'jogos', 'trabalho', 'uso_geral', 'bateria').
        2.  "caracteristicas_chave": Uma lista de características específicas mencionadas. (Ex: ['câmera boa', 'bateria duradoura', 'tela grande', 'barato']).
        3.  "faixa_preco": Qual a faixa de preço implícita? (Ex: 'básico', 'intermediário', 'top de linha', 'custo-benefício').

        Retorne APENAS o objeto JSON.
        Exemplo para "celular bom e barato pra tirar foto":
        {{
            "uso_principal": "fotos",
            "caracteristicas_chave": ["câmera boa", "barato"],
            "faixa_preco": "custo-benefício"
        }}
        """
        print("--- 1. Captando Intenção do Usuário ---")
        response = self.model.generate_content(prompt)
        print("Intenção extraída (JSON):", response.text)
        return self._extrair_json_da_resposta(response.text) or {}

    def buscar_produtos(self, intencao: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Passo 2: Usa a IA com busca em tempo real para encontrar produtos
        que correspondam à intenção do usuário e estruturar os dados.
        """
        prompt = f"""
        Você é um especialista em tecnologia que ajuda usuários a encontrar o celular ideal.
        Com base nos seguintes critérios de busca: {json.dumps(intencao, ensure_ascii=False)}

        Use a busca em tempo real para encontrar os 3 melhores modelos de celular disponíveis no mercado brasileiro que atendam a esses critérios.
        Para cada modelo, forneça as seguintes informações em um formato de lista de objetos JSON:
        - "marca_modelo": A marca e o nome do modelo (Ex: "Samsung Galaxy S24").
        - "beneficios": Uma lista de 3 a 4 strings curtas que traduzem especificações técnicas em benefícios claros para o usuário, com base na intenção de busca. (Ex: "Tira fotos incríveis mesmo com pouca luz", "Bateria que dura o dia todo sem preocupação").
        - "precos_referencia": Uma lista de 2 a 3 objetos com a "loja" (nome do varejista) e o "preco" (uma string formatada como "R$ X.XXX,XX").

        Retorne APENAS a lista de objetos JSON.
        Exemplo de formato de saída:
        [
            {{
                "marca_modelo": "Xiaomi Redmi Note 13",
                "beneficios": [
                    "Câmera de 108MP para fotos cheias de detalhes.",
                    "Tela AMOLED vibrante para assistir vídeos.",
                    "Carregamento super rápido de 33W."
                ],
                "precos_referencia": [
                    {{ "loja": "Amazon BR", "preco": "R$ 1.299,00" }},
                    {{ "loja": "Mercado Livre", "preco": "R$ 1.350,00" }}
                ]
            }}
        ]
        """
        print("\n--- 2. Buscando Produtos com Base na Intenção ---")
        response = self.model.generate_content(prompt)
        print("Produtos encontrados (JSON):", response.text)
        return self._extrair_json_da_resposta(response.text) or []

    def apresentar_resultados(self, produtos: List[Dict[str, Any]], query_original: str) -> str:
        """
        Passo 3: Usa a IA para formatar os dados estruturados em uma
        resposta amigável e conversacional para o usuário.
        """
        prompt = f"""
        Você é o "Consultor Inteligente" do site Bomdemarca. Sua personalidade é amigável, prestativa e didática.
        A consulta original do usuário foi: "{query_original}".
        Você encontrou os seguintes celulares: {json.dumps(produtos, ensure_ascii=False)}

        Apresente esses resultados para o usuário. Siga esta estrutura:
        1.  Comece com uma saudação e uma breve introdução, confirmando que você entendeu o que ele precisa.
        2.  Para cada celular, crie um pequeno parágrafo destacando o nome do aparelho em negrito.
        3.  Liste os 'beneficios' como um bullet point (usando emojis).
        4.  Mostre os 'precos_referencia' de forma clara.
        5.  Termine com uma conclusão amigável, dizendo que esses links são de parceiros e desejando uma boa escolha.

        Use uma linguagem simples e direta, focada no público-alvo que não entende muito de especificações técnicas.
        """
        print("\n--- 3. Formatando a Apresentação Final ---")
        response = self.model.generate_content(prompt)
        return response.text

    def obter_recomendacao(self, query_usuario: str) -> str:
        """
        Orquestra todo o fluxo, desde a consulta inicial até a recomendação final.
        """
        intencao = self.captar_intencao(query_usuario)
        if not intencao:
            return "Desculpe, não consegui entender o que você precisa. Poderia tentar de outra forma?"

        produtos = self.buscar_produtos(intencao)
        if not produtos:
            return "Puxa, fiz uma busca aqui mas não encontrei nenhum celular que se encaixe perfeitamente no seu pedido. Que tal tentarmos outros termos?"

        return self.apresentar_resultados(produtos, query_usuario)


# --- Exemplo de Execução ---
if __name__ == "__main__":
    consultor = ConsultorInteligente()

    # Pega uma das palavras-chave do seu plano para testar
    # consulta_exemplo = "Melhor celular custo-benefício"
    consulta_exemplo = "celular para jogos com boa bateria"
    # consulta_exemplo = "qual celular comprar para fotos até 2000 reais"


    print(f"==================================================")
    print(f"CONSULTA DO USUÁRIO: \"{consulta_exemplo}\"")
    print(f"==================================================\n")

    recomendacao_final = consultor.obter_recomendacao(consulta_exemplo)

    print("\n\n==================================================")
    print("RESPOSTA FINAL PARA O USUÁRIO (FRONT-END)")
    print("==================================================")
    print(recomendacao_final)
