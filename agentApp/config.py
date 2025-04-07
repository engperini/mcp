import os
import logging
from dotenv import load_dotenv

def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configuração do OpenAI
    if not os.getenv("OPENAI_API_KEY"):
        load_dotenv()
    
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY não encontrada no ambiente")