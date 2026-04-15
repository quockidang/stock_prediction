import asyncio
import semantic_kernel as sk
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

async def main():
    # Initialize the kernel
    kernel = sk.Kernel()

    # Get OpenAI credentials from environment variables
    api_key = os.getenv("OPENAI_API_KEY")
    org_id = os.getenv("OPENAI_ORG_ID") # Optional
    model_id = os.getenv("OPENAI_CHAT_MODEL_ID", "gpt-3.5-turbo")

    if not api_key:
        print("❌ Please set your OPENAI_API_KEY in the .env file.")
        return

    # Add OpenAI Chat Completion service
    kernel.add_service(
        OpenAIChatCompletion(
            service_id="chat-gpt",
            ai_model_id=model_id,
            api_key=api_key,
            org_id=org_id
        )
    )

    # Example 1: Creating a simple semantic function
    prompt = "Tell me a joke about {{ $input }}."
    joke_function = kernel.create_function_from_prompt(
        function_name="JokeFunction",
        plugin_name="JokePlugin",
        prompt=prompt,
    )

    # Run the function
    print("🤖 Kernel is ready! Let's try a joke...")
    result = await kernel.invoke(joke_function, input="Python programming")
    print(f"\nJoke: {result}")

    # Example 2: Prompt with multiple variables
    summary_prompt = """
    Summarize the following text in 3 bullet points:
    {{ $input }}
    """
    summary_function = kernel.create_function_from_prompt(
        function_name="SummaryFunction",
        plugin_name="SummaryPlugin",
        prompt=summary_prompt
    )

    text_to_summarize = """
    Semantic Kernel is an SDK that integrates Large Language Models (LLMs) like OpenAI, Azure OpenAI, and Hugging Face 
    with conventional programming languages like C#, Python, and Java. 
    It allows developers to create AI-powered applications that can use templates, plugins, and planners 
    to automate complex tasks.
    """
    
    print("\n🤖 Summarizing text...")
    summary_result = await kernel.invoke(summary_function, input=text_to_summarize)
    print(f"\nSummary:\n{summary_result}")

if __name__ == "__main__":
    asyncio.run(main())
