from langchain_core.messages import HumanMessage, SystemMessage

from core.llm import thinking_llm

from .prompt import prompt
from core.state import State

def pm_refine_agent(state: State):
    print("Refining Project Management...")
    userPrompt = state['user_answers']
    questionsAsked = state['questions']

    sys_msg = SystemMessage(content=prompt)

    # Collect streamed chunks
    full_response = ""
    for chunk in thinking_llm.stream([sys_msg, HumanMessage(content="userAnswers: " + userPrompt + "\n\nquestionsAsked: " + "\n".join(questionsAsked))]):
        if chunk.content:
            full_response += chunk.content
    
    return {'requirements_docs': full_response}