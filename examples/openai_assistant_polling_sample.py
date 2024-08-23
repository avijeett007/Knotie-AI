from openai import OpenAI
from typing_extensions import override
from openai import AssistantEventHandler

# Initialize the OpenAI client
client = OpenAI(api_key="OpenAI API Key")

# Step 1: Create Assistants
def create_assistant(name, instructions, tools, model="gpt-4o-mini"):
    assistant = client.beta.assistants.create(
        name=name,
        instructions=instructions,
        tools=tools,
        model=model,
    )
    print(f"{name} Assistant Created:", assistant)
    return assistant.id

# Step 2: Create a Thread
def create_thread():
    thread = client.beta.threads.create()
    print("Thread Created:", thread)
    return thread.id

# Step 3: Add a Message to the Thread
def add_message_to_thread(thread_id, content):
    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=content
    )
    print("Message Added:", message)
    return message.id

# Step 4: Create and Stream a Run
class EventHandler(AssistantEventHandler):    
    @override
    def on_text_created(self, text) -> None:
        print(f"\nassistant > ", end="", flush=True)

    @override
    def on_text_delta(self, delta, snapshot):
        print(delta.value, end="", flush=True)

    def on_tool_call_created(self, tool_call):
        print(f"\nassistant > {tool_call.type}\n", flush=True)

    def on_tool_call_delta(self, delta, snapshot):
        if delta.type == 'code_interpreter':
            if delta.code_interpreter.input:
                print(delta.code_interpreter.input, end="", flush=True)
            if delta.code_interpreter.outputs:
                print(f"\n\noutput >", flush=True)
                for output in delta.code_interpreter.outputs:
                    if output.type == "logs":
                        print(f"\n{output.logs}", flush=True)

def create_and_stream_run(thread_id, assistant_id, instructions=None):
    with client.beta.threads.runs.stream(
        thread_id=thread_id,
        assistant_id=assistant_id,
        instructions=instructions,
        event_handler=EventHandler(),
    ) as stream:
        stream.until_done()

# Define the API tool based on the OpenAPI spec
membership_price_tool = {
    "type": "function",
    "function": {
        "name": "fetchMembershipPrice",
        "description": "Fetch the price of a gym membership",
        "parameters": {
            "type": "object",
            "properties": {
                "membership": {
                    "type": "string",
                    "enum": [
                        "Silver-Gym-Membership",
                        "Gold-Gym-Membership",
                        "Platinum-Gym-Membership"
                    ],
                    "example": "Gold-Gym-Membership"
                }
            },
            "required": ["membership"]
        },
        "url": "https://kno2getherworkflow.ddns.net/webhook/fetchMemberShip",
        "method": "POST",
        "headers": {
            "Authorization": "Bearer YOUR_API_KEY"  # Replace with your actual API key
        }
    }
}

# Main Workflow
if __name__ == "__main__":
    # Step 1: Create Assistants with the tool
    customer_service_id = create_assistant(
        name="Customer Service",
        instructions="You are a customer service assistant. Help with billing and account-related queries.",
        tools=[membership_price_tool]
    )
    
    it_support_id = create_assistant(
        name="IT Support",
        instructions="You are an IT support assistant. Help with technical issues like password resets, account access, and software troubleshooting.",
        tools=[{"type": "code_interpreter"}]
    )

    sales_id = create_assistant(
        name="Sales",
        instructions="You are a sales assistant. Help users with product inquiries and upsell premium services.",
        tools=[]
    )

    # Step 2: Create a Thread
    thread_id = create_thread()

    # Step 3: Add a Message to the Thread - Customer Service Query
    add_message_to_thread(thread_id, "I have a billing issue.")

    # Step 4: Run the Customer Service Assistant
    print("\n--- Running Customer Service Assistant ---")
    create_and_stream_run(thread_id, customer_service_id)

    # Add a Message to the Thread - IT Support Query
    add_message_to_thread(thread_id, "I'm having trouble logging into my account.")

    # Run the IT Support Assistant
    print("\n--- Running IT Support Assistant ---")
    create_and_stream_run(thread_id, it_support_id)

    # Add a Message to the Thread - Sales Inquiry
    add_message_to_thread(thread_id, "I'm interested in your premium service. Can you tell me more about the Gold membership price?")

    # Run the Sales Assistant
    print("\n--- Running Sales Assistant ---")
    create_and_stream_run(thread_id, customer_service_id)  # Using the customer service assistant to test the tool call
