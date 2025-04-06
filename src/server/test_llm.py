from llm import LLMConnector
from dotenv import load_dotenv
import os


load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

async def test_ask_openai():
    print("\nTesting OpenAI API call...")
    connector = LLMConnector(OPENAI_API_KEY)
    response = await connector.ask_openai("Hello, how are you?")
    print(f"OpenAI Response: {response}")
    assert isinstance(response, str)
    assert len(response) > 0


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_ask_openai())