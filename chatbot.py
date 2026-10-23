import os
import re
import json
import unicodedata
import requests
from fastapi import FastAPI, Request

# ══════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ══════════════════════════════════════════════════════════════

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8876715116:AAHovOjaM9Bri0CwPCBWAGrRvpg2eiVTW0Y")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

LM_STUDIO_URL = os.environ.get("LM_STUDIO_URL", "http://127.0.0.1:1234/v1/chat/completions")

SINTOMAS_VALIDOS = {"S1", "S2", "S3", "S_GEN"}
SINAIS_VALIDOS   = {"C1", "C2", "C3", "C4", "C5", "C6"}
SINAIS_GRAVES    = {"C1", "C5", "C6"}

PARTES_CORPO_FORA_PATTERNS = [
    r"\bjoelho\b", r"\bjoelhos\b", r"\bdente\b", r"\bdentes\b",
    r"\bouvido\b", r"\bpe\b", r"\bpes\b", r"\bbraco\b", r"\bbracos\b",
    r"\bmao\b", r"\bmaos\b", r"\bdedo\b", r"\bdedos\b",
    r"\bombro\b", r"\bombros\b", r"\bcotovelo\b", r"\bcotovelos\b",
    r"\bpunho\b", r"\bpunhos\b", r"\btornozelo\b", r"\btornozelos\b",
    r"\bcoxa\b", r"\bcoxas\b", r"\bpanturrilha\b", r"\bboca\b",
    r"\blingua\b", r"\bunha\b", r"\bunhas\b", r"\bcabelo\b",
    r"\bcabelos\b",
]

# Padrões de sintomas genéricos pós-cesárea (não mapeados em S1-S3)
SINTOMAS_GENERICOS_PATTERNS = [
    r"\btontura\b", r"\btonto\b", r"\btonteira\b", r"\bvertigem\b",
    r"\bnausea\b", r"\benjoo\b", r"\benjoada\b", r"\benjoado\b",
    r"\bvomito\b", r"\bvomitando\b", r"\bvomitei\b", r"\bvomitou\b",
    r"\bfalta de ar\b", r"\bdispneia\b",
    r"\bcansaco\b", r"\bcansada\b", r"\bcansado\b", r"\bfadiga\b",
    r"\bfraqueza\b", r"\bfraca\b", r"\bfraco\b",
    r"\bpalpitacao\b", r"\bcoracao acelerado\b",
    r"\bdesmaio\b", r"\bdesmaiei\b",
]

CONTEXTO_CESAREA = [
    "cesarea", "cesariana", "ferida", "ponto", "curativo", "cicatriz",
    "barriga", "abdome", "abdomen", "incisao", "operacao", "cirurgia",
]

OBSERVACAO_OFF_TOPIC = (
    "\n\n⚠️ Observação: o que você mencionou por último não está relacionado "
    "à cesárea, então não foi considerado na avaliação pós-operatória. Se "
    "esse sintoma persistir ou te incomodar, procure um profissional de "
    "saúde para avaliar."
)


class Etapa:
    INICIO         = "INICIO"
    CONSENTIMENTO  = "CONSENTIMENTO"
    SINTOMAS       = "SINTOMAS"
    DIAS           = "DIAS"
    SINAIS         = "SINAIS"
    EXTRAS         = "EXTRAS"
    EXTRAS_DETALHE = "EXTRAS_DETALHE"
    ENCERRADO      = "ENCERRADO"


MENSAGENS = {
    Etapa.CONSENTIMENTO: (
        "Olá! Sou o Bot Cuidar, assistente virtual de acompanhamento "
        "pós-operatório de cesárea. Posso fazer algumas perguntas sobre "
        "como você está se sentindo? (responda sim ou não)"
    ),
    Etapa.SINTOMAS: (
        "Você está sentindo algum destes sintomas? "
        "Febre, calafrio ou dor no corpo."
    ),
    Etapa.DIAS: "Há quantos dias você está sentindo isso?",
    Etapa.SINAIS: (
        "Agora sobre o local da cesárea: você notou algum destes sinais? "
        "Sangramento, secreção (líquido amarelo, esverdeado ou marrom), "
        "vermelhidão, calor no local, ponto aberto ou mal cheiro."
    ),
    Etapa.EXTRAS: "Obrigada pelas informações! Você está sentindo mais alguma coisa?",
    Etapa.EXTRAS_DETALHE: "O que você está sentindo?",
}

MENSAGENS_REPETICAO = {
    Etapa.CONSENTIMENTO: (
        "Sem problemas! Vou explicar de outra forma: eu sou o Bot Cuidar, "
        "um assistente que ajuda no acompanhamento da recuperação após "
        "cesárea. Posso fazer algumas perguntas? (responda sim ou não)"
    ),
    Etapa.SINTOMAS: (
        "Vou repetir com mais detalhes: você está sentindo algum destes "
        "sintomas?\n\n"
        "• Febre (temperatura ≥ 37,5°C)\n"
        "• Calafrio (tremedeira)\n"
        "• Dor no corpo (dores musculares)\n\n"
        "Se não sente nenhum, é só responder 'não'."
    ),
    Etapa.DIAS: (
        "Vou reformular: há quanto tempo você sente isso? "
        "(ex: '1 dia', '2 dias', 'ontem', 'hoje')"
    ),
    Etapa.SINAIS: (
        "Vou repetir com mais detalhes: você notou algum destes sinais?\n\n"
        "• Sangramento\n"
        "• Secreção (líquido amarelo, esverdeado ou marrom)\n"
        "• Vermelhidão\n"
        "• Calor no local\n"
        "• Ponto aberto\n"
        "• Mal cheiro\n\n"
        "Se não notou nenhum, é só responder 'não'."
    ),
    Etapa.EXTRAS: (
        "Vou reformular: além do que você já contou, tem mais alguma "
        "coisa incomodando? (responda sim ou não)"
    ),
    Etapa.EXTRAS_DETALHE: (
        "Pode descrever melhor? Por exemplo: 'sinto calafrio' ou "
        "'a ferida está vermelha'."
    ),
}

