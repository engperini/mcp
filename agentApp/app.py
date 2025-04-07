import asyncio
import logging
from dotenv import load_dotenv
from pathlib import Path
import sys
# Adiciona o diretório agentApp ao PYTHONPATH
sys.path.append(str(Path(__file__).parent))

from weather_agent import WeatherAgent
from config import configure_logging

load_dotenv()
configure_logging()

async def main():
    agent = WeatherAgent(
        user_name="Arthur",
        default_location="Jundiai",
        preferences={"temperature_unit": "celsius"}
    )
    
    try:
        await agent.initialize()
        print("Bem-vindo ao Assistente Climático! Digite 'sair' para encerrar.")
        
        while True:
            try:
                query = input("\nVocê: ").strip()
                if query.lower() in ('sair', 'exit', 'quit'):
                    break
                    
                if not query:
                    continue
                    
                response = await agent.chat(query)
                print("\nAssistente:", response)
                
            except KeyboardInterrupt:
                print("\nEncerrando a sessão...")
                break
            except Exception as e:
                logging.exception("Erro inesperado:")
                print("Ocorreu um erro. Reiniciando a sessão...")
                await agent.close()
                await agent.initialize()
                
    finally:
        await agent.close()
        print("Sessão encerrada. Até logo!")

if __name__ == "__main__":
    asyncio.run(main())