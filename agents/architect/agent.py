from langchain_core.messages import HumanMessage, SystemMessage

from core.llm import thinking_llm

from .prompt import prompt
from core.state import State

def architect_agent(state: State):
    print("Compiling Production Architecture...")
    userPrompt = state['requirements_docs']

    sys_msg = SystemMessage(content=prompt)

    
    # Collect streamed chunks
    full_response = ""
    for chunk in thinking_llm.stream([sys_msg, HumanMessage(content=userPrompt)]):
        if chunk.content:
            # print(chunk.content, end="", flush=True)
            full_response += chunk.content
    # print()  # newline
    
    return {'architect': full_response}