from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI


load_dotenv()


def get_llm() -> ChatGoogleGenerativeAI:
    """Create the Gemini chat model used by LLM-powered agents."""

    return ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        temperature=0.3,
    )
