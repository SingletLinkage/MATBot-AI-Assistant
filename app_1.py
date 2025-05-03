import streamlit as st
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
THRESHOLD_SCORE = 0.7  # Threshold for evaluation score (0–1)

# --- Utility Functions ---
def call_groq_llm(query, context):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama3-8b-8192",
        "messages": [
            {"role": "system", "content": context},
            {"role": "user", "content": query}
        ]
    }
    response = requests.post(GROQ_URL, headers=headers, json=payload)
    try:
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error from LLM: {response.text}"
    


def evaluate_output(query, output):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    prompt = (
        "You are an evaluator AI. Rate the helpfulness and correctness of the response given the query.\n"
        f"Query: {query}\nResponse: {output}\n"
        "Give a float score between 0 (bad) to 1 (perfect), and explain briefly why."
    )
    payload = {
        "model": "llama3-8b-8192",
        "messages": [
            {"role": "system", "content": "You are a helpful and strict evaluation assistant."},
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post(GROQ_URL, headers=headers, json=payload)

    try:
        content = response.json()["choices"][0]["message"]["content"]
        score = float([s for s in content.split() if s.replace('.', '', 1).isdigit()][0])
    except Exception as e:
        score = 0.0
        content = f"Failed to parse score. Error: {e}\nResponse: {response.text}"

    return score, content





context = ""



# --- Streamlit App ---
st.title("RAG App")

query = st.text_input("Enter your query", key="query_input")  # Unique key for query input
# Context = st.text_area("Context (optional)", "You are a helpful assistant.", key="context_area")  # Unique key for context

if query:
    st.subheader("Generating Structured Response")

    with st.spinner("Generating Summary..."):
        summary_prompt = f"Given the following query, summarize the problem:\nQuery: {query}"
        summary = call_groq_llm(summary_prompt, context)

    with st.spinner("Identifying Root Cause..."):
        root_cause_prompt = f"Given the following query, identify the most likely root cause:\nQuery: {query}"
        root_cause = call_groq_llm(root_cause_prompt, context)

    with st.spinner("Generating Resolution..."):
        resolution_prompt = f"Given the following query, suggest a resolution step-by-step:\nQuery: {query}"
        resolution = call_groq_llm(resolution_prompt, context)

    final_output = (
        f"### Summary of Problem:\n{summary}\n\n"
        f"### Root Cause:\n{root_cause}\n\n"
        f"### Resolution:\n{resolution}"
    )

    st.subheader("Output")
    st.markdown(final_output)

    with st.spinner("Evaluating structured output..."):
        score, explanation = evaluate_output(query, final_output)

    st.subheader("Evaluation")
    st.write(f"Score: {score:.2f}")
    st.write(explanation)

    if score < THRESHOLD_SCORE:
        st.warning("Score below threshold. Improving response...")
        improved_prompt = (
            f"Improve the following structured response based on this feedback: {explanation}.\n"
            f"Original Query: {query}\nResponse:\n{final_output}"
        )
        with st.spinner("Improving output..."):
            improved_output = call_groq_llm(improved_prompt, context)
        st.subheader("Improved Output")
        st.markdown(improved_output)

    if st.button("👎 Thumbs Down - Improve Manually"):
        st.warning("User requested manual improvement.")
        manual_prompt = (
            f"The user did not like this structured response:\n{final_output}\nPlease try a better one.\n"
            f"Query: {query}"
        )
        with st.spinner("Generating alternative..."):
            retry_output = call_groq_llm(manual_prompt, context)
        st.subheader("Alternative Output")
        st.markdown(retry_output)

