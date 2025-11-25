import logging
import csv
import os
import re
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    ContextTypes, ConversationHandler
)

#Importar spaCy
try:
    import spacy
    # Carregar modelo em português
    nlp = spacy.load("pt_core_news_sm")
    SPACY_AVAILABLE = True
    print(" spaCy carregado com sucesso!")
except ImportError:
    print(" spaCy não instalado. Use: pip install spacy")
    print(" E depois: python -m spacy download pt_core_news_sm")
    SPACY_AVAILABLE = False
except OSError:
    print("Modelo pt_core_news_sm não encontrado.")
    print(" Execute: python -m spacy download pt_core_news_sm")
    SPACY_AVAILABLE = False

# Configuração do logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Estados da conversação
ACEITAR, INICIAIS, DATA_NASCIMENTO, DATA_PARTO, PERGUNTA_A, PERGUNTA_B, PERGUNTA_C = range(7)

# Nome do arquivo CSV
CSV_FILENAME = "dados_pacientes.csv"

#Dicionários de sinônimos e mapeamento para o spaCy
MApeamento_SINTOMAS = {
    'febre': ['febre', 'calor', 'temperatura', 'quente', 'aquecida', 'febril', '37.5', '38'],
    'calafrio': ['calafrio', 'tremedeira', 'tremor', 'calafrios', 'tremendo'],
    'dor_corpo': ['dor', 'dores', 'corpo dolorido', 'dói', 'dor no corpo', 'dores no corpo'],
    'nenhum_sintoma': ['nenhum', 'nada', 'tudo bem', 'estou bem', 'não sinto nada']
}

Mapeamento_SINAIS = {
    'sangramento': ['sangramento', 'sangrando', 'sangra', 'sangue'],
    'secrecao': ['líquido amarelo', 'líquido esverdeado', 'líquido marrom', 'secreção', 'pus', 'corrimento', 'amarelo', 'verde', 'marrom'],
    'vermelhidao': ['vermelhidão', 'vermelho', 'avermelhado', 'inchado', 'inflamado'],
    'calor_local': ['quente', 'calor', 'aquecido', 'ardendo'],
    'pontos_abertos': ['abriu', 'pontos abertos', 'pontos soltos', 'arrebentou', 'rompeu'],
    'mal_cheiro': ['mal cheiro', 'fedendo', 'fedor', 'cheiro ruim'],
    'nenhum_sinal': ['nenhum', 'nada', 'tudo normal', 'está bom']
}

# Dados do paciente
class Paciente:
    def __init__(self):
        self.iniciais = ""
        self.data_nascimento = ""
        self.data_parto = ""
        self.respostas = {}
        self.data_preenchimento = ""
        self.telegram_user_id = ""