MENSAGEM_CEFALEIA_COSTAS = (
    "Entendi. Dor de cabeça ou nas costas no pós-cesárea merece "
    "atenção — pode estar relacionada à febre ou a outras condições "
    "que precisam de avaliação.\n\n"
    "Para eu te orientar melhor, você está sentindo algum destes "
    "sintomas?\n\n"
    "• Febre (temperatura ≥ 37,5°C)\n"
    "• Calafrio (tremedeira)\n"
    "• Dor no corpo (dores musculares)\n\n"
    "Se não sente nenhum, é só responder 'não'."
)

MENSAGENS_FORA_ESCOPO = {
    Etapa.SINTOMAS: (
        "Entendi, mas essa informação não está relacionada à recuperação "
        "da cesárea. Vou repetir focando na sua recuperação:\n\n"
        "Você está sentindo febre, calafrio ou dor no corpo "
        "(dores musculares generalizadas)?\n\n"
        "Se não sente nenhum, é só responder 'não'."
    ),
    Etapa.SINAIS: (
        "Entendi, mas essa informação não está relacionada ao local da "
        "cesárea. Vou repetir focando no local da cirurgia:\n\n"
        "Você notou, na ferida da cesárea (barriga/abdômen), algum destes "
        "sinais?\n\n"
        "• Sangramento\n• Secreção\n• Vermelhidão\n• Calor no local\n"
        "• Ponto aberto\n• Mal cheiro\n\n"
        "Se não notou nenhum, é só responder 'não'."
    ),
}

MENSAGENS_ENCERRAMENTO = {
    "BAIXO": "Obrigada por compartilhar! Seus relatos não indicam sinais de alerta no momento. Continue seguindo as orientações da equipe que acompanha sua recuperação e mantenha os cuidados com a ferida. Se algo mudar, procure atendimento. Cuide-se bem!",
    "MEDIO": "Obrigada pelas informações! Alguns dos sinais/sintomas que você relatou merecem atenção. Recomendo entrar em contato com sua equipe médica ou de enfermagem nas próximas 24 horas para uma avaliação. Se piorar, procure atendimento imediatamente. Cuide-se bem!",
    "ALTO": "Obrigada por compartilhar! Os sintomas e sinais que você relatou indicam necessidade de avaliação médica o quanto antes. Por favor, procure sua equipe de saúde ou um pronto atendimento AGORA. Se houver sangramento intenso, febre alta persistente, falta de ar ou desmaio, chame ajuda imediatamente. Cuide-se bem!",
    "INDEFINIDO": "Obrigada pelo relato! Não consegui identificar com clareza o que você está sentindo. Por segurança, recomendo conversar com sua equipe médica ou de enfermagem. Cuide-se bem!"
}


# ══════════════════════════════════════════════════════════════
# AUXILIARES
# ══════════════════════════════════════════════════════════════

def novo_estado():
    return {
        "etapa": Etapa.INICIO,
        "consentimento": None,
        "sintomas": [],
        "dias": None,
        "sinais": [],
        "extras": [],
        "extras_off_topic": [],
        "risco": None,
        "confusoes": 0,
    }


def remover_acentos(texto):
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )


def detecta_sintoma_generico(texto):
    """Detecta sintomas comuns pós-cesárea fora dos códigos S1-S3."""
    t = remover_acentos(texto.lower())
    return any(re.search(p, t) for p in SINTOMAS_GENERICOS_PATTERNS)


def eh_confusao(texto):
    t = remover_acentos(texto.lower().strip())
    frases = [
        "nao entendi", "nao compreendi", "nao entendi nada",
        "nao ficou claro", "como assim", "o que voce quis dizer",
        "o que significa", "nao sei do que voce esta falando",
        "nao sei o que responder", "nao sei responder",
        "nao sei dizer", "me explica", "explica melhor",
        "pode explicar", "pode repetir", "repete", "repita",
    ]
    for f in frases:
        if f in t:
            return True
    if t in ["?", "??", "???", "que", "como", "oi?", "e?", "ha", "hein", "huh"]:
        return True
    return False


def eh_nao_sei(texto):
    t = remover_acentos(texto.lower().strip())
    frases = [
        "nao sei", "nao sei dizer", "nao tenho certeza",
        "nao sei informar", "nao lembro", "sei la", "nao sei bem",
        "nao sei te dizer", "nao tenho como saber", "nao faco ideia",
        "nao tenho ideia",
    ]
    return any(f in t for f in frases)


def menciona_cefaleia_ou_costas(texto):
    t = remover_acentos(texto.lower())
    return any(x in t for x in
               ["cabeca", "costas", "lombar", "nuca", "migranea", "enxaqueca"])


