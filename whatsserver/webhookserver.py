from flask import Flask, request
import requests
import asyncio
import time

import time
from agents import Agent, Runner, gen_trace_id, trace, WebSearchTool
from agents.model_settings import ModelSettings
from agents.mcp import MCPServerStdio
import os

# Histórico de conversas por chat (ex.: { chat_id: [("User", msg), ("Assistant", msg), ...] })
conversation_history = {}
server_params = {
    "command": "python",
    "args": ["/home/pi/mcp/src/server/server.py"],
    "env": os.environ.copy(),
}
# Flask app
app = Flask(__name__)

autorized = "5519971120828@c.us"


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

@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    data = request.get_json()
    

    if data.get("event") != "message":
        return f"Unknown event {data.get('event')}", 400

    payload = data.get("payload", {})
    text = payload.get("body")
    chat_id = payload.get("from")
    message_id = payload.get("id")
    participant = payload.get("participant")

    print("From:", chat_id)
    print("Recebido:", text)

    if not text or not chat_id:
        return "Invalid message", 400
    
    # Marca como visto
    send_seen(chat_id=chat_id, message_id=message_id, participant=participant)
    
    if chat_id == autorized:
        typing(chat_id, 2)
        # Chama a função async para processar o LLM e obter a resposta
        try:
            response_text = asyncio.run(process_llm(chat_id, text))
        except Exception as e:
            print("Erro ao processar LLM:", e)
            response_text = "Desculpe, ocorreu um erro ao processar sua mensagem."

        # Envia a resposta de volta para o usuário
        send_message(chat_id, response_text)


    
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

