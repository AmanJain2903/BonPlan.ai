# ask_user_question

## Purpose
Call this tool to ask the user a single short question and pause planning until they answer. Use ONLY when a user-flavor decision is genuinely ambiguous (vibe, intensity, choice between equally good options) — never to ask about facts, prices, distances, hours, or anything the user already supplied in trip_input/preferences or you could find from tool responses. Provide 2-4 short, scannable option chips and an answer_type. The user may pick a chip, type their own answer, or skip — you receive whichever they chose.

## When to use
Use this tool when you need a user-preference decision that cannot be resolved by tool outputs alone. For example: vibe (relaxed vs adventure), intensity (packed vs leisurely), specific choice between two equally good options from tools, or clarification on undefined user input. Do NOT use this tool to retrieve factual information such as prices, distances, opening hours, or anything you can find with `search_places`, `get_route_matrix`, `search_hotels`, or any esisting tools you have access to.