def eh_fora_do_escopo(texto):
    t = remover_acentos(texto.lower())
    if any(c in t for c in CONTEXTO_CESAREA):
        return False
    for pattern in PARTES_CORPO_FORA_PATTERNS:
        if re.search(pattern, t):
            return True
    return False


def eh_negacao_simples(texto):
    t = remover_acentos(texto.lower().strip())
    t = re.sub(r'[,.!?;]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    negacoes = {
        "nao", "n", "nenhum", "nenhuma", "nada",
        "nao nada", "nao nenhum", "nao nenhuma",
        "nao obrigada", "nada nao",
    }
    return t in negacoes


def quer_reiniciar(texto, etapa_atual):
    t = remover_acentos(texto.lower().strip())
    if t in ["/start", "/reset", "/reiniciar", "/recomecar", "/menu", "/novo"]:
        return True
    if etapa_atual == Etapa.ENCERRADO:
        palavras = ["reiniciar", "recomecar", "reset", "novo", "novo teste",
                    "de novo", "tentar de novo", "tentar novamente", "menu",
                    "iniciar", "comecar"]
        if t in palavras:
            return True
    return False


# ══════════════════════════════════════════════════════════════
# LLM
# ══════════════════════════════════════════════════════════════

def chamar_llm(messages, force_json=False, max_tokens=400):
    payload = {"messages": messages, "temperature": 0, "max_tokens": max_tokens}
    if force_json:
        payload["response_format"] = {"type": "json_object"}
    try:
        r = requests.post(LM_STUDIO_URL, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[ERRO LLM] {e}")
        return ""


# ══════════════════════════════════════════════════════════════
# FALLBACK POR PALAVRAS-CHAVE
# ══════════════════════════════════════════════════════════════

def _fallback_sintomas(texto):
    t = texto.lower()
    if any(n in t for n in ["não sinto nada", "nao sinto nada",
                            "não tenho nada", "nao tenho nada",
                            "nenhum sintoma", "sem sintoma"]):
        return ["NENHUM_SINTOMA"]

    codigos = []
    tem_febre = any(x in t for x in ["febre", "temperatura", "38 graus",
                                      "39 graus", "40 graus"])
    neg_febre = any(x in t for x in ["não tenho febre", "nao tenho febre",
                                      "sem febre", "não estou com febre",
                                      "nao estou com febre", "não sinto febre",
                                      "nao sinto febre"])
    if tem_febre and not neg_febre:
        codigos.append("S1")

    tem_cal = any(x in t for x in ["calafrio", "tremendo", "tremedeira",
                                    "tremor", "me tremendo"])
    neg_cal = any(x in t for x in ["não tenho calafrio", "nao tenho calafrio",
                                    "sem calafrio", "não estou tremendo",
                                    "nao estou tremendo"])
    if tem_cal and not neg_cal:
        codigos.append("S2")

    tem_dor = any(x in t for x in ["dor no corpo", "dói tudo", "doi tudo",
                                    "corpo dolorido", "corpo doído", "mialgia",
                                    "dores no corpo"])
    neg_dor = any(x in t for x in ["não tenho dor", "nao tenho dor", "sem dor",
                                    "não sinto dor", "nao sinto dor"])
    if tem_dor and not neg_dor:
        codigos.append("S3")

    # Sintomas genéricos (tontura, náusea, falta de ar, etc.)
    if detecta_sintoma_generico(texto):
        codigos.append("S_GEN")

    if codigos:
        return codigos

    if any(n in t for n in ["não sinto", "nao sinto", "não tenho", "nao tenho",
                            "estou bem", "tô bem", "to bem", "tudo normal",
                            "tudo bem", "nada disso"]):
        return ["NENHUM_SINTOMA"]

    return ["INDEFINIDO"]


def _fallback_sinais(texto):
    t = texto.lower()
    if any(n in t for n in ["não noto nada", "nao noto nada", "não vi nada",
                            "nao vi nada", "nenhum sinal", "sem sinal",
                            "tá normal", "ta normal", "não tem nada",
                            "nao tem nada", "está tudo normal",
                            "esta tudo normal"]):
        return ["NENHUM_SINAL"]

    codigos = []

    tem_sang = any(x in t for x in ["sangue", "sangrando", "sangramento",
                                     "sangrou", "saiu sangue"])
    neg_sang = any(x in t for x in ["sem sangue", "não tem sangue",
                                     "nao tem sangue", "não está sangrando",
                                     "nao esta sangrando", "parou de sangrar",
                                     "não sangra", "nao sangra"])
    if tem_sang and not neg_sang:
        codigos.append("C1")

    tem_secr = any(x in t for x in ["pus", "secre", "líquido amarelo",
                                     "liquido amarelo", "esverdeado",
                                     "corrimento", "saindo líquido"])
    neg_secr = any(x in t for x in ["sem secreção", "sem secrecao",
                                     "não tem pus", "nao tem pus",
                                     "não tem secreção", "nao tem secrecao",
                                     "não sai líquido"])
    if tem_secr and not neg_secr:
        codigos.append("C2")

    tem_verm = any(x in t for x in ["vermelh", "inflamad", "inflamação",
                                     "inflamacao", "avermelh"])
    neg_verm = any(x in t for x in ["não está vermelho", "nao esta vermelho",
                                     "não tem vermelhidão", "sem vermelhidão",
                                     "sem vermelhidao", "não está inflamado",
                                     "nao esta inflamado"])
    if tem_verm and not neg_verm:
        codigos.append("C3")

    tem_calor = any(x in t for x in ["local quente", "ferida quente",
                                      "tá quente", "ta quente", "calor no local",
                                      "esquentou", "está quente", "esta quente"])
    neg_calor = any(x in t for x in ["não está quente", "nao esta quente",
                                      "não tem calor", "nao tem calor"])
    if tem_calor and not neg_calor:
        codigos.append("C4")

    tem_abr = any(x in t for x in ["abriu", "aberto", "rasgou", "rompeu",
                                    "ponto abriu", "ferida abriu"])
    neg_abr = any(x in t for x in ["não abriu", "nao abriu",
                                    "não está aberto", "nao esta aberto"])
    if tem_abr and not neg_abr:
        codigos.append("C5")

    tem_cheiro = any(x in t for x in ["cheiro ruim", "mal cheiro", "mau odor",
                                       "odor ruim", "fedor", "fede",
                                       "cheirando mal"])
    neg_cheiro = any(x in t for x in ["não tem cheiro", "nao tem cheiro",
                                       "sem cheiro", "sem odor",
                                       "não tem odor"])
    if tem_cheiro and not neg_cheiro:
        codigos.append("C6")

    if codigos:
        return codigos

    if any(n in t for n in ["não noto", "nao noto", "não vi", "nao vi"]):
        return ["NENHUM_SINAL"]

    return ["INDEFINIDO"]


# ══════════════════════════════════════════════════════════════
# PARSERS
# ══════════════════════════════════════════════════════════════

def parse_consentimento(texto):
    t = texto.lower().strip()
    if t in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite",
             "e aí", "eai", "e ai", "hey", "hello"]:
        return "SAUDACAO"

    for neg in ["não", "nao", "n", "negativo", "prefiro não", "agora não",
                "deixa", "dispenso", "não quero", "nao quero"]:
        if t == neg or t.startswith(neg + " ") or t.startswith(neg + ","):
            return False
    for af in ["sim", "s", "claro", "pode", "ok", "tá bom", "ta bom",
               "positivo", "com certeza", "manda", "bora", "vamos",
               "aceito", "quero", "yes", "yep"]:
        if t == af or t.startswith(af + " ") or t.startswith(af + ","):
            return True

    resp = chamar_llm([
        {"role": "system", "content":
            "Classifique em SIM, NAO, SAUDACAO ou CONFUSAO.\n\n"
            "Exemplos:\n- 'sim' → SIM\n- 'claro, pode' → SIM\n"
            "- 'tá bom' → SIM\n- 'não' → NAO\n- 'prefiro não' → NAO\n"
            "- 'oi' → SAUDACAO\n- 'bom dia' → SAUDACAO\n"
            "- 'não entendi' → CONFUSAO\n- 'como assim?' → CONFUSAO\n\n"
            "Responda APENAS: SIM, NAO, SAUDACAO ou CONFUSAO."},
        {"role": "user", "content": texto}
    ])
    ru = resp.upper()
    if "CONFUSAO" in ru: return "CONFUSAO"
    if "SAUDACAO" in ru: return "SAUDACAO"
    if "SIM" in ru: return True
    if "NAO" in ru or "NÃO" in ru: return False
    return None


