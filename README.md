# SimuBot: Simulink Real-Time Troubleshooting Assistant

## Overview

SimuBot is an intelligent assistant for troubleshooting Simulink Real-Time issues. The application leverages RAG (Retrieval-Augmented Generation) architecture and LLM models to provide accurate, contextual solutions to common Simulink Real-Time problems by drawing from MathWorks documentation.

## Features

- **AI-Powered Debugging Assistance**: Identifies and resolves Simulink Real-Time errors with step-by-step solutions
- **Semantic Clustering**: Organizes technical documentation into relevant clusters for better retrieval
- **Interactive Chat Interface**: User-friendly Streamlit-based chat interface with real-time feedback
- **Model Customization**: Select between different Gemini models with configurable system prompts
- **Response Evaluation**: Automatic quality assessment of AI responses with detailed feedback
- **Structured Content Output**: Presents solutions in an easy-to-follow format with problem summary, root cause, and resolution

## Architecture

The application follows a modular architecture:

1. **Data Collection & Processing**:
   - Web scraping of Simulink Real-Time documentation (`scrapL1.py`, `individualLinkScrap.py`)
   - HTML to structured JSON conversion (`structurify.py`)

2. **Knowledge Base**:
   - Semantic clustering of documents (`clustering.py`)
   - FAISS vector index for efficient similarity search

3. **RAG Engine**:
   - Query processing
   - Relevant document retrieval
   - Context-enhanced generation

4. **Agent System**:
   - Debugger agent for problem-solving (`debugger_agent.py`)
   - Evaluator agent for quality assessment (`evaluator_agent.py`)

5. **User Interface**:
   - Streamlit web application (`streamlit_chat_app.py`)
   - Groq API integration for specific generation tasks (`app_1.py`)

## Technical Stack

- **Python 3.10+**
- **Machine Learning**: scikit-learn, sentence-transformers, FAISS
- **LLM APIs**: Google Gemini, Groq (llama3)
- **Web Framework**: Streamlit
- **Data Processing**: BeautifulSoup, pandas
- **Vector Database**: FAISS (Facebook AI Similarity Search)

## Getting Started

### Prerequisites

- Python 3.10+
- API keys for Google Gemini and Groq

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/simubot.git
   cd simubot
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   - Create a `.env` file in the project root
   - Add your API keys:
     ```
     GEMINI_API_KEY=your_gemini_api_key
     GROQ_API_KEY=your_groq_api_key
     ```

### Running the Application

Launch the chat interface:
```bash
streamlit run streamlit_chat_app.py
```

## Usage

1. Enter your Simulink Real-Time troubleshooting query in the chat input
2. The system will:
   - Retrieve relevant documentation from the knowledge base
   - Generate a structured response with problem analysis and solution
   - Evaluate the quality of the response
3. Use the model parameters sidebar to configure the LLM before starting the chat

## Project Structure

- `/agents/`: LLM agent implementations
- `/utils/`: Utility functions and wrappers for LLM APIs
- `/corpus/`: Processed knowledge base (generated)
- `structurify.py`: HTML processing utilities
- `clustering.py`: Document clustering implementation
- `streamlit_chat_app.py`: Main chat application
- `app_1.py`: Alternative application using Groq API
- `requirements.txt`: Project dependencies

## Future Improvements

- Expanded knowledge base with additional Simulink documentation
- Integration with MATLAB for direct code analysis
- User feedback-based continuous learning
- Support for more LLM providers
- Enhanced visualization of technical solutions

## License

This project was created as part of the HCL Tech CS671 Hackathon.
