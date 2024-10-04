import os
import json

from agents.base_agent import Agent
from agents.implementation_agent import ImplementationAgent
import chainlit as cl


IMPLEMENTATION_PROMPT = """\
You are a software engineer, implementing the web pages based on the provided plan.

You should read the artifacts provided to you at the end of this prompt. Your role is to pick and implement ONE milestone at a time.

You will generate both index.html and styles.css files for your implementation of each milestone and mark off the milestone in the plan markdown file.
You will save each file using the tool available to update the artifact. Do not return the implementation to the user. Only update the artifacts with the implementation

After creating the implementation, do the following:
    1. use available tools to save or update both index.html and styles.css in the artifact folder. A tool is available to update the artifacts. 
    2. use the available tools to mark off the milestone in the provided plan in the artifact folder. A tool is available to update the artifacts.

You should also take feedback to fix a milestone. If the implementation has already been saved, no need to save it again unless there is feedback. Do not \
use the tool again if there are no changes.
"""

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
        print(f"{self.__class__.__name__}: Function data: ", function_data)
        print(f"{self.__class__.__name__}: Response text: ", response_message.content)
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
                elif "callAgent" == index_data["name"]:
                    arguments_dict = json.loads(index_data["arguments"])
                    agent_name = arguments_dict.get("agent_name")
                    print(f"{self.__class__.__name__}: Calling {agent_name} agent from planning agent")
                    message_history.append({"role": "system", "content": f"Calling {agent_name} agent."})
                    copied_message_history.append({"role": "system", "content": f"Calling {agent_name} agent."})
                    if agent_name == "implementation":
                        implementation_agent = ImplementationAgent(name="Implementation Agent", client=self.client, prompt=IMPLEMENTATION_PROMPT)
                        await implementation_agent.execute(message_history)
                            
            response_message, function_data = await self.handle_tool_calls(copied_message_history)
            print(f"{self.__class__.__name__}: Function data after function calls: ", function_data)
            print(f"{self.__class__.__name__}: Response text after function calls: ", response_message.content)
            if response_message.content:
                message_history.append({"role": "assistant", "content": response_message.content})
                copied_message_history.append({"role": "assistant", "content": response_message.content})
                cl.user_session.set("message_history", message_history)
            

        else:
            print("No tool call")

        

        return response_message.content


