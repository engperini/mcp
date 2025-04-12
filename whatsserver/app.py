import os
import json
import requests
import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, redirect, url_for
from openai import OpenAI

import asyncio

import time
from agents import Agent, Runner, gen_trace_id, trace, WebSearchTool
from agents.model_settings import ModelSettings
from agents.mcp import MCPServerStdio
import os
 
load_dotenv()
client = OpenAI()

server_params = {
    "command": "python",
    "args": ["/home/pi/mcp/whatsserver/server.py"],
    "env": os.environ.copy(),
}

app = Flask(__name__)

# Arquivos de configuração e log unificado
ALLOWED_CONTACTS_FILE = "allowed_contacts.txt"
MESSAGES_LOG_FILE = "messages.log"  # Unifica mensagens recebidas e respostas (JSON line)
CONFIG_FILE = "config.txt"

conversation_history = {}
async def process_llm(chat_id, user_message):
    
    async with MCPServerStdio(params=server_params) as mcp_server:
        # Atualiza o histórico da conversa para esse chat
        if chat_id not in conversation_history:
            conversation_history[chat_id] = []
        conversation_history[chat_id].append(("User", user_message))
        
        # Define as instruções usando as últimas 3 interações (ou toda a história, se preferir)
        instructions = "Você é um assistente chatbot útil, use ferramentas para informacoes atualizadas quando necessario. Histórico:\n" + "\n".join(
            
            
            f"{role}: {msg}" for role, msg in conversation_history[chat_id][-3:]
        )
        
        # Instancia o agente
        agent = Agent(
            name="Assistant",
            instructions=instructions,
            model="gpt-4o-mini",
            tools=[WebSearchTool()],
            mcp_servers=[mcp_server],  # Se não for necessário usar um subprocesso com MCPServerStdio, deixe vazio
            model_settings=ModelSettings(tool_choice="auto"),
        )
        
        # Processa a query com o agente (usando trace para log, se desejar)
        with trace("Agent interaction", trace_id=gen_trace_id()):
            result = await Runner.run(agent, user_message)
        response_text = result.final_output
        
        conversation_history[chat_id].append(("Assistant", response_text))
        return response_text

# Função para enviar mensagem
def send_message(chat_id, text):
    response = requests.post(
        "http://localhost:3000/api/sendText",
        json={
            "chatId": chat_id,
            "text": text,
            "session": "default",
        },
    )
    response.raise_for_status()

# Função para marcar como "visto"
def send_seen(chat_id, message_id, participant):
    response = requests.post(
        "http://localhost:3000/api/sendSeen",
        json={
            "session": "default",
            "chatId": chat_id,
            "messageId": message_id,
            "participant": participant,
        },
    )
    response.raise_for_status()

# Simula digitação
def typing(chat_id, seconds):
    requests.post("http://localhost:3000/api/startTyping", json={"session": "default", "chatId": chat_id})
    time.sleep(seconds)
    requests.post("http://localhost:3000/api/stopTyping", json={"session": "default", "chatId": chat_id})



