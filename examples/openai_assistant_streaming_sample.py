import requests
from openai import OpenAI
from typing_extensions import override
from openai import AssistantEventHandler
import json

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

# Custom function to handle API call
def fetch_membership_price(membership_type):
    url = "https://kno2getherworkflow.ddns.net/webhook/fetchMemberShip"
    headers = {
        "Authorization": "Bearer YOUR_API_KEY",  # Replace with your actual API key
        "Content-Type": "application/json"
    }
    payload = {
        "membership": membership_type
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        return data.get("price", "Price not available")
    else:
        return "Error fetching the membership price."

# Step 4: Create and Stream a Run with Tool Handling
class EventHandler(AssistantEventHandler):
    def __init__(self):
        super().__init__()  # Properly initialize the parent class
        self.partial_sentence = ""

    @override
    def on_text_created(self, text) -> None:
        print(f"\nassistant > ", end="", flush=True)

    @override
    def on_text_delta(self, delta, snapshot):
        print(delta.value, end="", flush=True)

    @override
    def on_tool_call_created(self, tool_call):
        print(f"\nassistant > Tool Call Detected: {tool_call.type}\n", flush=True)
        
        # Log the entire tool call for debugging
        arguments = json.loads(tool_call.function.arguments)
        print("Tool Call Content:", arguments)
        
        if tool_call.type == "function" and tool_call.function.name == "fetchMembershipPrice":
            # Log the arguments
            print(f"Arguments received: {tool_call.function.arguments}")

            # Check if the arguments are present
            membership_type = tool_call.function.arguments.get("membership", None)
            if membership_type is None:
                print("No membership argument provided.")
                return

            price = fetch_membership_price(membership_type)
            
            # Provide the result back to the assistant
            client.beta.threads.messages.create(
                thread_id=snapshot.thread_id,
                role="assistant",
                content=f"The price for {membership_type} is ${price}."
            )

    def on_tool_call_delta(self, delta, snapshot):
        pass  # Handle streaming tool results here if needed

def create_and_stream_run(thread_id, assistant_id, instructions=None):
    with client.beta.threads.runs.stream(
        thread_id=thread_id,
        assistant_id=assistant_id,
        instructions=instructions,
        event_handler=EventHandler(),
    ) as stream:
        stream.until_done()

# Define the API tool with the correct structure
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
                    "description": "The type of gym membership to fetch the price for",
                    "enum": [
                        "Silver-Gym-Membership",
                        "Gold-Gym-Membership",
                        "Platinum-Gym-Membership"
                    ],
                    "example": "Gold-Gym-Membership"
                }
            },
            "required": ["membership"],
            "additionalProperties": False
        }
    }
}

# Main Workflow
if __name__ == "__main__":
    # Step 1: Create Assistants with the tool
    customer_service_id = create_assistant(
        name="Customer Service",
        instructions="You are a customer service assistant. Help with billing and account-related queries. If a user asks about membership pricing, use the fetchMembershipPrice function.",
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

    # Step 3: Add a Message to the Thread - Sales Inquiry
    add_message_to_thread(thread_id, "I'm interested in your premium service. Can you tell me more about the Gold membership price?")

    # Step 4: Run the Customer Service Assistant (where the tool is defined)
    print("\n--- Running Sales Assistant ---")
    create_and_stream_run(thread_id, customer_service_id)
