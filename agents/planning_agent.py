import os
import json

from agents.base_agent import Agent
from agents.implementation_agent import ImplementationAgent
import chainlit as cl


IMPLEMENTATION_PROMPT = """\
You are a software engineer, implementating the web pages based on the provided plan.

You should read process from the artifacts provided to you at the end of the system prompt, and tackle ONE of the milestones at a time. In order to maximize success, we want to take quite small steps.

You should also take feedback to fix a milestone before marking it as completed.

You will generate an index.html and a styles.css file for your implementation for the milestone.

If the user or reviewer confirms the implementation is good, use available tools to save the index.html and styles.css in an artifact \
folder. If the user has feedback on the implementation, revise the implementation, and save it using \
the tool again. A tool is available to update the artifact. Your role is to only pick and implement ONE milestone at a time.
You will not regenerate or modify the existing plan.

If the implementation has already been saved, no need to save it again unless there is feedback. Do not \
use the tool again if there are no changes.

After implementing a milestone, update the milestone section of the plan and use the tool available to you to save the updated artificat in the markdown file. 

Milestones should be formatted like this:

 - [*] 1. This milestone has been implemented, only mark if you have implemented a milestone
 - [ ] 2. This is the second milestone but not implemented yet
 - [ ] 3. This is the third milestone but not implemented yet
"""

class PlanningAgent(Agent):
    tools = [
        {
            "type": "function",
            "function": {
                "name": "updateArtifact",
                "description": "Update an artifact file which is markdown with the given contents of the generated.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The name of the file to update.",
                        },
                        "contents": {
                            "type": "string",
                            "description": "The markdown contents to write to the file.",
                        },
                    },
                    "required": ["filename", "contents"],
                    "additionalProperties": False,
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "callAgent",
                "description": "Call another agent to delegate a task if the user wants to implement the plan, callAgent('implementation')",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_name": {
                            "type": "string",
                            "description": "The name of the agent to execute a task.",
                        },
                    },
                    "required": ["agent_name"],
                    "additionalProperties": False,
                },
            }
        }
    ]
    def __init__(self, name, client, prompt="", gen_kwargs=None):

        super().__init__(name, client, prompt="", gen_kwargs=None)

    async def execute(self, message_history):
        """
        Executes the agent's main functionality.

        Note: probably shouldn't couple this with chainlit, but this is just a prototype.
        """
        copied_message_history = message_history.copy()

        # Check if the first message is a system prompt
        if copied_message_history and copied_message_history[0]["role"] == "system":
            # Replace the system prompt with the agent's prompt
            copied_message_history[0] = {"role": "system", "content": self._build_system_prompt()}
        else:
            # Insert the agent's prompt at the beginning
            copied_message_history.insert(0, {"role": "system", "content": self._build_system_prompt()})

        response_message = cl.Message(content="")
        await response_message.send()

        stream = await self.client.chat.completions.create(messages=copied_message_history, stream=True, tools=self.tools, tool_choice="auto", **self.gen_kwargs)

        function_data = {} 
        function_calls = {}

        async for part in stream:
            if part.choices[0].delta.tool_calls:
                tool_call = part.choices[0].delta.tool_calls[0]
                index = tool_call.index
                function_name_delta = tool_call.function.name or ""
                arguments_delta = tool_call.function.arguments or ""
                index_data = function_data.setdefault(index, {})
                index_data.setdefault("name", []).append(function_name_delta)
                index_data.setdefault("arguments", []).append(arguments_delta)
        
            if token := part.choices[0].delta.content or "":
                await response_message.stream_token(token)        
        
        for index, index_data in function_data.items():
            index_data["name"] = ''.join(index_data["name"])
            index_data["arguments"] = ''.join(index_data["arguments"])
            function_calls[index_data["name"]] = index_data["arguments"]

        if function_calls:
            print(f"DEBUG: function_calls: {function_calls}")

            if "updateArtifact" in function_calls:                
                arguments_dict = json.loads(function_calls["updateArtifact"])
                filename = arguments_dict.get("filename")
                contents = arguments_dict.get("contents")
                
                if filename and contents:
                    os.makedirs("artifacts", exist_ok=True)
                    with open(os.path.join("artifacts", filename), "w") as file:
                        file.write(contents)
                    
                    # Add a message to the message history
                    message_history.append({
                        "role": "system",
                        "content": f"The artifact '{filename}' was updated."
                    })

                    stream = await self.client.chat.completions.create(messages=message_history, stream=True, **self.gen_kwargs)
                    async for part in stream:
                        if token := part.choices[0].delta.content or "":
                            await response_message.stream_token(token)
            if "callAgent" in function_calls:
                arguments_dict = json.loads(function_calls["callAgent"])
                agent_name = arguments_dict.get("agent_name")
                if agent_name == "implementation":
                    message_history.append({
                        "role": "system",
                        "content": f"Provide an implementation."
                    })
                    implementation_agent = ImplementationAgent(name="Implementatuib Agent", client=self.client, prompt=IMPLEMENTATION_PROMPT)
                    response_message = await implementation_agent.execute(message_history)
        else:
            print("No tool call")

        await response_message.update()

        return response_message.content


