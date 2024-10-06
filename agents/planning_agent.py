import os
import json

from agents.base_agent import Agent
import chainlit as cl


class PlanningAgent(Agent):
    tools = [
        {
            "type": "function",
            "function": {
                "name": "updateArtifact",
                "description": "Update an artifact file which is markdown with the given contents.",
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
        }
    ]
    def __init__(self, name, client, prompt="", gen_kwargs=None):

        super().__init__(name, client, prompt=prompt, gen_kwargs=gen_kwargs)

    async def execute(self, message_history):
        """
        Executes the agent's main functionality.

        Note: probably shouldn't couple this with chainlit, but this is just a prototype.
        """
        print(f"{self.__class__.__name__}: Inside the execution and processing the request")  
        copied_message_history = message_history.copy()

        # Check if the first message is a system prompt
        if copied_message_history and copied_message_history[0]["role"] == "system":
            # Replace the system prompt with the agent's prompt
            copied_message_history[0] = {"role": "system", "content": self._build_system_prompt()}
        else:
            # Insert the agent's prompt at the beginning
            copied_message_history.insert(0, {"role": "system", "content": self._build_system_prompt()})


        response_message, function_data = await self.handle_tool_calls(copied_message_history)
        #print(f"{self.__class__.__name__}: Function data: ", function_data)
        #print(f"{self.__class__.__name__}: Response text: ", response_message.content)
        if response_message.content:
            message_history.append({"role": "assistant", "content": response_message.content})
            copied_message_history.append({"role": "assistant", "content": response_message.content})
            cl.user_session.set("message_history", message_history)      
        
        #print(f"DEBUG: function_data: {function_data}")
        if function_data:
            print(f"{self.__class__.__name__}: Received Function data just inside while loop: ", function_data)
            for index, index_data in function_data.items():
                if "updateArtifact" == index_data["name"]:
                    arguments_dict = json.loads(index_data["arguments"])
                    filename = arguments_dict.get("filename")
                    contents = arguments_dict.get("contents")
                    print(f"{self.__class__.__name__}: Updating artifacts: {filename} inside agent") 
                    
                    if filename and contents:
                        os.makedirs("artifacts", exist_ok=True)
                        with open(os.path.join("artifacts", filename), "w") as file:
                            file.write(contents)
                        
                        # Add a message to the message history
                        message_history.append({"role": "system", "content": f"The artifact '{filename}' was updated."})
                        copied_message_history.append({"role": "system", "content": f"The artifact '{filename}' was updated."})
                        response_message, function_data = await self.handle_tool_calls(message_history, call_tools=False)
                        print(f"{self.__class__.__name__}: Function data after updating artifact: ", function_data)
                        print(f"{self.__class__.__name__}: Response text after updating artifact: ", response_message.content)
                        if response_message.content:
                            message_history.append({"role": "assistant", "content": response_message.content})
                            copied_message_history.append({"role": "assistant", "content": response_message.content})
                            cl.user_session.set("message_history", message_history)

        else:
            print("No tool call")

        

        return response_message.content


