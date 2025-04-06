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

            city = "jundiai"
            days = 1
            # Call current weather tool
            result = await session.call_tool("fetch_weather", arguments={"city": city})
            weather_data = json.loads(result.content[0].text)
            weather_text = (f"Current Weather in Jundiaí: Temperature: {weather_data['main']['temp']}°C, Description: {weather_data['weather'][0]['description'].capitalize()}, Humidity: {weather_data['main']['humidity']}%, Wind Speed: {weather_data['wind']['speed']} m/s")
            print(weather_text)

            
            # Call forecast weather tool
            result = await session.call_tool("fetch_forecast", arguments={"city": city, "days":days})
            weather_data = json.loads(result.content[0].text)
            #weather_text = (f"Current Weather in Jundiaí: Temperature: {weather_data['main']['temp']}°C, Description: {weather_data['weather'][0]['description'].capitalize()}, Humidity: {weather_data['main']['humidity']}%, Wind Speed: {weather_data['wind']['speed']} m/s")
            print(weather_data)



          

if __name__ == "__main__":
    import asyncio

    asyncio.run(run())