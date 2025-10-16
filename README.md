# PIBIC-2025
DESENVOLVIMENTO DE FERRAMENTA DE VIGILÂNCIA PÓS-ALTA DAS INFECÇÕES DE SÍTIO CIRÚRGICO DE CESARIANAS USANDO CHATBOT INTELIGENTE

# Chatbot de Monitoramento Pós-Cesariana

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://python.org)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)](https://telegram.org)

Um chatbot inteligente para o Telegram que realiza busca ativa e monitoramento de pacientes no pós-operatório de cesariana, identificando sinais de Infecção do Sítio Cirúrgico (ISC) e fornecendo recomendações personalizadas.

##  Sobre o Projeto

Este é um projeto de PIBIC que está sendo desenvolvido para maternidades e serviços de saúde, permitindo o acompanhamento remoto de pacientes no puerpério através de um questionário estruturado que:

-  **Identifica sinais de complicações** pós-cirúrgicas
-  **Classifica o risco** baseado em critérios clínicos
-  **Fornece recomendações** personalizadas para cada caso
-  **Armazena dados** para acompanhamento (em desenvolvimento)

##  Funcionalidades

- **Questionário**: 17 perguntas baseadas em protocolos clínicos
- **Interface**: Teclados personalizados para respostas rápidas
- **Algoritmo**: Análise automática para detecção de ISC
- **4 Tipos de Recomendações**:
  - Retorno urgente à maternidade
  - Consulta de rotina no puerpério
  - Acompanhamento em andamento
  - Recuperação adequada

##Tecnologias Utilizadas

- **Python 3.8+**
- **python-telegram-bot** - Framework para bots do Telegram
- **Logging** - Registro de atividades e dados
- **Asyncio** - Programação assíncrona

##Instalação

### Pré-requisitos

- Python 3.8 ou superior
- Conta no Telegram
- Token de bot do Telegram (obtido via [@BotFather](https://t.me/BotFather))

### Passo a Passo

1. **Clone o repositório**
   ```bash
   git clone https://github.com/beatrizmartins123/PIBIC-2025.git
   cd chatbot-cesariana
