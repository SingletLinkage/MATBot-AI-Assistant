from typing import List, Dict
import numpy as np
from sentence_transformers import SentenceTransformer
import os
from dotenv import load_dotenv
import sys
sys.path.append('/home/arka/Desktop/Hackathons/HCLTech_CS671')
from utils import gemini_wrapper as gw

load_dotenv()

embedder = SentenceTransformer('all-MiniLM-L6-v2')

def get_statements(answer: str, question: str) -> List[str]:
    """Extract statements from the answer using Gemini."""
    prompt = f"""
Your task is to extract **precise standalone factual statements** from the given **answer**.
 Very strict rules:
- Each statement **must be directly present in the answer** (verbatim or minimal rephrasing).
- Do NOT add any external knowledge or inferred information.
- Do NOT include any EXPLANATION, notes, or any text outside the factual statements.
- Just return the statements as a list, one per line, like: [statement 1, statement 2, ...]

Only include statements that are **fully supported by the answer** itself.

---

Question: {question}

Answer: {answer}
"""

    response = gw.universal_agent(
        prompt,
        "",    # No system prompt
        model="gemini-2.0-flash"
    )
    # extracted = response.strip()
    # statements = [line.strip() for line in extracted.split("\n") if line.strip()]
    return response


def verify_statements(statements: List[str], context: str) -> List[bool]:
    """Verify each statement using Gemini, check if supported by context."""

    verification_prompt = """Consider the given context and following statements, then determine whether they are supported by the information present in the context. Provide a verdict (True/False) without any explanation. Format to be followed is:
    {
        "statement 1": True/False,
        "statement 2": True/False, ...
    }
    Do not deviate from the specified format.\n\n"""

    for i, stmt in enumerate(statements):
        verification_prompt += f"statement {i+1}: {stmt}\n"

    verification_prompt += f"\ncontext:\n{context}"

    response = gw.universal_agent(
        verification_prompt,
        "",    # No system prompt
        model="gemini-2.0-flash"
    )

    verdicts = response.values()
    return verdicts


def generate_questions(answer: str, n: int = 3) -> List[str]:
    """Generate questions from the answer using Gemini."""
    generated_questions = []
    for _ in range(n):
        prompt = "Generate a question for the given answer. In format: {'question': 'your  generated question'}\n\n" + f"answer: {answer}"
        response = gw.universal_agent(
            prompt,
            "",    # No system prompt
            model="gemini-2.0-flash"
        )       
        # print(response)
        generated_questions.append(response['question'])
    return generated_questions


def get_embedding(text: str) -> np.ndarray:
    """Get embedding using SentenceTransformers locally."""
    embedding = embedder.encode(text)
    return np.array(embedding)


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))


def extract_relevant_sentences(context: str, question: str) -> List[str]:
    """Extract relevant sentences from context using Gemini."""
    prompt = f"""
Please extract relevant sentences from the provided context that can potentially help answer the following question. If no relevant sentences are found, or if you believe the question cannot be answered from the given context, return the phrase "Insufficient Information". While extracting candidate sentences you're not allowed to make any changes to sentences from given context. Format: ['sentence 1', 'sentence 2', ...]

question: {question}
context:
{context}
"""
    response = gw.universal_agent(
        prompt,
        "",    # No system prompt
        model="gemini-2.0-flash"
    )

    return response


def evaluate_ragas(answer: str, context: str, question: str) -> Dict[str, float]:
    """
    Main function to evaluate using Ragas methodology with Gemini + local embeddings.

    Returns a dictionary with:
    - faithfulness score
    - answer relevance score
    - context relevance score
    """
    # print("get_statements()")
    statements = get_statements(answer, question)
    if not statements:
        faithfulness_score = 0.0
    else:
        # print("verify_statements()")
        verdicts = verify_statements(statements, context)
        faithfulness_score = sum(verdicts) / len(verdicts)

    # Answer Relevance
    # print("generate_questions()")
    generated_qs = generate_questions(answer, n=3)
    # print("get_embedding()")
    question_emb = get_embedding(question)
    similarities = []
    for gen_q in generated_qs:
        gen_emb = get_embedding(gen_q)
        sim = cosine_similarity(question_emb, gen_emb)
        similarities.append(sim)
    answer_relevance_score = np.mean(similarities) if similarities else 0.0

    # Context Relevance
    # print("extract_relevant_sentences()")
    context_sentences = [sent.strip() for sent in context.split(".") if sent.strip()]
    extracted_sentences = extract_relevant_sentences(context, question)
    if not context_sentences:
        context_relevance_score = 0.0
    else:
        context_relevance_score = len(extracted_sentences) / len(context_sentences)

    return {
        "faithfulness": round(float(faithfulness_score), 3),
        "answer_relevance": round(float(answer_relevance_score), 3),
        "context_relevance": round(float(context_relevance_score), 3),
    }


# Example use:
if __name__ == "__main__":
    answer = "Christopher Nolan directed Oppenheimer, and Cillian Murphy starred as J. Robert Oppenheimer."
    context = "Oppenheimer is a 2023 biographical thriller film written and directed by Christopher Nolan. Based on the 2005 biography American Prometheus by Kai Bird and Martin J. Sherwin, the film chronicles the life of J. Robert Oppenheimer, a theoretical physicist who was pivotal in developing the first nuclear weapons as part of the Manhattan Project, and thereby ushering in the Atomic Age. Cillian Murphy stars as Oppenheimer."
    question = "Who directed the film Oppenheimer and who stars as J. Robert Oppenheimer in the film?"

    result = evaluate_ragas(answer, context, question)
    print(result)
