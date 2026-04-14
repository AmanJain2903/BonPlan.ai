import json
import os
from app.agent.schemas.structuredOutput import AddItineraryEvent
from app.agent.schemas.structuredInput import TripInput

from app.agent.utils import fix_schema_for_gemini

inputSchema = TripInput.model_json_schema()
outputSchema = AddItineraryEvent.model_json_schema()

fixedInputSchema = fix_schema_for_gemini(inputSchema)
fixedOutputSchema = fix_schema_for_gemini(outputSchema)

relativePath = "app/agent/dumps/"
absolutePath = os.path.abspath(relativePath)
if not os.path.exists(absolutePath):
    os.makedirs(absolutePath)

with open(absolutePath + "/input_schema_dump.json", "w") as f:
    json.dump(fixedInputSchema, f, indent=2)

with open(absolutePath + "/output_schema_dump.json", "w") as f:
    json.dump(fixedOutputSchema, f, indent=2)

print("Imput & Output Schemas Dumped properly!")