# Funções para gerenciar allowed contacts (formato: número,nome,enabled)
def load_allowed_contacts():
    contacts = []
    if os.path.exists(ALLOWED_CONTACTS_FILE):
        with open(ALLOWED_CONTACTS_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    parts = line.split(",")
                    if len(parts) == 3:
                        contact = parts[0].strip()
                        name = parts[1].strip()
                        enabled = parts[2].strip().lower() == "true"
                        contacts.append({"contact": contact, "name": name, "enabled": enabled})
                    elif len(parts) == 2:
                        # Se só tem número e enabled, usamos o número como nome
                        contact = parts[0].strip()
                        enabled = parts[1].strip().lower() == "true"
                        contacts.append({"contact": contact, "name": contact, "enabled": enabled})
                    else:
                        contacts.append({"contact": line, "name": line, "enabled": True})
    else:
        contacts = [{"contact": "55191111111111", "name": "user-change", "enabled": True}]
    return contacts

def save_allowed_contacts(contacts):
    with open(ALLOWED_CONTACTS_FILE, "w") as f:
        for c in contacts:
            f.write(f"{c['contact']},{c.get('name', c['contact'])},{str(c['enabled']).lower()}\n")

allowed_contacts = load_allowed_contacts()


# Funções para gerenciar configuração global
def load_config():
    config = {"enable_responses": "true"}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    config[key.strip()] = value.strip()
    return config

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        for key, value in config.items():
            f.write(f"{key}={value}\n")

config = load_config()

# API Key do TextMeBot
API_KEY_TEXTMEBOT = os.getenv("API_KEY_TEXTMEBOT")
# Envio de mensagens via WhatsApp usando a API do TextMeBot

# Função para reconstruir o histórico (últimas 5 interações) a partir do log unificado
def reconstruir_historico():
    conversation = []
    # Mantém o prompt inicial
    conversation.append({
        "role": "system",
        "content": (
            

            "Você deve responder como se fosse eu, um cara direto sem enrolação. "
            "Escreva como se estivesse falando no WhatsApp, sem cumprimentos exagerados, sem emoji, sem formalidade e sem frases robóticas. "
            "Use frases curtas, linguagem de dia a dia, pode ser um pouco sarcástico quando fizer sentido. "
            "Não invente respostas se não souber"
            "Não pergunte como pode ajudar, apenas responda ao que foi perguntado. "
            "Evite explicações longas. "
            "Se a pergunta for sobre algo atual, como resultados ou agenda de esportes, clima, notícias ou qualquer coisa que dependa de data e hora atual, use a ferramenta Web Search e responda de forma resumida. "
            "Não revele que você é um chatbot ou usa IA. "
        )
    })
    # Tenta ler o log e pega as últimas 5 interações
    if os.path.exists(MESSAGES_LOG_FILE):
        with open(MESSAGES_LOG_FILE, "r") as f:
            linhas = f.readlines()
        # Considera cada linha como uma interação (JSON)
        ultimas = linhas[-5:]
        for linha in ultimas:
            try:
                entry = json.loads(linha)
                # Adiciona a mensagem do usuário
                conversation.append({
                    "role": "user",
                    "content": entry.get("user_message", "")
                })
                # Adiciona a resposta do assistente
                conversation.append({
                    "role": "assistant",
                    "content": entry.get("assistant_response", "")
                })
            except Exception as e:
                print("Erro ao parsear linha do log:", e)
                continue
    return conversation

# OpenAI responses API com histórico reconstruído a partir do log unificado
def responder_whatsapp(mensagem: str, nome_remetente: str) -> str:
    conversation = reconstruir_historico()
    # Adiciona uma mensagem informando o nome do remetente (caso queira que o modelo saiba)
    conversation.append({
        "role": "system",
        "content": f"O usuário que envia a mensagem se chama {nome_remetente}. "
    })
    # Adiciona a nova mensagem do usuário
    conversation.append({
        "role": "user",
        "content": mensagem
    })
    response = client.responses.create(
         model="gpt-4o-mini",
         input=conversation,
         text={"format": {"type": "text"}},
         reasoning={},
         tools=[
             {
                 "type": "web_search_preview",
                 "user_location": {
                     "type": "approximate",
                     "country": "BR",
                     "region": "São Paulo",
                     "city": "Jundiaí"
                 },
                 "search_context_size": "low"
             }
         ],
         temperature=0.5,
         max_output_tokens=2048,
         top_p=1,
         store=True
    )
    resposta = response.output_text
    print(resposta)
    return resposta

# Interface de configuração – rota principal
@app.route("/", methods=["GET", "POST"])
def index():
    global config, allowed_contacts
    if request.method == "POST":
        # Atualiza a configuração global
        global_enable = request.form.get("enable_responses", "off")
        config["enable_responses"] = "true" if global_enable == "on" else "false"
        
        # Atualiza cada contato individual (checkbox com nome: enabled_<número>)
        for c in allowed_contacts:
            checkbox_name = f"enabled_{c['contact']}"
            c["enabled"] = True if request.form.get(checkbox_name) == "on" else False
        
        # Exclusão de contato (se enviado no campo delete_contact)
        delete_contact = request.form.get("delete_contact", "").strip()
        if delete_contact:
            allowed_contacts = [c for c in allowed_contacts if c["contact"] != delete_contact]
        
        # Adiciona novo contato, se informado
        new_contact = request.form.get("new_contact", "").strip()
        new_contact_name = request.form.get("new_contact_name", "").strip()
        if new_contact:
            if all(new_contact != c["contact"] for c in allowed_contacts):
                if len(allowed_contacts) < 10:
                    if not new_contact_name:
                        new_contact_name = new_contact
                    allowed_contacts.append({"contact": new_contact, "name": new_contact_name, "enabled": True})
                else:
                    return redirect(url_for("index", message="Limite de 10 contatos atingido."))
        
        save_config(config)
        save_allowed_contacts(allowed_contacts)
        return redirect(url_for("index", message="Configurações salvas."))
    
    msg = request.args.get("message", "")
    # Lê o log unificado para exibição na interface
    log_sent_content = ""
    if os.path.exists(MESSAGES_LOG_FILE):
        with open(MESSAGES_LOG_FILE, "r") as f:
            linhas = f.readlines()
        log_entries = []
        for linha in linhas:
            try:
                entry = json.loads(linha)
                log_entries.append(entry)
            except Exception as e:
                print("Erro ao parsear log:", e)
        # Converte os logs para uma string formatada (você pode customizar o layout)
        log_sent_content = "\n".join(json.dumps(entry, indent=2, ensure_ascii=False) for entry in log_entries)
    else:
        log_sent_content = "Nenhuma mensagem registrada."
    
    return render_template("index.html", config=config, allowed_contacts=allowed_contacts, message=msg, log_sent_content=log_sent_content)

# Endpoint do webhook do TextMeBot
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if data.get("event") != "message":
        return f"Unknown event {data.get('event')}", 400

    payload = data.get("payload", {})
    text = payload.get("body")
    chat_id = payload.get("from")
    message_id = payload.get("id")
    participant = payload.get("participant")

    data=payload
    
    # Define o timestamp
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Registra o log de mensagem recebida (mesmo de números não autorizados)
    # Cria uma entrada unificada
    log_entry = {
        "from": data.get("from", ""),
        "from_name": data.get("pushName", "Desconhecido"),
        "to": data.get("to", ""),
        "type": data.get("type", ""),
        "user_message": data.get("body", ""),
        "assistant_response": "",  # Será preenchido abaixo
        "timestamp": timestamp
    }
    print(log_entry)
    
    #if not data or "from" not in data or "message" not in data:
    #    log_entry["assistant_response"] = "Dados inválidos."
    #    with open(MESSAGES_LOG_FILE, "a") as f:
    #        f.write(json.dumps(log_entry) + "\n")
    #    return jsonify({"status": "erro", "detalhe": "Dados inválidos"}), 400
    
    remetente = data.get("from", "").split('@')[0]
    mensagem_recebida = data.get("body", "")
    from_name = data.get("pushName", "Desconhecido")

    #print('from_name:',from_name)
    
    # Verifica se o remetente está na lista de contatos permitidos e se está habilitado
    contact_entry = next((c for c in allowed_contacts if c["contact"] == remetente), None)
    autorizado = contact_entry is not None and contact_entry["enabled"]
    
    if autorizado and config.get("enable_responses", "true") == "true" and mensagem_recebida:
        print("autorizado")
        send_seen(chat_id=chat_id, message_id=message_id, participant=participant)
        
        typing(chat_id, 3)
        # Chama a função async para processar o LLM e obter a resposta

        resposta = responder_whatsapp(mensagem_recebida, from_name)
        
                # Envia a resposta de volta para o usuário
        whatsapp_result = send_message(chat_id, f"🤖: {resposta}")
        
        #whatsapp_result = whatsapp(remetente, f"🤖: {resposta}")
        
        log_entry["assistant_response"] = resposta

    elif not mensagem_recebida:
        resposta = "mensagem texto vazia"
        whatsapp_result = {"status": "ok", "detail": resposta}
        log_entry["assistant_response"] = resposta    
    
    else:
        resposta = "Respostas desabilitadas ou remetente não autorizado."
        whatsapp_result = {"status": "ok", "detail": resposta}
        log_entry["assistant_response"] = resposta
    
    # Registra a entrada unificada no log (cada linha é um JSON)
    with open(MESSAGES_LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    
    return jsonify({
        "status": "ok",
        "resposta": resposta,
        "whatsapp": whatsapp_result
    }), 200

if __name__ == "__main__":
    app.run(host="192.168.0.22", port=5000)
