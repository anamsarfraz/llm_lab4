from agents.base_agent import Agent
import chainlit as cl
import os
import json

class ImplementationAgent(Agent):
    tools = [
        {
            "type": "function",
            "function": {
                "name": "updateArtifact",
                "description": "Update an artifact file which is HTML, or CSS, with the given contents.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The name of the file to update.",
                        },
                        "contents": {
                            "type": "string",
                            "description": "The HTML, or CSS contents to write to the file.",
                        },
                    },
                    "required": ["filename", "contents"],
                    "additionalProperties": False,
                },
            }
        }
    ]
    def __init__(self, name, client, prompt="", gen_kwargs=None):

        super().__init__(name, client, prompt=prompt, gen_kwargs=gen_kwargs)

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

            print(f"DEBUG: function_data: {function_data}")

            if "updateArtifact" == index_data["name"]:
                arguments_dict = json.loads(index_data["arguments"])
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

        else:
            print("No tool call")

        await response_message.update()

        return response_message


