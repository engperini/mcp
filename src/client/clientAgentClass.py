import os
import openai
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from agents import Agent, Runner, WebSearchTool, gen_trace_id, trace
from agents.mcp import MCPServerStdio
from agents.model_settings import ModelSettings
import logging

# Configuração
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

openai.api_key = os.getenv("OPENAI_API_KEY")

class ChatSession:
    def __init__(self):
        self.server_params = {
            "command": "python",
            "args": ["/home/pi/mcp/src/server/server.py"],
            "env": os.environ.copy(),
        }
        self.model_settings = ModelSettings(
            tool_choice="auto",
            temperature=0.7,
            max_tokens=2000
        )
        self.agent = None
        self.conversation_history = []
        self.user_context = {
            "name": None,  #personal
            "location": None, #personal
            "preferences": {
                "temperature_unit": "celsius",
                
            }
        }
    
    async def initialize(self):
        self.mcp_server = await MCPServerStdio(params=self.server_params).__aenter__()
        
        # Instruções dinâmicas que incluem contexto e histórico
        dynamic_instructions = self._build_instructions()
        
        self.agent = Agent(
            name="WeatherAssistantPro",
            model="gpt-4o-mini",  # Modelo mais atualizado
            tools=[WebSearchTool()],
            instructions=dynamic_instructions,
            mcp_servers=[self.mcp_server],
            model_settings=self.model_settings,
        )
    
    def _build_instructions(self) -> str:
        """Constroi as instruções dinâmicas incluindo contexto e histórico"""
        base_instructions = (
            "Você é um assistente chatbot conciso e direto. "
            "Seu objetivo é fornecer informações sucintas de clima e tempo precisas, voce pode pesquisar sobre qualquer coisa na internet, "
            "Sempre que possível, use ferramentas para obter dados atualizados e sempre resuma a resposta para o usuario.\n\n"
        )
        
        # Adiciona contexto do usuário
        context_section = "Contexto do usuário:\n"
        if self.user_context["name"]:
            context_section += f"- Nome: {self.user_context['name']}\n"
        if self.user_context["location"]:
            context_section += f"- Localização padrão: {self.user_context['location']}\n"
        context_section += (
            f"- Preferências: {self.user_context['preferences']['temperature_unit']}, "
            
        )
        
        # Adiciona histórico resumido se houver
        history_section = ""
        if self.conversation_history:
            history_section = "Últimas interações:\n"
            for i, (role, msg) in enumerate(self.conversation_history[-3:], 1):
                history_section += f"{i}. {role}: {msg}\n"
            history_section += "\n"
        
        # Data atual para contexto temporal
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        time_section = f"Data e hora atual: {current_time}\n\n"
        
        # Instruções finais
        final_instructions = (
            "Diretrizes importantes:\n"
            "- Se o usuário perguntar sobre clima sem especificar localização, "
            "use a localização padrão se disponível.\n"
            "- Para previsões, sempre especifique a fonte dos dados.\n"
            "- Mantenha respostas claras e informativas.\n"
            "- Use emojis relevantes quando apropriado para melhorar a experiência."
        )
        
        return (
            base_instructions + 
            context_section + 
            history_section + 
            time_section + 
            final_instructions
        )
    
    async def chat(self, query: str) -> str:
        # Atualiza histórico antes de processar
        self._update_history("user", query)
        
        with trace("Agent interaction", trace_id=gen_trace_id()):
            try:
                # Atualiza instruções com contexto mais recente
                self.agent.instructions = self._build_instructions()
                
                result = await Runner.run(self.agent, query)
                response = result.final_output
                
                # Atualiza histórico após resposta
                self._update_history("assistant", response)
                
                return response
            except Exception as e:
                logger.error(f"Erro na conversação: {str(e)}")
                error_msg = "Desculpe, ocorreu um erro ao processar sua solicitação."
                self._update_history("system", error_msg)
                return error_msg
    
    def _update_history(self, role: str, message: str):
        """Atualiza o histórico de conversação"""
        self.conversation_history.append((role, message.strip()))
        
        # Mantém um limite razoável no histórico
        if len(self.conversation_history) > 10:
            self.conversation_history.pop(0)
    
    async def close(self):
        await self.mcp_server.__aexit__(None, None, None)

async def main():
    session = ChatSession()
    try:
        await session.initialize()
        
        print("Bem-vindo ao Assistente Climático! Digite 'sair' para encerrar.")
        
        while True:
            try:
                query = input("\nVocê: ").strip()
                if query.lower() in ('sair', 'exit', 'quit'):
                    break
                    
                if not query:
                    continue
                    
                response = await session.chat(query)
                print("\nAssistente:", response)
                
            except KeyboardInterrupt:
                print("\nEncerrando a sessão...")
                break
            except Exception as e:
                logger.exception("Erro inesperado:")
                print("Ocorreu um erro inesperado. A sessão será reiniciada.")
                await session.close()
                session = ChatSession()
                await session.initialize()
                
    finally:
        await session.close()
        print("Sessão encerrada. Até logo!")

if __name__ == "__main__":
    asyncio.run(main())