def parse_sintomas(texto):
    if eh_negacao_simples(texto):
        print(f"[SINTOMAS] negação simples: '{texto}' → NENHUM_SINTOMA")
        return ["NENHUM_SINTOMA"]

    prompt = f"""Extraia APENAS os sintomas gerais relacionados à recuperação
pós-cesárea mencionados pela paciente.

Códigos:
S1 = Febre (temperatura alta, "tô quente", "38 graus")
S2 = Calafrio (tremedeira, tremendo, muito frio)
S3 = Dor no corpo (dói tudo, corpo dolorido, dores musculares generalizadas)
S_GEN = Outros sintomas (tontura, náusea, vômito, falta de ar, cansaço,
        fraqueza, palpitação, desmaio)

IMPORTANTE:
- "um pouco de X", "só um pouco de X", "leve X", "X baixa" INDICAM que a paciente TEM o sintoma X.
- Sintomas em OUTRAS partes do corpo (dor no joelho, dor de dente, 
  dor no braço) NÃO devem ser considerados.
- EXCEÇÃO: dor de cabeça e dor nas costas PODEM estar relacionadas ao 
  pós-cesárea. Se acompanhadas de febre, extraia S1. Se isoladas, 
  retorne ["INDEFINIDO"] para que o bot peça mais informações.
- Se a paciente só relatar sintomas fora do contexto → ["INDEFINIDO"]

Regras:
- Se disser que NÃO sente nada ou está bem → ["NENHUM_SINTOMA"]
- Se for vago/incompreensível → ["INDEFINIDO"]
- Se listar algum sintoma geral → JSON puro com os códigos

Exemplos:
- "estou com febre e dor no corpo" → ["S1","S3"]
- "só calafrio" → ["S2"]
- "não sinto nada" → ["NENHUM_SINTOMA"]
- "estou bem, obrigada" → ["NENHUM_SINTOMA"]
- "um pouco de febre" → ["S1"]
- "só um pouco de dor no corpo" → ["S3"]
- "leve febre" → ["S1"]
- "tô com uma febrinha" → ["S1"]
- "não tenho febre" → ["NENHUM_SINTOMA"]
- "sinto tontura" → ["S_GEN"]
- "tô com náusea" → ["S_GEN"]
- "estou com falta de ar" → ["S_GEN"]
- "cansaço e fraqueza" → ["S_GEN"]
- "tontura e febre" → ["S1","S_GEN"]
- "dor no joelho quando me abaixo" → ["INDEFINIDO"]
- "dor de dente" → ["INDEFINIDO"]
- "meu braço tá doendo" → ["INDEFINIDO"]
- "dor de cabeça e febre" → ["S1"]
- "dor de cabeça" → ["INDEFINIDO"]
- "dor nas costas desde a cesárea" → ["INDEFINIDO"]
- "estou com febre e dor no joelho" → ["S1"]
- "me sinto estranha" → ["INDEFINIDO"]
- "não sei" → ["INDEFINIDO"]

Mensagem da paciente: "{texto}"

Responda APENAS o JSON."""
    resp = chamar_llm([{"role": "user", "content": prompt}], force_json=True)
    try:
        codigos = json.loads(resp)
        if not isinstance(codigos, list) or not codigos:
            print(f"[SINTOMAS] JSON vazio → fallback")
            return _fallback_sintomas(texto)
        if "NENHUM_SINTOMA" in codigos:
            fb = _fallback_sintomas(texto)
            fb_pos = [c for c in fb if c.startswith("S") and c != "NENHUM_SINTOMA"]
            if fb_pos:
                print(f"[SINTOMAS] LLM disse NENHUM, mas fallback detectou {fb_pos} — usando fallback")
                return fb_pos
            return ["NENHUM_SINTOMA"]
        if "INDEFINIDO" in codigos:
            print(f"[SINTOMAS] LLM disse INDEFINIDO → fallback")
            return _fallback_sintomas(texto)
        validos = [c for c in codigos if c in SINTOMAS_VALIDOS]
        if not validos:
            print(f"[SINTOMAS] JSON sem códigos válidos → fallback")
            return _fallback_sintomas(texto)
        print(f"[SINTOMAS] LLM detectou: {validos}")
        return validos
    except json.JSONDecodeError:
        print(f"[SINTOMAS] JSON inválido → fallback")
        return _fallback_sintomas(texto)


