import json
import os
from app.agent.schemas.structuredOutput import AddItineraryEvent
from app.agent.schemas.structuredInput import TripInput

from app.agent.helpers.utils import normalize_llm_schema
from app.agent.core.runtime import agent_runtime_context
from app.agent.core.runtime import runtime
import asyncio

inputSchema = TripInput.model_json_schema()
outputSchema = AddItineraryEvent.model_json_schema()

fixedInputSchema = normalize_llm_schema(inputSchema)
fixedOutputSchema = normalize_llm_schema(outputSchema)

relativePath = "app/agent/dumps/"
absolutePath = os.path.abspath(relativePath)
if not os.path.exists(absolutePath):
    os.makedirs(absolutePath)

with open(absolutePath + "/input_schema_dump.json", "w") as f:
    json.dump(fixedInputSchema, f, indent=2)

with open(absolutePath + "/output_schema_dump.json", "w") as f:
    json.dump(fixedOutputSchema, f, indent=2)

print("Imput & Output Schemas Dumped properly!")

async def dump_mcp_tools():
    async with agent_runtime_context():
        mcpTools = runtime.llm_tools
        mcpTools = [tool.model_dump() for tool in mcpTools]
        with open(absolutePath + "/mcp_tools_dump.json", "w") as f:
            json.dump(mcpTools, f, indent=2)

asyncio.run(dump_mcp_tools())

print("MCP Tools Dumped properly!")

