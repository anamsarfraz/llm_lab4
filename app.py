from dotenv import load_dotenv
import chainlit as cl
from agents.supervisor_agent import SupervisorAgent
import base64


load_dotenv()

# Note: If switching to LangSmith, uncomment the following, and replace @observe with @traceable
# from langsmith.wrappers import wrap_openai
# from langsmith import traceable
# client = wrap_openai(openai.AsyncClient())

from langfuse.decorators import observe
from langfuse.openai import AsyncOpenAI
 

SYSTEM_PROMPT = """\
You are a pirate.
"""

SUPERVISOR_PROMPT = """\
You are a software engineer mananger, leading your team to build a web page in the image that the user sends. 
Once they send an image, you need to work with the a software architect to generate a plan and then work with a software engineer
to implement the milestones. These are your goals.

- Work with the software architect to create and save the plan
- Work with a software engineer to implement all the milestones, ONE milestone at a time, in the generated plan

You have available tool to call the right person for completing a task

Use the following format to build the page:
Thought: You should always think about what the user is asking for
Action: contacting someone to help with the task, only use callAgent to do that
ActionInput: only one of 'planning' or 'implementation' to call the right person for the task
Observation: The result of the action once all necessary information is gathered. Start from milestone 1, if the software engineer completes one milestone, ask the engineer to complete the next and repeat this until the last milestone has been implemented
Thought: I now have the task completed
Final Answer: The task has been completed based on the user input. If the planning task is complete i.e plan generated and saved. Then dont call the planning agent again until user asks for another plan.
If all the milestones have been implemented then dont call the implementation agent again until user asks for it.
"""


client = AsyncOpenAI()

# Create an instance of the Agent class
supervisor_agent = SupervisorAgent(name="Supervisor Agent", client=client, prompt=SUPERVISOR_PROMPT)


gen_kwargs = {
    "model": "gpt-4o-mini",
    "temperature": 0.2
}



@observe
@cl.on_chat_start
def on_chat_start():
    message_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    cl.user_session.set("message_history", message_history)

@observe
async def generate_response(client, message_history, gen_kwargs):
    response_message = cl.Message(content="")
    await response_message.send()

    stream = await client.chat.completions.create(messages=message_history, stream=True, **gen_kwargs)
    async for part in stream:
        if token := part.choices[0].delta.content or "":
            await response_message.stream_token(token)
    
    await response_message.update()

    return response_message

@cl.on_message
@observe
async def on_message(message: cl.Message):
    message_history = cl.user_session.get("message_history", [])
    
    # Processing images exclusively
    images = [file for file in message.elements if "image" in file.mime] if message.elements else []

    if images:
        # Read the first image and encode it to base64
        with open(images[0].path, "rb") as f:
            base64_image = base64.b64encode(f.read()).decode('utf-8')
        message_history.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": message.content
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
        })
    else:
        message_history.append({"role": "user", "content": message.content})
    await supervisor_agent.execute(message_history)

if __name__ == "__main__":
    cl.main()
