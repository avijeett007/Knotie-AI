import json
import tiktoken
import numpy as np
from collections import defaultdict
from openai import OpenAI
import os
import time

# Initialize the OpenAI client
client = OpenAI(api_key='Your API KEY here..')

# Path to your local JSONL dataset file
dataset_path = './BHealthy/BHealthy_data.jsonl'
# dataset_path = './BHealthy/BHealth_tool_calling_data.jsonl'
# Load the dataset
with open(dataset_path, 'r', encoding='utf-8') as f:
    dataset = [json.loads(line) for line in f]

# Initial dataset stats
print("Num examples:", len(dataset))
print("First example:")
for message in dataset[0]["messages"]:
    print(message)

# Format error checks
format_errors = defaultdict(int)

for ex in dataset:
    if not isinstance(ex, dict):
        format_errors["data_type"] += 1
        continue
        
    messages = ex.get("messages", None)
    if not messages:
        format_errors["missing_messages_list"] += 1
        continue
        
    for message in messages:
        if "role" not in message or "content" not in message:
            format_errors["message_missing_key"] += 1
        
        if any(k not in ("role", "content", "name", "function_call", "weight") for k in message):
            format_errors["message_unrecognized_key"] += 1
        
        if message.get("role", None) not in ("system", "user", "assistant", "function"):
            format_errors["unrecognized_role"] += 1
            
        content = message.get("content", None)
        function_call = message.get("function_call", None)
        
        if (not content and not function_call) or not isinstance(content, str):
            format_errors["missing_content"] += 1
    
    if not any(message.get("role", None) == "assistant" for message in messages):
        format_errors["example_missing_assistant_message"] += 1

if format_errors:
    print("Found errors:")
    for k, v in format_errors.items():
        print(f"{k}: {v}")
else:
    print("No errors found")

# Token Counting Utilities
encoding = tiktoken.get_encoding("cl100k_base")

# not exact!
# simplified from https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
def num_tokens_from_messages(messages, tokens_per_message=3, tokens_per_name=1):
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3
    return num_tokens

def num_assistant_tokens_from_messages(messages):
    num_tokens = 0
    for message in messages:
        if message["role"] == "assistant":
            num_tokens += len(encoding.encode(message["content"]))
    return num_tokens

def print_distribution(values, name):
    print(f"\n#### Distribution of {name}:")
    print(f"min / max: {min(values)}, {max(values)}")
    print(f"mean / median: {np.mean(values)}, {np.median(values)}")
    print(f"p5 / p95: {np.quantile(values, 0.1)}, {np.quantile(values, 0.9)}")

# Warnings and tokens counts
n_missing_system = 0
n_missing_user = 0
n_messages = []
convo_lens = []
assistant_message_lens = []

for ex in dataset:
    messages = ex["messages"]
    if not any(message["role"] == "system" for message in messages):
        n_missing_system += 1
    if not any(message["role"] == "user" for message in messages):
        n_missing_user += 1
    n_messages.append(len(messages))
    convo_lens.append(num_tokens_from_messages(messages))
    assistant_message_lens.append(num_assistant_tokens_from_messages(messages))
    
print("Num examples missing system message:", n_missing_system)
print("Num examples missing user message:", n_missing_user)
print_distribution(n_messages, "num_messages_per_example")
print_distribution(convo_lens, "num_total_tokens_per_example")
print_distribution(assistant_message_lens, "num_assistant_tokens_per_example")
n_too_long = sum(l > 16385 for l in convo_lens)
print(f"\n{n_too_long} examples may be over the 16,385 token limit, they will be truncated during fine-tuning")

# Pricing and default n_epochs estimate
MAX_TOKENS_PER_EXAMPLE = 16385

TARGET_EPOCHS = 10
MIN_TARGET_EXAMPLES = 100
MAX_TARGET_EXAMPLES = 25000
MIN_DEFAULT_EPOCHS = 1
MAX_DEFAULT_EPOCHS = 25

