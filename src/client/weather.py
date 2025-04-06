from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import logging
import os
from dotenv import load_dotenv
import json
from collections import defaultdict
from openai import AsyncOpenAI

load_dotenv()
logging.basicConfig(level=logging.INFO)
logging.getLogger().setLevel(logging.INFO)  # This ensures no debug level logs are shown

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")


# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="python",  # Executable
    args=["/home/pi/mcp/src/server/server.py"],  # Optional command line arguments
    env=None,  # Optional environment variables
)

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
conversation_history = [{"role": "system", "content": "You are a helpful assistant."}]
async def handle_openai_sampling(message: types.CreateMessageRequestParams) -> types.CreateMessageResult:
    try:
        user_content = next((c.text for m in message.messages for c in getattr(m, "content", []) if c.type == "text"), "Hello, please assist me.")
        conversation_history.append({"role": "user", "content": user_content})

        response = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo", messages=conversation_history
        )

        ai_text = response.choices[0].message.content
        conversation_history.append({"role": "assistant", "content": ai_text})
        
        return types.CreateMessageResult(role="assistant", content=types.TextContent(type="text", text=ai_text), model="gpt-3.5-turbo", stopReason="endTurn")
    except Exception as e:
        logging.error(f"OpenAI API error: {e}")
        return types.CreateMessageResult(role="assistant", content=types.TextContent(type="text", text=f"Error: {e}"), model="gpt-3.5-turbo", stopReason="error")


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

# Função específica que busca e exibe o weather e o forecast
async def fetch_and_display_weather(session):
    city = input("Digite o nome da cidade: ").strip()
    try:
        days = int(input("Digite o número de dias para previsão: "))
    except ValueError:
        print("Quantidade inválida, utilizando 1 dia como padrão.")
        days = 1

    # Chama a ferramenta de clima atual
    result = await session.call_tool("fetch_weather", arguments={"city": city})
    weather_data = json.loads(result.content[0].text)
    current_weather = (
        f"Agora em {city.capitalize()}: {weather_data['main']['temp']}°C, "
        f"{weather_data['weather'][0]['description'].capitalize()}, "
        f"umidade de {weather_data['main']['humidity']}% e vento de {weather_data['wind']['speed']} m/s."
    )
    print(current_weather)

    # Calcula o cnt necessário (8 previsões a cada dia, com intervalos de 3h)
    cnt = days * 8

    # Chama a ferramenta de previsão do tempo passando o cnt calculado
    result = await session.call_tool("fetch_forecast", arguments={"city": city, "days": cnt})
    forecast_data = json.loads(result.content[0].text)
    forecast_list = forecast_data.get('list', [])
    
    if forecast_list:
        # Agrupa as previsões por data (YYYY-MM-DD)
        daily_temps = defaultdict(list)
        for forecast in forecast_list:
            dt_txt = forecast.get('dt_txt', '')
            date = dt_txt.split(" ")[0] if dt_txt else "Data desconhecida"
            temp_min = forecast['main']['temp_min']
            temp_max = forecast['main']['temp_max']
            daily_temps[date].append((temp_min, temp_max))
        
        daily_summary = []
        # Ordena as datas e calcula, para cada dia, o mínimo e máximo
        for date in sorted(daily_temps.keys()):
            temps = daily_temps[date]
            day_min = min(t[0] for t in temps)
            day_max = max(t[1] for t in temps)
            daily_summary.append(f"{date}: Mín {day_min}°C, Máx {day_max}°C")
            
        forecast_summary = (
            f"Previsão para {city.capitalize()} para os próximos {days} dia(s): " +
            "; ".join(daily_summary) + "."
        )
        print(forecast_summary)
    else:
        print("Não foi possível obter a previsão do tempo.")

        
async def run1():
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

            # Chama a função que busca e exibe o weather e forecast
            await fetch_and_display_weather(session)

async def run():
    print("\n===== MCP CLIENT =====\n")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write, sampling_callback=handle_openai_sampling) as session:
            await session.initialize()
            print(f"Available tools: {[tool.name for tool in (await session.list_tools()).tools]}")
            
            while True:
                user_input = input("\nYou: ").strip()
                if user_input.lower() == "exit":
                    print("Exiting...")
                    break
                
                print("\n[USING OpenAI]")
                conversation_history.append({"role": "user", "content": user_input})
                response = await openai_client.chat.completions.create(
                    model="gpt-3.5-turbo", messages=conversation_history
                )
                assistant_response = response.choices[0].message.content
                print(f"\nAssistant: {assistant_response}")
                conversation_history.append({"role": "assistant", "content": assistant_response})


if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
