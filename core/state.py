from typing import TypedDict

class State(TypedDict):
    user_prompt: str
    requirements_docs: str
    wireframe: str
    questions: list[str]
    user_answers: str
    security_docs: str
    architect: str
    db: str