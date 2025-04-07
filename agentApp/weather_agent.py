from datetime import datetime
from chat_session import BaseChatSession
from agents import Agent, Runner, WebSearchTool, gen_trace_id, trace
from agents.mcp import MCPServerStdio

class WeatherAgent(BaseChatSession):
    def __init__(self, user_name: str, default_location: str, preferences: dict):
        super().__init__()
        self.user_context = {
            "name": user_name,
            "location": default_location,
            "preferences": preferences
        }
    
    async def initialize(self):
        self.mcp_server = await MCPServerStdio(params=self.server_params).__aenter__()
        
        self.agent = Agent(
            name="WeatherAssistantPro",
            model="gpt-4o-mini",
            tools=[WebSearchTool(user_location={
                "type": "approximate", 
                "city": self.user_context["location"].lower()
            })],
            instructions=self._build_instructions(),
            mcp_servers=[self.mcp_server],
            model_settings=self.model_settings,
        )
    
    def _build_instructions(self) -> str:
        base_instructions = (
            "Você é um assistente chatbot conciso e direto especializado em clima. "
            "Forneça informações meteorológicas precisas e pesquisas na web quando necessário.\n\n"
            "Contexto do usuário:\n"
            f"- Nome: {self.user_context['name']}\n"
            f"- Localização padrão: {self.user_context['location']}\n"
            f"- Preferências: {self.user_context['preferences']['temperature_unit']}\n\n"
        )
        
        if self.conversation_history:
            base_instructions += "Últimas interações:\n"
            for i, (role, msg) in enumerate(self.conversation_history[-3:], 1):
                base_instructions += f"{i}. {role}: {msg}\n"
            base_instructions += "\n"
        
        base_instructions += (
            f"Data e hora atual: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "Diretrizes:\n"
            "- Seja conciso mas informativo\n"
            "- Use emojis quando apropriado\n"
            "- Sempre resuma pesquisas web\n"
            "- Verifique dados com ferramentas quando necessário"
        )
        
        return base_instructions