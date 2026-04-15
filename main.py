import json
import asyncio
import aiofiles

from core.graph import questions_app, refinement_app


async def collect_answers(questions):
    """Collect user answers interactively"""
    answers = []
    for i, q in enumerate(questions, 1):
        print(f"\n[Question {i}/{len(questions)}]")
        
        # Handle both string and dict question formats
        question_text = q['question'] if isinstance(q, dict) else q
        options = q.get('options', []) if isinstance(q, dict) else []
        
        print(question_text)
        
        # Show options if available
        if options:
            for j, opt in enumerate(options, 1):
                print(f"  {j}. {opt}")
            answer = input("Your answer (number or text): ").strip()
        else:
            answer = input("Your answer: ").strip()
        
        answers.append(f"Q{i}: {answer}")
    
    return "\n".join(answers)

async def populate_state(result):
    async with aiofiles.open('outputs/requirements_docs.md', 'w', encoding='utf-8') as f:
        await f.write(json.dumps(result))

    async with aiofiles.open('outputs/req.md', 'w', encoding='utf-8') as f:
        await f.write(result['requirements_docs'])

    async with aiofiles.open('outputs/wireframe.md', 'w', encoding='utf-8') as f:
        await f.write(result['wireframe'])
    
    async with aiofiles.open('outputs/architect_design.md', 'w', encoding='utf-8') as f:
        await f.write(result['architect'])

    async with aiofiles.open('outputs/db_schema.md', 'w', encoding='utf-8') as f:
        await f.write(result['db'])

    async with aiofiles.open('outputs/security_report.md', 'w', encoding='utf-8') as f:
        await f.write(result['security_docs'])

async def main():
    userInput: str = input("Enter your project requirements: ")
    
    # Step 1: Generate questions    
    result = questions_app.invoke({'user_prompt': "I want a simple web app where a user can paste a sensitive secret (like an API key or a password), click a button, and get a unique link. Once that link is opened by someone, the secret is shown once and then permanently deleted forever."})

    # Step 2: Collect answers
    print("\n" + "="*50)
    print("ANSWERING QUESTIONS:")
    print("="*50)
    user_answers = await collect_answers(result['questions'])

    # Step 3: Refine and generate wireframe
    result = refinement_app.invoke({
        **result,
        'user_answers': user_answers
    })

    await populate_state(result)

if __name__ == "__main__":
    asyncio.run(main())