def parse_dias(texto):
    t = texto.lower().strip()
    m = re.search(r'\d+', t)
    if m: return int(m.group())
    numeros = {"um":1,"uma":1,"dois":2,"duas":2,"três":3,"tres":3,"quatro":4,
               "cinco":5,"seis":6,"sete":7,"oito":8,"nove":9,"dez":10,
               "ontem":1,"hoje":0,"anteontem":2}
    for palavra, num in numeros.items():
        if palavra in t: return num
    return None


def parse_sinais(texto):
    if eh_negacao_simples(texto):
        print(f"[SINAIS] negação simples: '{texto}' → NENHUM_SINAL")
        return ["NENHUM_SINAL"]

    prompt = f"""Extraia APENAS os sinais no LOCAL DA CESÁREA (barriga/abdômen/ferida).

Códigos:
C1 = Sangramento (sangue, sangrando)
C2 = Secreção (pus, líquido amarelo/esverdeado/marrom)
C3 = Vermelhidão (vermelho, inflamado)
C4 = Calor local (local quente ao toque)
C5 = Ponto aberto (abriu, rompeu, rasgou)
C6 = Mal cheiro (cheiro ruim, odor, fedor)

IMPORTANTE:
- "um pouco de X", "só um pouco de X", "leve X" INDICAM que a paciente TEM o sinal X.
- Sinais em OUTRAS partes do corpo (vermelhidão no braço, pus no pé, 
  coceira no joelho) NÃO devem ser considerados.
- Se a paciente só relatar sinais fora do contexto → ["INDEFINIDO"]

Regras:
- Se disser que NÃO notou nada → ["NENHUM_SINAL"]
- Se for vago → ["INDEFINIDO"]
- Se listar → JSON puro com os códigos

Exemplos:
- "o ponto está sangrando" → ["C1"]
- "sai pus do curativo" → ["C2"]
- "tá vermelho e quente" → ["C3","C4"]
- "o ponto abriu" → ["C5"]
- "tem cheiro ruim na ferida" → ["C6"]
- "um pouco de pus" → ["C2"]
- "levemente vermelho na cicatriz" → ["C3"]
- "não noto nada" → ["NENHUM_SINAL"]
- "tá tudo normal" → ["NENHUM_SINAL"]
- "meu braço tá vermelho" → ["INDEFINIDO"]
- "o pé tá com pus" → ["INDEFINIDO"]
- "a cicatriz tá vermelha e o braço também" → ["C3"]
- "não sei" → ["INDEFINIDO"]

Mensagem da paciente: "{texto}"

Responda APENAS o JSON."""
    resp = chamar_llm([{"role": "user", "content": prompt}], force_json=True)
    try:
        codigos = json.loads(resp)
        if not isinstance(codigos, list) or not codigos:
            print(f"[SINAIS] JSON vazio → fallback")
            return _fallback_sinais(texto)
        if "NENHUM_SINAL" in codigos:
            fb = _fallback_sinais(texto)
            fb_pos = [c for c in fb if c.startswith("C")]
            if fb_pos:
                print(f"[SINAIS] LLM disse NENHUM, mas fallback detectou {fb_pos} — usando fallback")
                return fb_pos
            return ["NENHUM_SINAL"]
        if "INDEFINIDO" in codigos:
            print(f"[SINAIS] LLM disse INDEFINIDO → fallback")
            return _fallback_sinais(texto)
        validos = [c for c in codigos if c in SINAIS_VALIDOS]
        if not validos:
            print(f"[SINAIS] JSON sem códigos válidos → fallback")
            return _fallback_sinais(texto)
        print(f"[SINAIS] LLM detectou: {validos}")
        return validos
    except json.JSONDecodeError:
        print(f"[SINAIS] JSON inválido → fallback")
        return _fallback_sinais(texto)


