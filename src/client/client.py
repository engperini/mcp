from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import logging
import os
from dotenv import load_dotenv
import json

load_dotenv()
logging.basicConfig(level=logging.INFO)
logging.getLogger().setLevel(logging.INFO)  # This ensures no debug level logs are shown

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")


# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="python",  # Executable
    args=["/home/pi/mcp/src/server/server.py"],  # Optional command line arguments
    env= None,  # Optional environment variables
)


# Optional: create a sampling callback
async def handle_sampling_message(
    message: types.CreateMessageRequestParams,
) -> types.CreateMessageResult:
    return types.CreateMessageResult(
        role="assistant",
        content=types.TextContent(
            type="text",
            text="Hello, world! from model",
        ),
        model="gpt-3.5-turbo",
        stopReason="endTurn",
    )


async def run():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(
            read, write, sampling_callback=handle_sampling_message
        ) as session:
            # Initialize the connection
            await session.initialize()

            # List available prompts
            prompts = await session.list_prompts()

            # Get a prompt
            #prompt = await session.get_prompt(
            #    "example-prompt", arguments={"arg1": "value"}
            #)

            # List available resources
            resources = await session.list_resources()

            # List available tools
            tools = await session.list_tools()

            # Read a resource
            #content, mime_type = await session.read_resource("file://some/path")

            # Call a tool
            result = await session.call_tool("fetch_weather", arguments={"city": "jundiai"})
                        # Acessando o conteúdo JSON a partir do TextContent
            # Verifique a estrutura de result.content
            #print("Result Content:", result.content)  # Para depuração

            # Asuppondo que result.content seja uma lista e que você precisa pegar o primeiro item
            if isinstance(result.content, list) and len(result.content) > 0:
                weather_data = json.loads(result.content[0].text)  # Acesse o primeiro item se for uma lista
                
                # Imprimindo informações formatadas diretamente
                print(f"Current Weather in Jundiaí:\n"
                      f"Temperature: {weather_data['main']['temp']}°C\n"
                      f"Description: {weather_data['weather'][0]['description'].capitalize()}\n"
                      f"Humidity: {weather_data['main']['humidity']}%\n"
                      f"Wind Speed: {weather_data['wind']['speed']} m/s")
            else:
                print("Unexpected format of result.content:", result.content)
            


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())