n_epochs = TARGET_EPOCHS
n_train_examples = len(dataset)
if n_train_examples * TARGET_EPOCHS < MIN_TARGET_EXAMPLES:
    n_epochs = min(MAX_DEFAULT_EPOCHS, MIN_TARGET_EXAMPLES // n_train_examples)
elif n_train_examples * TARGET_EPOCHS > MAX_TARGET_EXAMPLES:
    n_epochs = max(MIN_DEFAULT_EPOCHS, MAX_TARGET_EXAMPLES // n_train_examples)

n_billing_tokens_in_dataset = sum(min(MAX_TOKENS_PER_EXAMPLE, length) for length in convo_lens)
print(f"Dataset has ~{n_billing_tokens_in_dataset} tokens that will be charged for during training")
print(f"By default, you'll train for {n_epochs} epochs on this dataset")
print(f"By default, you'll be charged for ~{n_epochs * n_billing_tokens_in_dataset} tokens")

# Function to estimate cost
def estimate_cost(total_tokens, epochs, cost_per_token=0.00006):  # Example cost per token
    return total_tokens * epochs * cost_per_token

# Function to upload the dataset
def upload_dataset(file_path):
    response = client.files.create(
        file=open(file_path, 'rb'),
        purpose='fine-tune'
    )
    file_id = response.id
    print(f"Uploaded file ID: {file_id}")
    return file_id

# Function to create a fine-tuning job
def create_fine_tuning_job(file_id, model_name='gpt-3.5-turbo', epochs=10):
    response = client.fine_tuning.jobs.create(
        training_file=file_id,
        model=model_name,
        hyperparameters={
            "n_epochs":2
        }
    )
    fine_tune_id = response.id
    print(f"Fine-tune job ID: {fine_tune_id}")
    return fine_tune_id

# Function to monitor the fine-tuning job
def monitor_fine_tuning_job(fine_tune_id):
    response = client.fine_tuning.jobs.retrieve(fine_tune_id)
    status = response.status
    print(f"Fine-tuning status: {status}")
    return response

# Function to use the fine-tuned model
def use_fine_tuned_model(model_name, prompt, max_tokens=150):
    response = client.completions.create(
        model=model_name,
        prompt=prompt,
        max_tokens=max_tokens
    )
    print(response.choices[0].text)
    return response.choices[0].text

# Function to calculate dataset tokens
def calculate_dataset_tokens(file_path):
    total_tokens = 0
    with open(file_path, 'r') as file:
        for line in file:
            data = json.loads(line)
            for message in data['messages']:
                total_tokens += num_tokens_from_messages([message])
            if 'response' in data:
                response_text = json.dumps(data['response'])
                total_tokens += num_tokens_from_messages([{'content': response_text, 'role': 'assistant'}])
    return total_tokens

# Main function to orchestrate the fine-tuning process
def main():
    # Calculate the number of tokens in the dataset
    total_tokens = calculate_dataset_tokens(dataset_path)
    print(f"Total tokens in the dataset: {total_tokens}")

    # Estimate the cost
    epochs = 10  # Define the number of epochs
    estimated_cost = estimate_cost(total_tokens, epochs)
    print(f"Estimated cost for fine-tuning: ${estimated_cost:.2f}")

    # Confirm if the user wants to proceed
    proceed = input("Do you want to proceed with fine-tuning? (yes/no): ")
    if proceed.lower() != 'yes':
        print("Fine-tuning aborted.")
        return

    # Upload the dataset
    file_id = upload_dataset(dataset_path)

    # Create the fine-tuning job
    fine_tune_id = create_fine_tuning_job(file_id, epochs=epochs)

    # Monitor the fine-tuning job until completion
    while True:
        response = monitor_fine_tuning_job(fine_tune_id)
        if response.status in ['succeeded', 'failed']:
            break
        time.sleep(60)  # Wait for 1 minute before checking the status again

    if response.status == 'succeeded':
        # Use the fine-tuned model
        fine_tuned_model = response.fine_tuned_model
        prompt = "Your custom prompt here"
        use_fine_tuned_model(fine_tuned_model, prompt)
    else:
        print("Fine-tuning job did not succeed.")

# Run the main function
if __name__ == '__main__':
    main()