def parse_extras(texto):
    t = texto.lower().strip()

    if t in ["sim", "s", "positivo", "yes", "aham", "uhum"]:
        return ("APENAS_SIM", [])

    if t in ["não", "nao", "n", "negativo", "nenhum", "nada"] \
       or t.startswith("não ") or t.startswith("nao "):
        return ("NAO", [])
    if eh_nao_sei(texto):
        return ("NAO", [])

    prompt = f"""A paciente foi questionada se sente MAIS alguma coisa e disse:
"{texto}"

Extraia APENAS sintomas gerais (S) e sinais no local da cesárea (C).

Sintomas: S1=Febre, S2=Calafrio, S3=Dor no corpo,
          S_GEN=Outros (tontura, náusea, vômito, falta de ar, cansaço,
          fraqueza, palpitação, desmaio)
Sinais: C1=Sangramento, C2=Secreção, C3=Vermelhidão,
        C4=Calor local, C5=Ponto aberto, C6=Mal cheiro

IMPORTANTE: sintomas/sinais em outras partes do corpo (joelho, dente,
braço) NÃO devem ser considerados. Exceção: dor de cabeça com febre 
conta como S1.

Exemplos:
- "não" → {{"itens": []}}
- "sim, sinto calafrio e febre" → {{"itens": ["S1","S2"]}}
- "sim, tem pus saindo do ponto" → {{"itens": ["C2"]}}
- "tô com dor no corpo e o ponto tá vermelho" → {{"itens": ["S3","C3"]}}
- "um pouco de febre" → {{"itens": ["S1"]}}
- "sinto tontura" → {{"itens": ["S_GEN"]}}
- "tô com náusea" → {{"itens": ["S_GEN"]}}
- "falta de ar" → {{"itens": ["S_GEN"]}}
- "cansaço e febre" → {{"itens": ["S1","S_GEN"]}}
- "estou com dor no joelho" → {{"itens": []}}
- "sim, dor de dente" → {{"itens": []}}
- "meu braço tá com pus" → {{"itens": []}}
- "sim, dor de cabeça e febre" → {{"itens": ["S1"]}}
- "sim" → {{"itens": []}}

Responda APENAS o JSON no formato {{"itens": [...]}}."""
    resp = chamar_llm([{"role": "user", "content": prompt}], force_json=True)

    itens = []
    try:
        dados = json.loads(resp)
        itens = dados.get("itens", []) or []
    except (json.JSONDecodeError, AttributeError):
        print(f"[EXTRAS] JSON inválido → fallback")

    if not itens:
        itens = [c for c in _fallback_sintomas(texto) if c.startswith("S") and c != "NENHUM_SINTOMA"]
        itens.extend([c for c in _fallback_sinais(texto) if c.startswith("C") and c != "NENHUM_SINAL"])

    if itens:
        print(f"[EXTRAS] detectou: {itens}")
        return ("DETALHE", itens)

    if eh_fora_do_escopo(texto):
        print(f"[EXTRAS] OFF_TOPIC detectado: '{texto}'")
        return ("OFF_TOPIC", [])

    return ("APENAS_SIM", [])


# ══════════════════════════════════════════════════════════════
# CLASSIFICAÇÃO DE RISCO
# ══════════════════════════════════════════════════════════════

def classificar_risco(estado):
    sintomas, sinais = [], []
    if estado["sintomas"] not in (["NENHUM_SINTOMA"], ["INDEFINIDO"], []):
        sintomas.extend(estado["sintomas"])
    if estado["sinais"] not in (["NENHUM_SINAL"], ["INDEFINIDO"], []):
        sinais.extend(estado["sinais"])
    for item in estado["extras"]:
        if item.startswith("S"): sintomas.append(item)
        elif item.startswith("C"): sinais.append(item)

    n_s = len(set(sintomas))
    n_c = len(set(sinais))
    total = n_s + n_c
    d = estado["dias"] if estado["dias"] is not None else 0
    tem_grave = any(s in SINAIS_GRAVES for s in sinais)

    print(f"[RISCO] S={sorted(set(sintomas))} C={sorted(set(sinais))} "
          f"n_s={n_s} n_c={n_c} total={total} dias={d} grave={tem_grave}")

    if total == 0:
        print("[RISCO] Regra 1 (nada) → BAIXO"); return "BAIXO"
    if tem_grave:
        print("[RISCO] Regra 2 (sinal grave) → ALTO"); return "ALTO"
    if total >= 3:
        print("[RISCO] Regra 3 (3+ itens) → ALTO"); return "ALTO"
    if total == 2:
        if d >= 2:
            print("[RISCO] Regra 4a (2 itens persistentes) → ALTO"); return "ALTO"
        print("[RISCO] Regra 4b (2 itens, 1 dia) → MEDIO"); return "MEDIO"
    if d >= 2:
        print("[RISCO] Regra 5a (1 item persistente) → MEDIO"); return "MEDIO"
    print("[RISCO] Regra 5b (1 item isolado) → BAIXO"); return "BAIXO"


