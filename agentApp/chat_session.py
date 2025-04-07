import logging
from agents import Agent, Runner, gen_trace_id, trace
from agents.model_settings import ModelSettings

class BaseChatSession:
    def __init__(self):
        self.server_params = {
            "command": "python",
            "args": ["/home/pi/mcp/src/server/server.py"],
            "env": {},
        }
        self.model_settings = ModelSettings(
            tool_choice="auto",
            temperature=0.7,
            max_tokens=2000
        )
        self.agent = None
        self.conversation_history = []
        self.user_context = {}
    
    async def chat(self, query: str) -> str:
        self._update_history("user", query)
        
        with trace("Agent interaction", trace_id=gen_trace_id()):
            try:
                if self.agent:
                    self.agent.instructions = self._build_instructions()
                
                result = await Runner.run(self.agent, query)
                response = result.final_output
                self._update_history("assistant", response)
                return response
            except Exception as e:
                logging.error(f"Erro na conversação: {str(e)}")
                error_msg = "Desculpe, ocorreu um erro."
                self._update_history("system", error_msg)
                return error_msg
    
    def _update_history(self, role: str, message: str):
        self.conversation_history.append((role, message.strip()))
        if len(self.conversation_history) > 10:
            self.conversation_history.pop(0)
    
    async def close(self):
        if hasattr(self, 'mcp_server'):
            await self.mcp_server.__aexit__(None, None, None)
    
    def _build_instructions(self) -> str:
        raise NotImplementedError("Subclasses devem implementar este método")