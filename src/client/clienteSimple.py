import os
import asyncio
from dotenv import load_dotenv
from agents import Agent, Runner, gen_trace_id, trace, WebSearchTool
from agents.mcp import MCPServerStdio
from agents.model_settings import ModelSettings
import sys

sys.path.append(os.path.abspath('/home/pi/mcp/src/server'))
import webhookserver  # Importa o módulo do server, que possui a fila message_queue

load_dotenv()

# Memória simplificada (apenas histórico)
conversation_history = []

server_params = {
    "command": "python",
    "args": ["/home/pi/mcp/src/server/server.py"],
    "env": os.environ.copy(),
}



async def run():
    # Inicia o MCPServerStdio; isso vai rodar o seu server.py como um subprocesso
    async with MCPServerStdio(params=server_params) as mcp_server:
        agent = Agent(
            name="Assistant",
            instructions="Você é um assistente chatbot útil. Últimas mensagens:\n" +
                         "\n".join(f"{role}: {msg}" for role, msg in conversation_history[-3:]),
            model="gpt-4o-mini",
            tools=[WebSearchTool()],
            mcp_servers=[mcp_server],
            model_settings=ModelSettings(tool_choice="auto"),
        )
        
        # Cria uma tarefa assíncrona para processar a fila
        asyncio.create_task(process_queue())
        
        # Loop principal para receber input do usuário e tratar as interações com o agente
        while True:
            query = input("\nVocê: ").strip()
            if query.lower() in ('sair', 'exit'):
                break

            conversation_history.append(("User", query))
            with trace("Agent interaction", trace_id=gen_trace_id()):
                try:
                    # Atualiza as instruções com o histórico recente
                    agent.instructions = "Histórico:\n" + "\n".join(f"{role}: {msg}" for role, msg in conversation_history[-3:])
                    result = await Runner.run(agent, query)
                    response = result.final_output
                    conversation_history.append(("Assistant", response))
                    print("\nAssistente:", response)
                except Exception as e:
                    print("Erro:", str(e))

if __name__ == "__main__":
    asyncio.run(run())
    