# ══════════════════════════════════════════════════════════════
# MÁQUINA DE ESTADOS
# ══════════════════════════════════════════════════════════════

def _finalizar(estado):
    risco = classificar_risco(estado)
    estado["risco"] = risco
    estado["etapa"] = Etapa.ENCERRADO

    off_topic = estado.get("extras_off_topic", [])

    if risco == "BAIXO" and off_topic:
        msg = (
            "Obrigada por compartilhar! Sobre a recuperação da cesárea, "
            "seus relatos não indicam sinais de alerta no momento. Continue "
            "seguindo as orientações da equipe que acompanha sua recuperação "
            "e mantenha os cuidados com a ferida." + OBSERVACAO_OFF_TOPIC
        )
    else:
        msg = MENSAGENS_ENCERRAMENTO.get(risco, MENSAGENS_ENCERRAMENTO["INDEFINIDO"])
        if off_topic:
            msg += OBSERVACAO_OFF_TOPIC

    print(f"[FINALIZADO] risco={risco} off_topic={bool(off_topic)}")
    return msg, estado


def processar_mensagem(numero, texto, estado):
    etapa = estado["etapa"]
    t = texto.lower().strip()

    if etapa not in (Etapa.INICIO, Etapa.ENCERRADO) and eh_confusao(texto):
        estado["confusoes"] = estado.get("confusoes", 0) + 1
        print(f"[CONFUSAO] etapa={etapa} tentativa={estado['confusoes']}")
        if estado["confusoes"] >= 3:
            return (
                "Vejo que está difícil prosseguir. Se quiser, podemos "
                "recomeçar do zero — envie /start.\n\n" +
                MENSAGENS_REPETICAO.get(etapa, "Pode me contar novamente?")
            ), estado
        return MENSAGENS_REPETICAO.get(etapa, "Pode me contar novamente?"), estado

    estado["confusoes"] = 0

    if etapa == Etapa.INICIO:
        estado["etapa"] = Etapa.CONSENTIMENTO
        return MENSAGENS[Etapa.CONSENTIMENTO], estado

    if etapa == Etapa.CONSENTIMENTO:
        consent = parse_consentimento(texto)
        estado["consentimento"] = consent
        if consent == "CONFUSAO":
            return MENSAGENS_REPETICAO[Etapa.CONSENTIMENTO], estado
        if consent == "SAUDACAO":
            return (
                "Olá! Que bom falar com você. Para começarmos, posso fazer "
                "algumas perguntas sobre como você está se sentindo? "
                "(responda sim ou não)"
            ), estado
        if consent is False:
            estado["etapa"] = Etapa.ENCERRADO
            return (
                "Entendo sua decisão e respeito. Mesmo assim, recomendo "
                "fortemente que você continue o acompanhamento com sua equipe "
                "médica ou de enfermagem. Se surgir qualquer sintoma "
                "preocupante, procure atendimento. Cuide-se bem!\n\n"
                " Para fazer um novo teste, envie /start."
            ), estado
        if consent is True:
            estado["etapa"] = Etapa.SINTOMAS
            return MENSAGENS[Etapa.SINTOMAS], estado
        return (
            "Desculpe, não entendi. Podemos prosseguir com algumas perguntas? "
            "Responda sim ou não."
        ), estado

    if etapa == Etapa.SINTOMAS:
        if t in ["sim", "s", "positivo", "yes", "aham", "uhum"]:
            return (
                "Quais sintomas você está sentindo? "
                "(febre, calafrio ou dor no corpo)"
            ), estado
        sintomas = parse_sintomas(texto)

        if sintomas == ["INDEFINIDO"]:
            if eh_nao_sei(texto):
                print("[SINTOMAS] 'não sei' → tratando como NENHUM_SINTOMA")
                estado["sintomas"] = ["NENHUM_SINTOMA"]
                estado["etapa"] = Etapa.SINAIS
                return (
                    "Tudo bem não ter certeza! Vou seguir com as próximas "
                    "perguntas.\n\n" + MENSAGENS[Etapa.SINAIS]
                ), estado

            if menciona_cefaleia_ou_costas(texto):
                print("[SINTOMAS] cefaleia/lombalgia detectada")
                return MENSAGEM_CEFALEIA_COSTAS, estado

            if eh_fora_do_escopo(texto):
                print("[SINTOMAS] FORA_DO_ESCOPO detectado")
                return MENSAGENS_FORA_ESCOPO[Etapa.SINTOMAS], estado

            print("[SINTOMAS] INDEFINIDO — repetindo pergunta")
            return MENSAGENS_REPETICAO[Etapa.SINTOMAS], estado

        estado["sintomas"] = sintomas
        if sintomas == ["NENHUM_SINTOMA"]:
            estado["etapa"] = Etapa.SINAIS
            return MENSAGENS[Etapa.SINAIS], estado
        estado["etapa"] = Etapa.DIAS
        return MENSAGENS[Etapa.DIAS], estado

    if etapa == Etapa.DIAS:
        if eh_nao_sei(texto):
            print("[DIAS] 'não sei' → dias=None, avançando")
            estado["dias"] = None
            estado["etapa"] = Etapa.SINAIS
            return (
                "Tudo bem! Vou seguir sem essa informação. Se lembrar "
                "depois, é só me avisar.\n\n" + MENSAGENS[Etapa.SINAIS]
            ), estado
        estado["dias"] = parse_dias(texto)
        estado["etapa"] = Etapa.SINAIS
        return MENSAGENS[Etapa.SINAIS], estado

    if etapa == Etapa.SINAIS:
        if t in ["sim", "s", "positivo", "yes", "aham", "uhum"]:
            return (
                "Quais sinais você notou? "
                "(sangramento, secreção, vermelhidão, calor no local, "
                "ponto aberto ou mal cheiro)"
            ), estado
        sinais = parse_sinais(texto)

        if sinais == ["INDEFINIDO"]:
            if eh_nao_sei(texto):
                print("[SINAIS] 'não sei' → tratando como NENHUM_SINAL")
                estado["sinais"] = ["NENHUM_SINAL"]
                estado["etapa"] = Etapa.EXTRAS
                return (
                    "Tudo bem não ter certeza! Vou seguir com as próximas "
                    "perguntas.\n\n" + MENSAGENS[Etapa.EXTRAS]
                ), estado

            if eh_fora_do_escopo(texto):
                print("[SINAIS] FORA_DO_ESCOPO detectado")
                return MENSAGENS_FORA_ESCOPO[Etapa.SINAIS], estado

            print("[SINAIS] INDEFINIDO — repetindo pergunta")
            return (
                "Desculpe, não consegui entender. Você notou algum destes "
                "sinais: sangramento, secreção, vermelhidão, calor no local, "
                "ponto aberto ou mal cheiro? "
                "(se não notou nenhum, responda 'não')"
            ), estado

        estado["sinais"] = sinais
        estado["etapa"] = Etapa.EXTRAS
        return MENSAGENS[Etapa.EXTRAS], estado

    if etapa == Etapa.EXTRAS:
        tipo, itens = parse_extras(texto)
        if tipo == "NAO":
            estado["extras"] = []
            estado["extras_off_topic"] = []
            return _finalizar(estado)
        if tipo == "OFF_TOPIC":
            estado["extras"] = []
            estado["extras_off_topic"] = [texto]
            return _finalizar(estado)
        if tipo == "APENAS_SIM":
            estado["etapa"] = Etapa.EXTRAS_DETALHE
            return MENSAGENS[Etapa.EXTRAS_DETALHE], estado
        if tipo == "DETALHE":
            estado["extras"] = itens
            estado["extras_off_topic"] = []
            return _finalizar(estado)

    if etapa == Etapa.EXTRAS_DETALHE:
        tipo, itens = parse_extras(texto)
        if tipo == "DETALHE":
            estado["extras"] = itens
            estado["extras_off_topic"] = []
        elif tipo == "OFF_TOPIC":
            estado["extras"] = []
            estado["extras_off_topic"] = [texto]
        else:
            estado["extras"] = []
            estado["extras_off_topic"] = []
        return _finalizar(estado)

    if etapa == Etapa.ENCERRADO:
        return (
            "Esta conversa já foi encerrada. Se precisar de algo, procure "
            "sua equipe médica ou de enfermagem. Cuide-se bem!\n\n"
            "💡 Para fazer um novo teste, envie /start."
        ), estado

    return "Desculpe, algo deu errado. Pode repetir?", estado


