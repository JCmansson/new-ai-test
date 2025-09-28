import os
from xai_sdk import Client
from xai_sdk.chat import user


def refactor_file_interactively(file_path, client, model="grok-4-latest"):
    try:
        # Read the Python file
        with open(file_path, "r") as file:
            code = file.read()

        # Initialize chat session
        chat = client.chat.create(model=model)
        output_dir = "utils_refactored"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, os.path.basename(file_path))

        # Initial refactoring prompt
        initial_prompt = (
            f"Phase1: Analyze the Python files in ´utils/´ directory and check PyCharms analysis in `code-reports/` "
            f"Find the code's patterns and compare them to my ADR in `ai/decided/adr_v3.md`, relationship in `module-dependency-diagram.md`"
            f"Our goal is to refactor the code *.py and make ADR complete with our coding style dicisions`"
            f"Suggest changed and deliver them as to-do.md in a markdown file. : :\n\n{code}"
        )
        chat.append(user(initial_prompt))

        # Get initial response
        response = chat.sample()
        print("\nInitial Refactored Code and Explanation:")
        print(response.content)

        # Save initial refactored code
        with open(output_path, "w") as file:
            file.write(response.content)
        print(f"\nSaved initial refactored code to {output_path}")

        # Continuous discussion loop
        while True:
            print("\nEnter a follow-up prompt (e.g., 'Explain this change', 'Make it more concise')")
            print("or type 'next' to move to the next file, or 'exit' to stop:")
            user_input = input("> ").strip()

            if user_input.lower() == "exit":
                break
            elif user_input.lower() == "next":
                return True  # Signal to process the next file

            # Append follow-up prompt to the chat
            chat.append(user(user_input))
            response = chat.sample()
            print("\nGrok Response:")
            print(response.content)

            # Save updated code (optional, based on user input)
            save = input("\nSave this response to the output file? (y/n): ").strip().lower()
            if save == "y":
                with open(output_path, "w") as file:
                    file.write(response.content)
                print(f"Updated {output_path}")

        return False  # Signal to stop processing files

    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        return True  # Continue to next file on error


def main():
    # Initialize the client
    client = Client(
        api_key=os.getenv("XAI_API_KEY"),
        timeout=3600
    )

    # Directory to refactor
    utils_dir = "utils"

    # Process each Python file
    for filename in sorted(os.listdir(utils_dir)):
        if filename.endswith(".py"):
            file_path = os.path.join(utils_dir, filename)
            print(f"\n=== Processing {file_path} ===")
            continue_to_next = refactor_file_interactively(file_path, client)
            if not continue_to_next:
                break  # Stop if user exits


if __name__ == "__main__":
    main()