#Função para iniciar com QUALQUER mensagem
async def iniciar_conversa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia a conversa quando o usuário envia QUALQUER mensagem"""
    
    # Verifica se já existe uma conversa em andamento
    if 'paciente' in context.user_data:
        # Se já existe uma conversa, não reinicia
        return await handle_mensagem_qualquer(update, context)
    
    # Inicia nova conversa
    context.user_data['paciente'] = Paciente()
    context.user_data['paciente'].telegram_user_id = update.effective_user.id
    context.user_data['paciente'].data_preenchimento = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    
    keyboard = [
        [KeyboardButton("SIM"), KeyboardButton("NÃO")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "👋 Olá! Sou assistente virtual da Comissão de Controle de Vigilância Hospitalar e "
        "gostaria de saber como você está após seu parto cesariano para garantir que "
        "sua recuperação esteja indo bem. Serão apenas 5 minutos, onde faremos 3 perguntas "
        "com alternativas de resposta.\n\n"
        "Você aceita seguir com a conversa nesse momento?",
        reply_markup=reply_markup
    )
    return ACEITAR

async def handle_mensagem_qualquer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lida com mensagens enviadas durante conversas em andamento"""
    await update.message.reply_text(
        "🤔 Você já tem uma conversa em andamento. "
        "Se quiser recomeçar, use /start para iniciar uma nova conversa.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

#Função start tradicional para quem preferir usar o comando
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Função start tradicional - opcional"""
    context.user_data['paciente'] = Paciente()
    context.user_data['paciente'].telegram_user_id = update.effective_user.id
    context.user_data['paciente'].data_preenchimento = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    
    keyboard = [
        [KeyboardButton("SIM"), KeyboardButton("NÃO")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "👋 Olá! Sou assistente virtual da Comissão de Controle de Vigilância Hospitalar e "
        "gostaria de saber como você está após seu parto cesariano para garantir que "
        "sua recuperação esteja indo bem. Serão apenas 5 minutos, onde faremos 3 perguntas "
        "com alternativas de resposta.\n\n"
        "Você aceita seguir com a conversa nesse momento?",
        reply_markup=reply_markup
    )
    return ACEITAR

#Funções de Processamento de Linguagem Natural com spaCy
def processar_texto_spacy(texto):
    """Processa texto usando spaCy para extrair informações relevantes"""
    if not SPACY_AVAILABLE:
        return processar_texto_simples(texto)
    
    doc = nlp(texto.lower())
    
    # Extrair tokens relevantes (remover stop words)
    tokens_relevantes = []
    for token in doc:
        if not token.is_stop and not token.is_punct and token.is_alpha:
            tokens_relevantes.append(token.lemma_)
    
    return tokens_relevantes

def identificar_sintomas(texto):
    """Identifica sintomas no texto usando spaCy"""
    tokens = processar_texto_spacy(texto)
    
    sintomas_identificados = []
    
    for token in tokens:
        for sintoma, sinônimos in MApeamento_SINTOMAS.items():
            if any(sinônimo in token for sinônimo in sinônimos):
                if sintoma not in sintomas_identificados and sintoma != 'nenhum_sintoma':
                    sintomas_identificados.append(sintoma)
    
    # Verificar se mencionou "nenhum sintoma"
    texto_limpo = texto.lower()
    for palavra in MApeamento_SINTOMAS['nenhum_sintoma']:
        if palavra in texto_limpo:
            return ['4']  # Retorna código para "nenhum sintoma"
    
    # Mapear para códigos numéricos
    codigos = []
    for sintoma in sintomas_identificados:
        if sintoma == 'febre':
            codigos.append('1')
        elif sintoma == 'calafrio':
            codigos.append('2')
        elif sintoma == 'dor_corpo':
            codigos.append('3')
    
    return codigos if codigos else None

def identificar_sinais_cesariana(texto):
    """Identifica sinais na cesariana usando spaCy"""
    tokens = processar_texto_spacy(texto)
    
    sinais_identificados = []
    
    for token in tokens:
        for sinal, sinônimos in Mapeamento_SINAIS.items():
            if any(sinônimo in token for sinônimo in sinônimos):
                if sinal not in sinais_identificados and sinal != 'nenhum_sinal':
                    sinais_identificados.append(sinal)
    
    # Verificar se mencionou "nenhum sinal"
    texto_limpo = texto.lower()
    for palavra in Mapeamento_SINAIS['nenhum_sinal']:
        if palavra in texto_limpo:
            return ['7']  # Retorna código para "nenhum sinal"
    
    # Mapear para códigos numéricos
    codigos = []
    for sinal in sinais_identificados:
        if sinal == 'sangramento':
            codigos.append('1')
        elif sinal == 'secrecao':
            codigos.append('2')
        elif sinal == 'vermelhidao':
            codigos.append('3')
        elif sinal == 'calor_local':
            codigos.append('4')
        elif sinal == 'pontos_abertos':
            codigos.append('5')
        elif sinal == 'mal_cheiro':
            codigos.append('6')
    
    return codigos if codigos else None

def processar_texto_simples(texto):
    """Fallback se spaCy não estiver disponível"""
    texto = texto.lower()
    
    # Verificação simples por palavras-chave
    sintomas = []
    if any(palavra in texto for palavra in ['febre', 'calor', 'temperatura']):
        sintomas.append('1')
    if any(palavra in texto for palavra in ['calafrio', 'tremedeira', 'tremor']):
        sintomas.append('2')
    if any(palavra in texto for palavra in ['dor', 'dores', 'dói']):
        sintomas.append('3')
    if any(palavra in texto for palavra in ['nenhum', 'nada', 'tudo bem']):
        return ['4']
    
    return sintomas if sintomas else None

# Função para inicializar o arquivo CSV com cabeçalhos
def inicializar_csv():
    if not os.path.exists(CSV_FILENAME):
        with open(CSV_FILENAME, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            headers = [
                'Data_Preenchimento', 'Telegram_User_ID', 'Iniciais_Nome', 
                'Data_Nascimento', 'Data_Parto', 'Pergunta_A_Sintomas',
                'Pergunta_B_Tempo_Sintomas', 'Pergunta_C_Sinais_Cesariana',
                'Recomendacao', 'Alerta_Risco', 'Texto_Original_A', 'Texto_Original_C'
            ]
            writer.writerow(headers)

#Função para salvar dados no CSV
def salvar_no_csv(paciente, telegram_user_id, recomendacao, alerta_risco, texto_original_a="", texto_original_c=""):
    try:
        with open(CSV_FILENAME, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            linha = [
                paciente.data_preenchimento,
                telegram_user_id,
                paciente.iniciais,
                paciente.data_nascimento,
                paciente.data_parto,
                paciente.respostas.get('pergunta_a', ''),
                paciente.respostas.get('pergunta_b', ''),
                paciente.respostas.get('pergunta_c', ''),
                recomendacao,
                alerta_risco,
                texto_original_a,
                texto_original_c
            ]
            
            writer.writerow(linha)
        logging.info(f"Dados salvos no CSV para: {paciente.iniciais}")
        return True
    except Exception as e:
        logging.error(f"Erro ao salvar no CSV: {e}")
        return False

# Função para validar data no formato DD/MM/AAAA
def validar_data(data_str, tipo="nascimento"):
    try:
        data = datetime.strptime(data_str, '%d/%m/%Y')
        
        if tipo == "nascimento":
            if data > datetime.now():
                return False, "Data de nascimento não pode ser no futuro."
        elif tipo == "parto":
            if data > datetime.now():
                return False, "Data do parto não pode ser no futuro."
        
        return True, data_str
    except ValueError:
        return False, "Formato inválido. Use DD/MM/AAAA."

#Função para validar APENAS iniciais
def validar_iniciais(iniciais_str):
    iniciais_limpas = iniciais_str.strip().upper()
    
    if not iniciais_limpas:
        return False, "Iniciais não podem estar vazias."
    
    if not re.match(r'^[A-ZÀ-ÿ]+$', iniciais_limpas.replace(' ', '')):
        return False, "Use apenas letras para as iniciais (sem números ou caracteres especiais)."
    
    if len(iniciais_limpas.replace(' ', '')) > 10:
        return False, "Por favor, digite apenas as iniciais (máximo 10 letras). Ex: PRN"
    
    if len(iniciais_limpas.replace(' ', '')) < 2:
        return False, "Digite pelo menos 2 letras para as iniciais."
    
    return True, iniciais_limpas

async def aceitar_conversa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resposta = update.message.text.upper()
    
    if resposta == "NÃO":
        await update.message.reply_text(
            "Retorne com seu médico ou enfermeira do pré-natal para sua consulta de resguardo "
            "e em caso de sintomas como febre, vermelhidão e secreção no local da cesariana "
            "retorna à maternidade onde realizou o parto.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    elif resposta == "SIM":
        await update.message.reply_text(
            "Maravilha! Antes, digite apenas as **iniciais do seu nome**.\n\n"
            "💡 *Exemplos:*\n"
            "• Patrícia Rodrigues Nunes → **PRN**\n"
            "• Maria Silva → **MS**\n"
            "• Ana Clara Santos → **ACS**\n\n"
            "Por favor, digite apenas as iniciais:",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )
        return INICIAIS

async def obter_iniciais(update: Update, context: ContextTypes.DEFAULT_TYPE):
    iniciais_input = update.message.text.upper()
    
    valido, resultado = validar_iniciais(iniciais_input)
    
    if not valido:
        await update.message.reply_text(
            f"✋ {resultado}\n\n"
            "💡 *Digite apenas as iniciais:*\n"
            "• Exemplo 1: PRN\n"
            "• Exemplo 2: MS\n"
            "• Exemplo 3: ACS\n\n"
            "Por favor, digite novamente as iniciais:",
            parse_mode='Markdown'
        )
        return INICIAIS
    
    context.user_data['paciente'].iniciais = resultado
    await update.message.reply_text("Informe sua data de nascimento (ex: 08/11/1987):")
    return DATA_NASCIMENTO

async def obter_data_nascimento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data_input = update.message.text
    
    valido, resultado = validar_data(data_input, "nascimento")
    
    if not valido:
        await update.message.reply_text(
            f"Data inválida! {resultado}\n"
            "Por favor, digite no formato DD/MM/AAAA (ex: 08/11/1987):"
        )
        return DATA_NASCIMENTO
    
    context.user_data['paciente'].data_nascimento = data_input
    await update.message.reply_text("Informe a data do parto (ex: 23/05/2025):")
    return DATA_PARTO

async def obter_data_parto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data_input = update.message.text
    
    valido, resultado = validar_data(data_input, "parto")
    
    if not valido:
        await update.message.reply_text(
            f"Data inválida! {resultado}\n"
            "Por favor, digite no formato DD/MM/AAAA (ex: 23/05/2025):"
        )
        return DATA_PARTO
    
    context.user_data['paciente'].data_parto = data_input
    
    # Teclado apenas com opções numéricas
    keyboard = [
        [KeyboardButton("1 - Febre"), KeyboardButton("2 - Calafrio")],
        [KeyboardButton("3 - Dor no corpo"), KeyboardButton("4 - Nenhum sintoma")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "Vamos às perguntas!\n\n"
        "A. Você sente 1 ou mais desses sintomas abaixo? "
        "📝 *Você pode escolher os números OU descrever com suas palavras*\n\n"
        "1. Febre (temperatura ≥ 37,5°C)\n"
        "2. Calafrio (tremedeira)\n"
        "3. Dor no corpo\n"
        "4. Nenhum dos sintomas\n\n"
        "💡 *Dica: Pode digitar como preferir! Ex: \"estou com febre\" ou \"1\"*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return PERGUNTA_A

#Função da pergunta A com spaCy
async def pergunta_a(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resposta = update.message.text
    texto_original = resposta  # Guardar texto original
    
    #Processar com spaCy
    sintomas_identificados = None
    
    # Se for número ou opção do botão, processa
    if resposta in ['1', '2', '3', '4', '1 - Febre', '2 - Calafrio', '3 - Dor no corpo', '4 - Nenhum sintoma']:
        # Extrai apenas o número se veio do botão
        if ' - ' in resposta:
            resposta_final = resposta.split(' - ')[0]
        else:
            resposta_final = resposta
    # Se for texto, processa com spaCy
    else:
        sintomas_identificados = identificar_sintomas(resposta)
        
        if sintomas_identificados:
            if len(sintomas_identificados) == 1:
                resposta_final = sintomas_identificados[0]
            else:
                resposta_final = ','.join(sintomas_identificados)
            
            # Feedback do que foi entendido
            await update.message.reply_text(
                f"✅ Entendi! Você mencionou: {', '.join(sintomas_identificados)}"
            )
        else:
            # Se não entendeu, pede para tentar novamente
            await update.message.reply_text(
                "🤔 Não consegui identificar os sintomas. "
                "Pode descrever melhor ou usar os números (1, 2, 3, 4)?\n\n"
                "Exemplos:\n"
                "• \"estou com febre\"\n" 
                "• \"calafrios e dor\"\n"
                "• \"não sinto nada\""
            )
            return PERGUNTA_A
    
    context.user_data['paciente'].respostas['pergunta_a'] = resposta_final
    context.user_data['texto_original_a'] = texto_original  # Guardar original
    
    # Se resposta for "4" (nenhum sintoma), pula para pergunta C
    if resposta_final == "4":
        context.user_data['paciente'].respostas['pergunta_b'] = "NÃO SE APLICA"
        
        keyboard = [
            [KeyboardButton("1 - Sangramento"), KeyboardButton("2 - Secreção")],
            [KeyboardButton("3 - Vermelhidão"), KeyboardButton("4 - Calor local")],
            [KeyboardButton("5 - Pontos abertos"), KeyboardButton("6 - Mal cheiro")],
            [KeyboardButton("7 - Nenhum sinal")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        await update.message.reply_text(
            "C. Por favor, nos responda: você percebe alguns desses sinais no local da sua cesariana? "
            "📝 *Você pode escolher os números OU descrever com suas palavras*\n\n"
            "1. Sangramento\n"
            "2. Líquido amarelo, esverdeado ou marrom\n"
            "3. Vermelhidão\n"
            "4. Local dos pontos está quente\n"
            "5. Abriu 1 ou mais pontos\n"
            "6. Mal cheiro\n"
            "7. Nenhum desses sinais\n\n"
            "💡 *Dica: Pode digitar como preferir! Ex: \"está vermelho\" ou \"3\"*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return PERGUNTA_C
    else:
        # Se respondeu 1, 2 ou 3, vai para pergunta B
        keyboard = [
            [KeyboardButton("1 - Desde a alta"), KeyboardButton("2 - 1-2 dias")],
            [KeyboardButton("3 - 3+ dias")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        await update.message.reply_text(
            "B. Dando continuidade, nos responda: Há quanto tempo sente esses sintomas?\n\n"
            "1. Desde que saí do hospital\n"
            "2. 1 ou 2 dias\n"
            "3. 3 dias ou mais dias\n\n"
            "Resposta:",
            reply_markup=reply_markup
        )
        return PERGUNTA_B

async def pergunta_b(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resposta = update.message.text
    
    # Processar possíveis respostas em texto
    if resposta in ['1', '2', '3', '1 - Desde a alta', '2 - 1-2 dias', '3 - 3+ dias']:
        # Extrai apenas o número se veio do botão
        if ' - ' in resposta:
            resposta_final = resposta.split(' - ')[0]
        else:
            resposta_final = resposta
    else:
        texto = resposta.lower()
        if any(palavra in texto for palavra in ['desde', 'alta', 'hospital']):
            resposta_final = '1'
        elif any(palavra in texto for palavra in ['1', 'um', 'dois', '2', 'poucos']):
            resposta_final = '2'
        elif any(palavra in texto for palavra in ['3', 'três', 'mais', 'vários']):
            resposta_final = '3'
        else:
            resposta_final = resposta  # Guarda o texto original
    
    context.user_data['paciente'].respostas['pergunta_b'] = resposta_final
    
    keyboard = [
        [KeyboardButton("1 - Sangramento"), KeyboardButton("2 - Secreção")],
        [KeyboardButton("3 - Vermelhidão"), KeyboardButton("4 - Calor local")],
        [KeyboardButton("5 - Pontos abertos"), KeyboardButton("6 - Mal cheiro")],
        [KeyboardButton("7 - Nenhum sinal")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "C. Por favor, nos responda: você percebe alguns desses sinais no local da sua cesariana? "
        "📝 *Você pode escolher os números OU descrever com suas palavras*\n\n"
        "1. Sangramento\n"
        "2. Líquido amarelo, esverdeado ou marrom\n"
        "3. Vermelhidão\n"
        "4. Local dos pontos está quente\n"
        "5. Abriu 1 ou mais pontos\n"
        "6. Mal cheiro\n"
        "7. Nenhum desses sinais\n\n"
        "💡 *Dica: Pode digitar como preferir! Ex: \"está vermelho\" ou \"3\"*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return PERGUNTA_C

#Função da pergunta C com spaCy
async def pergunta_c(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resposta = update.message.text
    texto_original = resposta  # Guardar texto original
    
    #Processar com spaCy
    sinais_identificados = None
    
    # Se for número ou opção do botão, processa
    if resposta in ['1', '2', '3', '4', '5', '6', '7', 
                   '1 - Sangramento', '2 - Secreção', '3 - Vermelhidão',
                   '4 - Calor local', '5 - Pontos abertos', '6 - Mal cheiro', 
                   '7 - Nenhum sinal']:
        # Extrai apenas o número se veio do botão
        if ' - ' in resposta:
            resposta_final = resposta.split(' - ')[0]
        else:
            resposta_final = resposta
    # Se for texto, processa com spaCy
    else:
        sinais_identificados = identificar_sinais_cesariana(resposta)
        
        if sinais_identificados:
            if len(sinais_identificados) == 1:
                resposta_final = sinais_identificados[0]
            else:
                resposta_final = ','.join(sinais_identificados)
            
            # Feedback do que foi entendido
            await update.message.reply_text(
                f"✅ Entendi! Você mencionou: {', '.join(sinais_identificados)}"
            )
        else:
            # Se não entendeu, usa texto original
            resposta_final = resposta
            await update.message.reply_text(
                "⚠️ Registrei sua descrição. Vamos analisar suas respostas."
            )
    
    context.user_data['paciente'].respostas['pergunta_c'] = resposta_final
    context.user_data['texto_original_c'] = texto_original  # Guardar original
    
    # Análise dos resultados
    recomendacao, alerta_risco = analisar_respostas(context.user_data['paciente'])
    
    # Salva os dados no CSV
    sucesso = salvar_no_csv(
        context.user_data['paciente'],
        context.user_data['paciente'].telegram_user_id,
        recomendacao,
        alerta_risco,
        context.user_data.get('texto_original_a', ''),
        context.user_data.get('texto_original_c', '')
    )
    
    mensagem_final = f"Pronto, terminamos! Muito obrigado por sua participação.\n\n{recomendacao}"
    
    if not sucesso:
        mensagem_final += "\n\n⚠️ Observação: Houve um problema técnico ao salvar seus dados."
    
    #Remove o teclado ao final
    await update.message.reply_text(
        mensagem_final,
        reply_markup=ReplyKeyboardRemove(),
        parse_mode='Markdown'
    )
    
    # Log dos dados
    logging.info(f"Paciente: {context.user_data['paciente'].iniciais}")
    logging.info(f"Data parto: {context.user_data['paciente'].data_parto}")
    logging.info(f"Respostas: {context.user_data['paciente'].respostas}")
    logging.info(f"Recomendação: {recomendacao}")
    logging.info(f"Alerta Risco: {alerta_risco}")
    
    # Limpa os dados da conversa
    context.user_data.clear()
    
    return ConversationHandler.END

def analisar_respostas(paciente):
    respostas = paciente.respostas
    
    # Contar sinais e sintomas
    sinais_sintomas_count = 0
    
    # Verificar sintomas (Pergunta A)
    pergunta_a = respostas.get('pergunta_a', '')
    if pergunta_a and pergunta_a != '4':  # Se não for "nenhum sintoma"
        sinais_sintomas_count += len(pergunta_a.split(',')) if ',' in pergunta_a else 1
    
    # Verificar sinais locais (Pergunta C)
    pergunta_c = respostas.get('pergunta_c', '')
    if pergunta_c and pergunta_c != '7':  # Se não for "nenhum sinal"
        sinais_sintomas_count += len(pergunta_c.split(',')) if ',' in pergunta_c else 1
    
    # CENÁRIO 1: 2 ou mais sinais/sintomas -> ALERTA VERMELHO
    if sinais_sintomas_count >= 2:
        recomendacao = "🚨 Baseado em suas respostas recomendamos que você retorne com urgência à maternidade onde fez sua cesariana para que seja avaliada por uma profissional de saúde."
        alerta_risco = "VERMELHO"
    
    # CENÁRIO 2: Nenhum sinal/sintoma -> Consulta de rotina
    else:
        recomendacao = "Baseado em suas respostas, recomendamos que retorne à unidade de saúde onde fez seu pré-natal para consulta do puerpério ou resguardo com sua médica ou enfermeiro."
        alerta_risco = "BAIXO"
    
    return recomendacao, alerta_risco

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Conversa interrompida. Se precisar reiniciar, envie qualquer mensagem ou use /start.",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

def main():
    # Inicializa o arquivo CSV
    inicializar_csv()
    
    # Verificar se spaCy está disponível
    if not SPACY_AVAILABLE:
        print("AVISO: spaCy não está disponível. Usando sistema de fallback.")
        print("Para melhor experiência, instale: pip install spacy && python -m spacy download pt_core_news_sm")
    
    # Token do bot
    TOKEN = "8441175313:AAF3UlhGCijQwZR09aQNFuN372DMPIL4Hgs"
    
    application = Application.builder().token(TOKEN).build()

    #Conversation handler com entrada para QUALQUER mensagem
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),  # Mantém o comando /start
            MessageHandler(filters.TEXT & ~filters.COMMAND, iniciar_conversa)  # 🔥 NOVO: Qualquer mensagem inicia
        ],
        states={
            ACEITAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, aceitar_conversa)],
            INICIAIS: [MessageHandler(filters.TEXT & ~filters.COMMAND, obter_iniciais)],
            DATA_NASCIMENTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, obter_data_nascimento)],
            DATA_PARTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, obter_data_parto)],
            PERGUNTA_A: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_a)],
            PERGUNTA_B: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_b)],
            PERGUNTA_C: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_c)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)

    print("Bot de monitoramento pós-cesárea COM spaCy está rodando...")
    print(f"Os dados serão salvos no arquivo: {CSV_FILENAME}")
    print("Agora o bot inicia com QUALQUER mensagem ou com /start")
    if SPACY_AVAILABLE:
        print("spaCy ativo - Chatbot entendendo linguagem natural!")
    else:
        print("spaCy inativo - Usando sistema básico")
    application.run_polling()

if __name__ == '__main__':
    main()
