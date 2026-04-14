import os
import json
import logging
from typing import AsyncGenerator, Dict, Any
import asyncio
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from app.core.config import settings
from app.agent.schemas.structuredInput import TripInput
from app.agent.schemas.structuredOutput import AddItineraryEvent
from app.agent.utils import fix_schema_for_gemini
from openai import OpenAI

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "plannerPrompt.md")
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

logger = logging.getLogger(__name__)

planner_api_key = settings.PLANNER_AGENT_API_KEY
planner_model = settings.PLANNER_AGENT_MODEL

ADD_EVENT_TOOL = types.FunctionDeclaration(
    name="add_itinerary_event",
    description="Call this tool to commit a specific event (Flight, Hotel, etc.) to the user's itinerary. "
                "The agent must call this multiple times to build a full trip.",
    # This ensures Gemini treats the arguments as a strictly structured JSON object
    parameters=fix_schema_for_gemini(AddItineraryEvent.model_json_schema())
)

def convert_mcp_to_gemini(mcp_tool) -> types.FunctionDeclaration:
    return types.FunctionDeclaration(
        name=mcp_tool.name,
        description=mcp_tool.description or "",
        parameters=fix_schema_for_gemini(mcp_tool.inputSchema)
    )


async def generate_trip_itinerary(trip_payload: dict) -> AsyncGenerator[Dict[str, Any], None]:
    try:
        client = genai.Client(api_key=planner_api_key)

    except Exception as e:
        logger.error(f"Failed to initialize GenAI client: {e}")
        
    try:
        trip_data = TripInput(**trip_payload)
    except Exception as e:
        yield {"type": "error", "content": f"Invalid input: {e}"}
        return

    server_params = StdioServerParameters(
        command="python",
        args=["-m", "app.agent.mcp_server.main"],
        env=os.environ.copy()
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                mcp_response = await session.list_tools()

                gemini_tools = [convert_mcp_to_gemini(t) for t in mcp_response.tools]
                gemini_tools.append(ADD_EVENT_TOOL)
                
                config = types.GenerateContentConfig(
                    tools=[types.Tool(function_declarations=gemini_tools)],
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.6, # 0.6 is a good starting point for creative tasks. More temperature = more creativity but less consistency
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
                )

                chat = client.chats.create(model=planner_model, config=config)
                
                current_message = f"User Request: {trip_data.model_dump_json()}"

                while True:
                    # Use the stream for the 'Thinking' and 'Tool Call' UI experience
                    
                    max_retries = 6
                    retry_delay = 2
                    
                    for attempt in range(max_retries):
                        try:
                            response_stream = chat.send_message_stream(current_message)
                            
                            active_tool_calls = []
                            turn_text = ""

                            for chunk in response_stream:
                                # Stream the 'Thought' text
                                if chunk.text:
                                    turn_text += chunk.text
                                    yield {"type": "thinking", "content": chunk.text}
                                
                                # Check for tool calls in the candidate parts
                                if getattr(chunk, 'candidates', None) and len(chunk.candidates) > 0 and getattr(chunk.candidates[0], 'content', None) and getattr(chunk.candidates[0].content, 'parts', None):
                                    for part in chunk.candidates[0].content.parts:
                                        if part.function_call:
                                            fc = part.function_call
                                            active_tool_calls.append(fc)
                                            
                                            if fc.name == "add_itinerary_event":
                                                # fc.args is a validated dict
                                                yield {"type": "event", "data": fc.args}
                                            else:
                                                yield {"type": "tool_call", "tool_name": fc.name, "args": fc.args}
                            
                            break # Success, exit retry loop
                        except Exception as e:
                            if "503" in str(e) or "429" in str(e) or "500" in str(e):
                                if attempt < max_retries - 1:
                                    yield {"type": "system", "content": f"Google API Overloaded/Internal Error ({str(e)[:50]}...). Retrying in {retry_delay}s... (Attempt {attempt+1}/{max_retries})"}
                                    await asyncio.sleep(retry_delay)
                                    retry_delay *= 2
                                else:
                                    raise
                            else:
                                raise

                    if not active_tool_calls:
                        # If no tools were called, the agent has finished the response
                        if turn_text.strip():
                            yield {"type": "summary", "content": turn_text.strip()}
                        break 
                    
                    # Resolve Tool Responses concurrently!
                    async def execute_tool(fc):
                        if fc.name == "add_itinerary_event":
                            return fc, {"status": "success", "message": "Event added to timeline."}
                        try:
                            mcp_result = await session.call_tool(fc.name, fc.args)
                            result = {"output": "".join([c.text for c in mcp_result.content if hasattr(c, 'text')])}
                        except Exception as e:
                            result = {"error": str(e)}
                        return fc, result
                    
                    # Fire all MCP network requests off at exactly the same time
                    gathered_results = await asyncio.gather(*(execute_tool(fc) for fc in active_tool_calls))
                    
                    tool_responses = []
                    for fc, result in gathered_results:
                        if fc.name != "add_itinerary_event":
                            yield {"type": "tool_response", "tool_name": fc.name, "response": result}

                        tool_responses.append(
                            types.Part.from_function_response(name=fc.name, response=result)
                        )

                    # Pass the tool results back for the next turn in the ReAct loop
                    current_message = tool_responses


    except Exception as e:
        import traceback
        traceback.print_exc()
        yield {"type": "error", "content": f"Runtime Error: {str(e)}"}