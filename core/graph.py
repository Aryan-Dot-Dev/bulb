from langgraph.graph import StateGraph, START, END

from core.state import State

from agents.pm.agent import pm_agent
from agents.questions.agent import questions_agent
from agents.pm_refine.agent import pm_refine_agent
from agents.wireframe.agent import wireframe_agent
from agents.db.agent import db_agent
from agents.architect.agent import architect_agent
from agents.security.agent import security_agent

# First graph: Generate questions
questions_workflow = StateGraph(State)
questions_workflow.add_node("pm", pm_agent)
questions_workflow.add_node("questions", questions_agent)

questions_workflow.add_edge(START, "pm")
questions_workflow.add_edge("pm", "questions")
questions_workflow.add_edge("questions", END)
questions_app = questions_workflow.compile()

# Second graph: Refine and wireframe
refinement_workflow = StateGraph(State)
refinement_workflow.add_node("pm_refine", pm_refine_agent)
refinement_workflow.add_node("architect", architect_agent)
refinement_workflow.add_node("db", db_agent)
refinement_workflow.add_node("security", security_agent)
refinement_workflow.add_node("wireframe", wireframe_agent)

refinement_workflow.add_edge(START, "pm_refine")
refinement_workflow.add_edge("pm_refine", "architect")
refinement_workflow.add_edge("architect", "db")
refinement_workflow.add_edge("db", "security")
refinement_workflow.add_edge("security", "wireframe")
refinement_workflow.add_edge("wireframe", END)

refinement_app = refinement_workflow.compile()