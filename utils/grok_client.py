import os
from xai_sdk import Client
from xai_sdk.chat import user, image

try:
    # Initialize the client
    client = Client(
        api_key=os.getenv("XAI_API_KEY"),
        timeout=3600  # Long timeout for reasoning models
    )

    # Create a chat session with Grok-4
    chat = client.chat.create(model="grok-4-latest")  # Use the same model as curl

    # Append a user message with an image
    chat.append(
        user(
            "What's in this image?",
            image("https://science.nasa.gov/wp-content/uploads/2023/09/web-first-images-release.png")
        )
    )

    # Get and print the response
    response = chat.sample()
    print("Grok Response:", response.content)

except ValueError as ve:
    print(f"ValueError: {ve}")
except Exception as e:
    print(f"Unexpected error: {e}")