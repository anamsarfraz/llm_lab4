import os
import json

from agents.base_agent import Agent
from agents.planning_agent import PlanningAgent
from agents.implementation_agent import ImplementationAgent

import chainlit as cl

from langfuse.openai import AsyncOpenAI

PLANNING_PROMPT = """\
You are a software architect, preparing to build the web page in the image that the user sends. 
Once they send an image, generate a plan, described below, in markdown format.

If the user or reviewer confirms the plan is good, use the available tools to save it as an artifact \
called `plan.md`. If the user has feedback on the plan, revise the plan, and save it using \
the tool again. A tool is available to update the artifact. Your role is only to plan the \
project. You will not implement the plan, and will not write any code in the plan.

If the plan has already been saved, no need to save it again unless there is feedback. Do not \
use the tool again if there are no changes.

For the contents of the markdown-formatted plan, create two sections, "Overview" and "Milestones".

In a section labeled "Overview", analyze the image, and describe the elements on the page, \
their positions, and the layout of the major sections.

Using vanilla HTML and CSS, discuss anything about the layout that might have different \
options for implementation. Review pros/cons, and recommend a course of action.

In a section labeled "Milestones", describe an ordered set of milestones for methodically \
building the web page, so that errors can be detected and corrected early. Pay close attention \
to the aligment of elements, and describe clear expectations in each milestone. Do not include \
testing milestones, just implementation.

Milestones should be formatted like this:

 - [ ] 1. This is the first milestone
 - [ ] 2. This is the second milestone
 - [ ] 3. This is the third milestone
"""


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

client = AsyncOpenAI()

# Create an instance of the Agent class
planning_agent = PlanningAgent(name="Planning Agent", client=client, prompt=PLANNING_PROMPT)
implementation_agent = ImplementationAgent(name="Implementation Agent", client=client, prompt=IMPLEMENTATION_PROMPT)


class SupervisorAgent(Agent):

    tools = [
        {
            "type": "function",
            "function": {
                "name": "callAgent",
                "description": "Call another agent to delegate a task if the user wants to create a plan, callAgent('planning') or implement the plan, callAgent('implementation')",
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
        #print(f"{self.__class__.__name__}: Function data: ", function_data)
        #print(f"{self.__class__.__name__}: Response text: ", response_message.content)
                
        if response_message.content:
            message_history.append({"role": "assistant", "content": response_message.content})
            copied_message_history.append({"role": "assistant", "content": response_message.content})
            cl.user_session.set("message_history", message_history)

        #print(f"DEBUG: function_data: {function_data}")
        while function_data:
            print(f"{self.__class__.__name__}: Received Function data just inside while loop: ", function_data)
            for index, index_data in function_data.items():
                if "callAgent" == index_data["name"]:
                    arguments_dict = json.loads(index_data["arguments"])
                    agent_name = arguments_dict.get("agent_name")
                    print(f"{self.__class__.__name__}: Calling {agent_name} agent from supervisor agent")
                    if agent_name == 'planning':

                        await planning_agent.execute(message_history)
                    elif agent_name == "implementation":
                        message_history.append({"role": "system", "content": f"Implement the next milestone that has not been implemented yet. Start from milestone 1."})
                        await implementation_agent.execute(message_history)

                        message_history.append({"role": "system", "content": "Proceed to the next milestone that has not been implemented yet."})
                        copied_message_history.append({"role": "system", "content": "Proceed to the next milestone that has not been implemented yet."})
                        
            response_message, function_data = await self.handle_tool_calls(copied_message_history)
            print(f"{self.__class__.__name__}: Function data in loop: ", function_data)
            print(f"{self.__class__.__name__}: Response text in loop: ", response_message.content)
            if response_message.content:
                message_history.append({"role": "assistant", "content": response_message.content})
                copied_message_history.append({"role": "assistant", "content": response_message.content})
                cl.user_session.set("message_history", message_history)
        else:
            print("No tool call")
        
