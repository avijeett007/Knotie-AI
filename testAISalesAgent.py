from ai_helpers import process_initial_message, process_message, initiate_inbound_message
from appUtils import clean_response,save_message_history
import uuid
import redis
import time
import json
import logging

# Initial customer details
customer_name = "John Doe"
customer_problem = "Looking for a gym membership to address back pain"
unique_id = str(uuid.uuid4())

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# # Initialize Message History array to save the conversation
message_history = []

redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
initial_transcript = "Customer Name:" + customer_name + ". Customer filled up details in the website:" + customer_problem
message_history.append({"role": "user", "content": initial_transcript})


# # Generate initial message
initial_response = process_initial_message(unique_id, customer_name, customer_problem)
print("Initial Response:", initial_response)
initial_message=clean_response(initial_response)
message_history.append({"role": "assistant", "content": initial_message})
save_message_history(unique_id, message_history)

# # Display initial AI response
print("Assistant Response:", initial_response)

while True:
    user_input = input("Your response: ")
    message_history.append({"role": "user", "content": user_input})
    start_time = time.time()
    # Generate the assistant's response based on user input and message history
    response_text = process_message(unique_id, message_history, user_input)
    assistant_response = clean_response(response_text)
    
    # Append the assistant's response to the message history
    message_history.append({"role": "assistant", "content": assistant_response})
    
    # Check if the current assistant response contains 'END_OF_CALL'
    if "<END_OF_CALL>" in assistant_response:
        print("Assistant Response:", assistant_response)
        print("The conversation has ended.")
        break
    # Print the assistant's response
    print("Assistant Response:", assistant_response)
    end_time = time.time()
    elapsed_time_ms = (end_time - start_time) * 1000
    logger.info(f"Elapsed latency by AI Model for producing response: {elapsed_time_ms:.2f} ms")
