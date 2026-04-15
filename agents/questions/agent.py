import json
from langchain_core.messages import HumanMessage, SystemMessage
from core.llm import thinking_llm
from .prompt import prompt
from core.state import State

def questions_agent(state: State):
    print("Extracting Questions...")
    userPrompt = state['requirements_docs']
    
    sys_msg = SystemMessage(content=prompt)
    full_response = ""
    
    for chunk in thinking_llm.stream([sys_msg, HumanMessage(content=userPrompt)]):
        if chunk.content:
            full_response += chunk.content
    
    # Parse JSON response
    try:
        questions_data = json.loads(full_response)
        questions_list = questions_data.get('questions', [])  # Keep full question objects
    except json.JSONDecodeError:
        # Fallback: create simple question objects
        questions_list = [{"question": q.strip(), "options": []} for q in full_response.split('\n') if q.strip()]
    
    return {'questions': questions_list}