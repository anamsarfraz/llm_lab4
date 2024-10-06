import os
import chainlit as cl

class Agent:
    """
    Base class for all agents.
    """

    tools = [
        {
            "type": "function",
            "function": {
                "name": "updateArtifact",
                "description": "Update an artifact file which is HTML, CSS, or markdown with the given contents.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The name of the file to update.",
                        },
                        "contents": {
                            "type": "string",
                            "description": "The markdown, HTML, or CSS contents to write to the file.",
                        },
                    },
                    "required": ["filename", "contents"],
                    "additionalProperties": False,
                },
            }
        }
    ]

    def __init__(self, name, client, prompt="", gen_kwargs=None):
        self.name = name
        self.client = client
        self.prompt = prompt
        self.gen_kwargs = gen_kwargs or {
            "model": "gpt-4o-mini",
            "temperature": 0.2
        }

    def _build_system_prompt(self):
        """
        Builds the system prompt including the agent's prompt and the contents of the artifacts folder.
        """
        artifacts_content = "<ARTIFACTS>\n"
        artifacts_dir = "artifacts"

        if os.path.exists(artifacts_dir) and os.path.isdir(artifacts_dir):
            for filename in os.listdir(artifacts_dir):
                file_path = os.path.join(artifacts_dir, filename)
                if os.path.isfile(file_path):
                    with open(file_path, "r") as file:
                        file_content = file.read()
                        artifacts_content += f"<FILE name='{filename}'>\n{file_content}\n</FILE>\n"
        
        artifacts_content += "</ARTIFACTS>"
        return f"{self.prompt}\n{artifacts_content}"
    
    async def handle_tool_calls(self, message_history, call_tools=True):

        stream = await self.client.chat.completions.create(messages=message_history, stream=True, tools=self.tools if call_tools else None, **self.gen_kwargs)

        function_data = {}
        response_message = cl.Message(content="")
        #await response_message.send()    
        
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

        await response_message.update()        

        if response_message.content:
            message_history.append({"role": "assistant", "content": response_message.content})
            cl.user_session.set("message_history", message_history)        

        for index, index_data in function_data.items():
            index_data["name"] = ''.join(index_data["name"])
            index_data["arguments"] = ''.join(index_data["arguments"])

        return response_message, function_data