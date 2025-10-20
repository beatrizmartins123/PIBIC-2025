import logging
import csv
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    ContextTypes, ConversationHandler
)

# Configuração do logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Estados da conversação
ACEITAR, NOME, DATA_PARTO, PERGUNTA_1, PERGUNTA_2, PERGUNTA_3, PERGUNTA_4, PERGUNTA_5, PERGUNTA_6, PERGUNTA_7, PERGUNTA_8, PERGUNTA_9, PERGUNTA_10, PERGUNTA_11, PERGUNTA_12, PERGUNTA_13, PERGUNTA_14, PERGUNTA_15, PERGUNTA_16, PERGUNTA_17 = range(20)

# Nome do arquivo CSV
CSV_FILENAME = "dados_pacientes.csv"

# Dados do paciente
class Paciente:
    def __init__(self):
        self.nome = ""
        self.data_parto = ""
        self.respostas = {}
        self.data_preenchimento = ""
        self.telegram_user_id = ""

# Função para inicializar o arquivo CSV com cabeçalhos
def inicializar_csv():
    if not os.path.exists(CSV_FILENAME):
        with open(CSV_FILENAME, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            # Cabeçalhos
            headers = [
                'Data_Preenchimento', 'Telegram_User_ID', 'Nome', 'Data_Parto',
                'P1_Sintomas', 'P2_Sangramento', 'P3_Edema_Local', 'P4_Edema_Pernas',
                'P5_Falta_Ar', 'P6_Nausea_Vomito', 'P7_Defecacao', 'P8_Vermelhidão',
                'P9_Calor_Local', 'P10_Secrecao', 'P11_Cor_Secrecao', 'P12_Ferida_Aberta',
                'P13_Mal_Cheiro', 'P14_Consulta_Resguardo', 'P15_Exames_Pos_Alta',
                'P16_Reinternacao', 'P17_Duvidas_Cuidados', 'Recomendacao'
            ]
            writer.writerow(headers)

# Função para salvar dados no CSV
def salvar_no_csv(paciente, telegram_user_id, recomendacao):
    try:
        with open(CSV_FILENAME, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Prepara os dados para a linha
            linha = [
                paciente.data_preenchimento,
                telegram_user_id,
                paciente.nome,
                paciente.data_parto,
                paciente.respostas.get('pergunta_1', ''),
                paciente.respostas.get('pergunta_2', ''),
                paciente.respostas.get('pergunta_3', ''),
                paciente.respostas.get('pergunta_4', ''),
                paciente.respostas.get('pergunta_5', ''),
                paciente.respostas.get('pergunta_6', ''),
                paciente.respostas.get('pergunta_7', ''),
                paciente.respostas.get('pergunta_8', ''),
                paciente.respostas.get('pergunta_9', ''),
                paciente.respostas.get('pergunta_10', ''),
                paciente.respostas.get('pergunta_11', ''),
                paciente.respostas.get('pergunta_12', ''),
                paciente.respostas.get('pergunta_13', ''),
                paciente.respostas.get('pergunta_14', ''),
                paciente.respostas.get('pergunta_15', ''),
                paciente.respostas.get('pergunta_16', ''),
                paciente.respostas.get('pergunta_17', ''),
                recomendacao
            ]
            
            writer.writerow(linha)
        logging.info(f"Dados salvos no CSV para o paciente: {paciente.nome}")
        return True
    except Exception as e:
        logging.error(f"Erro ao salvar no CSV: {e}")
        return False

# Função para validar data no formato DD/MM/AAAA
def validar_data(data_str):
    try:
        # Tenta fazer o parsing da data
        data = datetime.strptime(data_str, '%d/%m/%Y')
        
        # Verifica se a data não é no futuro
        if data > datetime.now():
            return False, "Data não pode ser no futuro."
        
        return True, data
    except ValueError:
        return False, "Formato inválido."

# Função para validar nome (apenas letras e espaços)
def validar_nome(nome_str):
    # Remove espaços extras no início e fim
    nome_limpo = nome_str.strip()
    
    # Verifica se o nome não está vazio
    if not nome_limpo:
        return False, "Nome não pode estar vazio."
    
    # Verifica se o nome tem pelo menos 2 caracteres
    if len(nome_limpo) < 2:
        return False, "Nome deve ter pelo menos 2 caracteres."
    
    # Verifica se contém apenas letras, espaços e alguns caracteres especiais comuns em nomes
    # Permitindo: letras, espaços, hífens e afins... :3
    import re
    padrao = r'^[a-zA-ZÀ-ÿ\s\-\']+$'
    
    if not re.match(padrao, nome_limpo):
        return False, "Nome deve conter apenas letras e espaços."
    
    # Verifica se tem pelo menos um espaço (nome e sobrenome)
    if ' ' not in nome_limpo:
        return False, "Por favor, digite seu nome completo (nome e sobrenome)."
    
    # Verifica se cada parte do nome tem pelo menos 2 caracteres
    partes_nome = nome_limpo.split()
    for parte in partes_nome:
        if len(parte) < 2:
            return False, "Cada parte do nome deve ter pelo menos 2 caracteres."
    
    return True, nome_limpo

# Início da conversa
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['paciente'] = Paciente()
    context.user_data['paciente'].telegram_user_id = update.effective_user.id
    context.user_data['paciente'].data_preenchimento = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    
    keyboard = [
        [KeyboardButton("SIM"), KeyboardButton("NÃO")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "Olá! Sou enfermeira do controle de Infecção Hospitalar da Maternidade e "
        "gostaria de contribuir com seu cuidado pós-operatório, fazendo algumas perguntas. "
        "Você aceita seguir com a conversa nesse momento?",
        reply_markup=reply_markup
    )
    return ACEITAR

async def aceitar_conversa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resposta = update.message.text.upper()
    
    if resposta == "NÃO":
        await update.message.reply_text(
            "Entendo. Informamos que essa conversa é muito importante para sua saúde. "
            "Aguardamos seu retorno.",
            reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
        )
        return ConversationHandler.END
    elif resposta == "SIM":
        await update.message.reply_text(
            "Maravilha! Nessa conversa você responde escolhendo a alternativa com a qual "
            "mais se identifica. Antes, confirme seu nome completo:",
            reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
        )
        return NOME

async def obter_nome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome_input = update.message.text
    
    # Valida o nome
    valido, resultado = validar_nome(nome_input)
    
    if not valido:
        await update.message.reply_text(
            f"Nome inválido! {resultado}\n"
            "Por favor, digite seu nome completo (ex: Maria Silva Santos):"
        )
        return NOME  # Permanece no mesmo estado para nova tentativa
    
    context.user_data['paciente'].nome = resultado
    await update.message.reply_text("Informe a data do parto (ex: 01/01/2024):")
    return DATA_PARTO

async def obter_data_parto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data_input = update.message.text
    
    # Valida o formato da data
    valido, resultado = validar_data(data_input)
    
    if not valido:
        await update.message.reply_text(
            f"Data inválida! {resultado}\n"
            "Por favor, digite a data no formato DD/MM/AAAA (ex: 15/03/2024):"
        )
        return DATA_PARTO  # Permanece no mesmo estado para nova tentativa
    
    context.user_data['paciente'].data_parto = data_input
    
    keyboard = [[KeyboardButton("SIM"), KeyboardButton("NÃO")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "Vamos às perguntas! Ah, uma dica: vamos chamar o local da cirurgia de ferida operatória 😉\n\n"
        "1. Você apresentou sintomas (calafrios, tremedeira, febre: T= 37,5°C, dor intensa) que a fizeram procurar atendimento médico depois que foi para casa?",
        reply_markup=reply_markup
    )
    return PERGUNTA_1

# Funções para as perguntas
async def pergunta_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['paciente'].respostas['pergunta_1'] = update.message.text.upper()
    
    keyboard = [[KeyboardButton("SIM"), KeyboardButton("NÃO")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "2. Sua ferida operatória apresentou sangramento persistente?",
        reply_markup=reply_markup
    )
    return PERGUNTA_2

async def pergunta_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['paciente'].respostas['pergunta_2'] = update.message.text.upper()
    
    keyboard = [[KeyboardButton("SIM"), KeyboardButton("NÃO")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "3. Há algum edema (inchaço) no local da cirurgia?",
        reply_markup=reply_markup
    )
    return PERGUNTA_3

async def pergunta_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['paciente'].respostas['pergunta_3'] = update.message.text.upper()
    
    keyboard = [[KeyboardButton("SIM"), KeyboardButton("NÃO")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "4. Você apresenta dor ou edema (inchaço) nas pernas?",
        reply_markup=reply_markup
    )
    return PERGUNTA_4

async def pergunta_4(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['paciente'].respostas['pergunta_4'] = update.message.text.upper()
    
    keyboard = [[KeyboardButton("SIM"), KeyboardButton("NÃO")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "5. Sente falta de ar ou cansaço aos mínimos esforços?",
        reply_markup=reply_markup
    )
    return PERGUNTA_5

async def pergunta_5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['paciente'].respostas['pergunta_5'] = update.message.text.upper()
    
    keyboard = [[KeyboardButton("SIM"), KeyboardButton("NÃO")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "6. Sente náusea (enjoo) ou apresentou vômito (provocou) depois que foi pra casa?",
        reply_markup=reply_markup
    )
    return PERGUNTA_6

async def pergunta_6(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['paciente'].respostas['pergunta_6'] = update.message.text.upper()
    
    keyboard = [
        [KeyboardButton("Nenhuma vez"), KeyboardButton("1 ou 2 vezes")],
        [KeyboardButton("Dia sim, dia não"), KeyboardButton("Defeco todos os dias")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "7. Desde que chegou em casa, você tem defecado 💩? Quantas vezes? Escolha uma das opções:",
        reply_markup=reply_markup
    )
    return PERGUNTA_7

async def pergunta_7(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['paciente'].respostas['pergunta_7'] = update.message.text
    
    keyboard = [
        [KeyboardButton("Não, está com aparência normal"), KeyboardButton("Um pouco (Vermelho claro)")],
        [KeyboardButton("Sim, bastante vermelho"), KeyboardButton("Está roxo")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "8. Você percebeu vermelhidão (cor vermelha) ao redor dos pontos cirúrgicos? Escolha uma das opções:",
        reply_markup=reply_markup
    )
    return PERGUNTA_8

async def pergunta_8(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['paciente'].respostas['pergunta_8'] = update.message.text
    
    keyboard = [[KeyboardButton("SIM"), KeyboardButton("NÃO")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "9. Você sentiu a pele ao redor dos pontos cirúrgicos mais quente que o normal?",
        reply_markup=reply_markup
    )
    return PERGUNTA_9

async def pergunta_9(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['paciente'].respostas['pergunta_9'] = update.message.text.upper()
    
    keyboard = [[KeyboardButton("SIM"), KeyboardButton("NÃO")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "10. Você notou se está saindo líquido ou secreção dos pontos?",
        reply_markup=reply_markup
    )
    return PERGUNTA_10

async def pergunta_10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resposta = update.message.text.upper()
    context.user_data['paciente'].respostas['pergunta_10'] = resposta
    
    if resposta == "SIM":
        keyboard = [
            [KeyboardButton("Transparente (líquido claro)"), KeyboardButton("Purulenta (amarela ou verde)")],
            [KeyboardButton("Sanguinolenta (líquido com aspecto de sangue)"), KeyboardButton("De cor amarronzada (marrom)")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        await update.message.reply_text(
            "11. Qual a cor do líquido que está saindo dos pontos cirúrgicos?",
            reply_markup=reply_markup
        )
        return PERGUNTA_11
    else:
        context.user_data['paciente'].respostas['pergunta_11'] = "NÃO SE APLICA"
        
        keyboard = [[KeyboardButton("SIM"), KeyboardButton("NÃO")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        await update.message.reply_text(
            "12. A ferida operatória abriu? 1 ou mais pontos soltaram (arrebentaram)?",
            reply_markup=reply_markup
        )
        return PERGUNTA_12

async def pergunta_11(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['paciente'].respostas['pergunta_11'] = update.message.text
    
    keyboard = [[KeyboardButton("SIM"), KeyboardButton("NÃO")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "12. A ferida operatória abriu? 1 ou mais pontos soltaram (arrebentaram)?",
        reply_markup=reply_markup
    )
    return PERGUNTA_12

async def pergunta_12(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['paciente'].respostas['pergunta_12'] = update.message.text.upper()
    
    keyboard = [[KeyboardButton("SIM"), KeyboardButton("NÃO")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "13. Você percebeu mal cheiro no local da ferida operatória?",
        reply_markup=reply_markup
    )
    return PERGUNTA_13

async def pergunta_13(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['paciente'].respostas['pergunta_13'] = update.message.text.upper()
    
    keyboard = [[KeyboardButton("SIM"), KeyboardButton("NÃO")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "14. Você foi para a consulta de resguardo com a enfermeira ou o médico do pré-natal?",
        reply_markup=reply_markup
    )
    return PERGUNTA_14

async def pergunta_14(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['paciente'].respostas['pergunta_14'] = update.message.text.upper()
    
    keyboard = [[KeyboardButton("SIM"), KeyboardButton("NÃO")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "15. Fez exames depois da alta hospitalar?",
        reply_markup=reply_markup
    )
    return PERGUNTA_15

async def pergunta_15(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['paciente'].respostas['pergunta_15'] = update.message.text.upper()
    
    keyboard = [[KeyboardButton("SIM"), KeyboardButton("NÃO")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "16. Necessitou ser internada novamente na maternidade?",
        reply_markup=reply_markup
    )
    return PERGUNTA_16

async def pergunta_16(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['paciente'].respostas['pergunta_16'] = update.message.text.upper()
    
    keyboard = [[KeyboardButton("SIM"), KeyboardButton("NÃO")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "17. Você saiu do hospital com dúvidas ou tem dúvidas quanto aos cuidados com a ferida operatória?",
        reply_markup=reply_markup
    )
    return PERGUNTA_17

async def pergunta_17(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['paciente'].respostas['pergunta_17'] = update.message.text.upper()
    
    # Análise dos resultados
    recomendacao = analisar_respostas(context.user_data['paciente'])
    
    # Salva os dados no CSV
    sucesso = salvar_no_csv(
        context.user_data['paciente'],
        context.user_data['paciente'].telegram_user_id,
        recomendacao
    )
    
    if sucesso:
        await update.message.reply_text(
            f"Pronto! Terminamos.\n\n{recomendacao}\n\n"
            "Agora, caso preferir, você pode anexar exames ou uma foto da sua ferida operatória.\n"
            "Muito obrigada por sua participação!",
            reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
        )
    else:
        await update.message.reply_text(
            f"Pronto! Terminamos.\n\n{recomendacao}\n\n"
            "Agora, caso preferir, você pode anexar exames ou uma foto da sua ferida operatória.\n"
            "Muito obrigada por sua participação!\n\n"
            "⚠️ Observação: Houve um problema técnico ao salvar seus dados. Por favor, entre em contato com a maternidade.",
            reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
        )
    
    # Log dos dados
    logging.info(f"Paciente: {context.user_data['paciente'].nome}")
    logging.info(f"Data parto: {context.user_data['paciente'].data_parto}")
    logging.info(f"Respostas: {context.user_data['paciente'].respostas}")
    logging.info(f"Recomendação: {recomendacao}")
    
    return ConversationHandler.END

def analisar_respostas(paciente):
    respostas = paciente.respostas
    
    # Critérios para forte suspeita de ISC (Infecção do Sítio Cirúrgico)
    criterios_isc = [
        respostas.get('pergunta_1') == 'SIM',  # Sintomas sistêmicos
        respostas.get('pergunta_2') == 'SIM',  # Sangramento persistente
        respostas.get('pergunta_8') in ['Sim, bastante vermelho', 'Está roxo'],  # Vermelhidão intensa
        respostas.get('pergunta_9') == 'SIM',  # Calor local
        respostas.get('pergunta_11') in ['Purulenta (amarela ou verde)', 'Sanguinolenta (líquido com aspecto de sangue)'],  # Secreção purulenta
        respostas.get('pergunta_12') == 'SIM',  # Ferida aberta
        respostas.get('pergunta_13') == 'SIM',  # Mal cheiro
    ]
    
    # Critério para consulta puerperal
    fez_consulta = respostas.get('pergunta_14') == 'SIM'
    
    # Se houver qualquer critério de ISC positivo
    if any(criterios_isc):
        return "Baseado em suas informações, recomendamos que retorne com urgência, à maternidade onde você pariu ou à mais próxima de sua residência."
    
    # Se não há ISC mas não fez consulta puerperal
    elif not fez_consulta:
        return "Baseado em suas informações, recomendamos que retorne à unidade de saúde onde fez seu pré-natal para consulta do puerpério ou resguardo com sua médica ou enfermeiro."
    
    # Se está internada (pergunta 16)
    elif respostas.get('pergunta_16') == 'SIM':
        return "Baseado em suas informações, verificamos que você já tem o acompanhamento de saúde necessário e desejamos uma ótima recuperação. Não esqueça de retornar à consulta na unidade de saúde onde fez o pré-natal."
    
    # Caso ideal: sem ISC e já fez consulta
    else:
        return "Baseado em suas informações, verificamos que você já tem o acompanhamento de saúde necessário e segue com ótima recuperação."

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Conversa interrompida. Se precisar reiniciar, use /start.",
        reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
    )
    return ConversationHandler.END

def main():
    # Inicializa o arquivo CSV
    inicializar_csv()
    
    # Token do bot 
    TOKEN = "8441175313:AAF3UlhGCijQwZR09aQNFuN372DMPIL4Hgs"
    
    application = Application.builder().token(TOKEN).build()

    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ACEITAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, aceitar_conversa)],
            NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, obter_nome)],
            DATA_PARTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, obter_data_parto)],
            PERGUNTA_1: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_1)],
            PERGUNTA_2: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_2)],
            PERGUNTA_3: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_3)],
            PERGUNTA_4: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_4)],
            PERGUNTA_5: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_5)],
            PERGUNTA_6: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_6)],
            PERGUNTA_7: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_7)],
            PERGUNTA_8: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_8)],
            PERGUNTA_9: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_9)],
            PERGUNTA_10: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_10)],
            PERGUNTA_11: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_11)],
            PERGUNTA_12: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_12)],
            PERGUNTA_13: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_13)],
            PERGUNTA_14: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_14)],
            PERGUNTA_15: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_15)],
            PERGUNTA_16: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_16)],
            PERGUNTA_17: [MessageHandler(filters.TEXT & ~filters.COMMAND, pergunta_17)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)

    print("Bot de monitoramento pós-cesárea está rodando...")
    print(f"Os dados serão salvos no arquivo: {CSV_FILENAME}")
    application.run_polling()

if __name__ == '__main__':
    main()
