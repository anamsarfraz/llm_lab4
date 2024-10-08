import os
import json

from agents.base_agent import Agent
import chainlit as cl


class ReviewerAgent(Agent):

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


        response_message, function_data = await self.handle_tool_calls(copied_message_history, call_tools=False)
        #print(f"{self.__class__.__name__}: Function data: ", function_data)
        #print(f"{self.__class__.__name__}: Response text: ", response_message.content)
        print(f"{self.__class__.__name__}: Response from reviewer after reviewing the implementation: {response_message.content}") 
        return response_message.content