# ══════════════════════════════════════════════════════════════
# FASTAPI
# ══════════════════════════════════════════════════════════════

app = FastAPI(title="Bot Cuidar — Telegram")
conversas = {}


def enviar_telegram(chat_id, texto):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {"chat_id": chat_id, "text": texto}
    try:
        r = requests.post(url, json=payload, timeout=15)
        print(f"[TELEGRAM ENVIO] status={r.status_code} resp={r.text[:300]}")
    except Exception as e:
        print(f"[ERRO TELEGRAM] {e}")


@app.post("/telegram")
async def telegram_webhook(request: Request):
    data = await request.json()
    message = data.get("message")
    if not message or "text" not in message:
        return {"status": "ignored"}

    chat_id = message["chat"]["id"]
    texto = message["text"].strip()

    is_first = chat_id not in conversas
    if is_first:
        conversas[chat_id] = novo_estado()

    if quer_reiniciar(texto, conversas[chat_id]["etapa"]):
        avisar = not (is_first and conversas[chat_id]["etapa"] == Etapa.INICIO)
        conversas[chat_id] = novo_estado()
        estado = conversas[chat_id]
        resposta, estado = processar_mensagem(chat_id, "", estado)
        conversas[chat_id] = estado
        print(f"[{chat_id}] REINICIADO → etapa={estado['etapa']}")
        if avisar:
            enviar_telegram(chat_id, " Conversa reiniciada.\n\n" + resposta)
        else:
            enviar_telegram(chat_id, resposta)
        return {"status": "ok"}

    estado = conversas[chat_id]
    resposta, estado = processar_mensagem(chat_id, texto, estado)
    conversas[chat_id] = estado
    print(f"[{chat_id}] etapa={estado['etapa']} risco={estado['risco']}")
    enviar_telegram(chat_id, resposta)
    return {"status": "ok"}


@app.get("/")
async def raiz():
    return {"status": "ok", "bot": "Bot Cuidar — Telegram"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
