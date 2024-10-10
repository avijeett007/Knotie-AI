# This code is licensed under the Custom License for Paid Community Members.
# For more information, see the LICENSE file in the root directory of this repository.
from ConversationCache import CacheManager
from ConversationCache.environment import Configuration
from config import Config
import openai
import anthropic
from groq import Groq
from anthropic import Anthropic
import json
from langchain_core.prompts import PromptTemplate
from prompts import get_prompt_template
from stages import OUTBOUND_CONVERSATION_STAGES, INBOUND_CONVERSATION_STAGES
import logging
import sqlite3
from openapi_spec_validator import validate_spec
import yaml
import importlib
import requests
import sys
import os
# Import tool-related functions
from tools_helper import (
    initialize_tools, 
    get_tool_and_spec, 
    call_api, 
    replace_sensitive_values,
    fetch_tools_from_db,
    initialized_tools
)

sys.path.append(os.path.join(os.path.dirname(__file__), 'generated_tools'))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# session ={} # Added for testing. remove after testing
ai_api_key = Config.AI_API_KEY
salesperson_name = Config.AISALESAGENT_NAME
company_name = Config.COMPANY_NAME
company_business = Config.COMPANY_BUSINESS
conversation_purpose = Config.CONVERSATION_PURPOSE
agent_custom_instructions = Config.AGENT_CUSTOM_INSTRUCTIONS
company_products_services = Config.COMPANY_PRODUCTS_SERVICES
conversation_stages = OUTBOUND_CONVERSATION_STAGES
which_model = Config.WHICH_MODEL
llm_model = Config.LLM_MODEL
# In-memory storage for testing
conversation_states = {}
ai = None
GENERATED_TOOLS_DIR = 'generated_tools/'

if which_model == "GROQ":
    params = {
        "model": llm_model,
        "temperature": 0.5,
        "max_tokens": 100,
        "stream": False,
        "top_p": 1
    }  # params["messages"] = prompt
elif which_model == "OpenAI" or which_model == "OpenRouter":
    params = {
        "model": llm_model,
        "temperature": 0.5,
        "max_tokens": 100,
    }  # params["messages"] = prompt
elif which_model == "Anthropic":
    params = {
        "model": llm_model,
        "temperature": 0.5,
        "max_tokens": 100,
    }


# Example usage:
initialize_tools()


# Method added to reinitialize on updating from UI
def reinitialize_ai_clients():
    global ai
    logger.info(f"Initiating AI client")
    if Config.WHICH_MODEL == "GROQ":
        ai = Groq(api_key=Config.AI_API_KEY)
        params = {
            "model": llm_model,
            "temperature": 0.5,
            "max_tokens": 100,
            "stream": False,
            "top_p": 1
        }        
    elif Config.WHICH_MODEL == "OpenAI" or Config.WHICH_MODEL == "OpenRouter":
        openai.api_key = Config.AI_API_KEY
        openai.base_url = Config.OPENAI_BASE_URL
        params = {
            "model": llm_model,
            "temperature": 0.5,
            "max_tokens": 100,
        }
    elif Config.WHICH_MODEL == "Anthropic":
        ai = Anthropic(api_key=Config.AI_API_KEY)
        params = {
            "model": llm_model,
            "temperature": 0.5,
            "max_tokens": 100,
        }

reinitialize_ai_clients()

def gen_ai_output(prompt, isToolResponse):
    """Generate AI output based on the prompt."""

    print("model selected is: ", which_model)

    if which_model == "OpenAI" or which_model == "OpenRouter":
        params["messages"] = prompt
        if isToolResponse == "no" and Config.OPENAI_FINE_TUNED_MODEL_ID:
            print(f"Fine tuned model selected: {Config.OPENAI_FINE_TUNED_MODEL_ID}")
            params['model'] = Config.OPENAI_FINE_TUNED_MODEL_ID
        if isToolResponse == "yes" and Config.OPENAI_FINE_TUNED_TOOLS_MODEL_ID:
            print(f"Fine tuned model selected for tool calling: {Config.OPENAI_FINE_TUNED_TOOLS_MODEL_ID}")
            params['model'] = Config.OPENAI_FINE_TUNED_TOOLS_MODEL_ID
        response = openai.chat.completions.create(**params)
        return response.choices[0].message.content
    if which_model == "GROQ":
        params["messages"] = prompt
        response = ai.chat.completions.create(**params)
        return response.choices[0].message.content
    elif which_model == "Anthropic":
        system_prompt = None
        # Iterate over the list to find and remove the "system" role message
        filtered_messages = []
        for msg in prompt:
            if msg["role"] == "system":
                params["system"] = msg["content"]
            else:
                filtered_messages.append(msg)
        params["messages"] = filtered_messages
        response = ai.messages.create(**params)

        return response.content[0].text


def is_tool_required(ai_output):
    """Check if the use of a tool is required according to AI's output."""
    try:
        data = json.loads(ai_output)
        return data.get("tool_required") == "yes"
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format in AI output.")


def get_conversation_stage(ai_output):
    """Extract the conversation stage from AI's output."""
    try:
        data = json.loads(ai_output)
        return int(data.get("conversation_stage_id"))
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format in AI output.")


def get_tool_details(ai_output):
    """Retrieve the tool name, operationId, and parameters if a tool is required."""
    if not is_tool_required(ai_output):
        return None, None, None
    try:
        data = json.loads(ai_output)
        tool_name = data.get("tool_name")
        operation_id = data.get("operation_id")
        tool_parameters = data.get("tool_parameters")
        tool_body_parameters = data.get("tool_body_parameters")
        tool_headers = data.get("tool_headers")
        return tool_name, operation_id, tool_parameters, tool_headers, tool_body_parameters
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format in AI output.")


def process_initial_message(call_sid, customer_name, customer_problem):
    initial_prompt_template = get_prompt_template('AGENT_STARTING_PROMPT_TEMPLATE')
    initial_prompt = initial_prompt_template.format(
        salesperson_name=salesperson_name,
        company_name=company_name,
        company_business=company_business,
        conversation_purpose=conversation_purpose,
        conversation_stages=conversation_stages,
        agent_custom_instructions=agent_custom_instructions
    )
    message_to_send_to_ai = [
        {
            "role": "system",
            "content": initial_prompt
        }
    ]
    initial_transcript = "Customer Name:" + customer_name + ". Customer filled up details in the website:" + customer_problem
    message_to_send_to_ai.append({"role": "user", "content": initial_transcript})
    # Initialize conversation state for the customer
    conversation_states[call_sid] = {
        'conversation_stage_id': 1
    }
    isToolResponse = "no"
    response = gen_ai_output(message_to_send_to_ai, isToolResponse)
    return response

def invoke_stage_tool_analysis(message_history, user_input, conversation_stage_id):
    tools_from_db = fetch_tools_from_db()
    tools_description = ""

    for tool in tools_from_db:
        tool_name = tool['name']
        tool_description = f"{tool_name}: {tool['description']}\nAvailable Operations:\n"
        
        operation_ids = initialized_tools[tool_name]['operations']

        for operation_id, operation_details in operation_ids.items():
            tool_description += f"  - {operation_id}: {operation_details['method']} {operation_details['url']}\n"

            tool_info = get_tool_and_spec(tool_name)
            sensitive_headers = json.loads(tool_info.get('sensitive_headers', '{}') or '{}')
            sensitive_body = json.loads(tool_info.get('sensitive_body', '{}') or '{}')

            # Headers
            headers_description = ', '.join([
                f"{header}: {details['type']}" +
                (f" (enum: {details['enum']})" if details['enum'] else "") +
                (" (sensitive)" if header in sensitive_headers else "") +
                (" (mandatory)" if details.get('required') else "")
                for header, details in operation_details['parameters'].get('header', {}).items()
            ])

            # Query Parameters
            query_description = ', '.join([
                f"{param}: {details['type']}" +
                (f" (enum: {details['enum']})" if details['enum'] else "") +
                (" (mandatory)" if details.get('required') else "")
                for param, details in operation_details['parameters'].get('query', {}).items()
            ])

            # Path Parameters
            path_description = ', '.join([
                f"{param}: {details['type']}" +
                (f" (enum: {details['enum']})" if details['enum'] else "") +
                (" (mandatory)" if details.get('required') else "")
                for param, details in operation_details['parameters'].get('path', {}).items()
            ])

            # Body Parameters
            body_description = ', '.join([
                f"{param}: {details['type']}" +
                (f" (enum: {details['enum']})" if details['enum'] else "") +
                (" (sensitive)" if param in sensitive_body else "") +
                (" (mandatory)" if details.get('required') else "")
                for param, details in operation_details['parameters'].get('body', {}).items()
            ])

            if headers_description:
                tool_description += f"    Headers: {headers_description}\n"
            if query_description:
                tool_description += f"    Query Parameters: {query_description}\n"
            if path_description:
                tool_description += f"    Path Parameters: {path_description}\n"
            if body_description:
                tool_description += f"    Body Parameters: {body_description}\n"

        tools_description += tool_description + "\n"
    intent_tool_prompt_template = get_prompt_template('STAGE_TOOL_ANALYZER_PROMPT')
    intent_tool_prompt = intent_tool_prompt_template.format(
        salesperson_name=salesperson_name,
        company_name=company_name,
        company_business=company_business,
        conversation_purpose=conversation_purpose,
        conversation_stage_id=conversation_stage_id,
        conversation_stages=conversation_stages,
        conversation_history=message_history,
        company_products_services=company_products_services,
        user_input=user_input,
        tools=tools_description
    )

    print("Prompt being sent to AI:" + intent_tool_prompt)
    
    message_to_send_to_ai = [
        {
            "role": "system",
            "content": intent_tool_prompt
        }
    ]
    message_to_send_to_ai.append(
        {"role": "user", "content": "You Must Respond in the JSON format specified in the system prompt"})
    isToolResponse = "yes"
    ai_output = gen_ai_output(message_to_send_to_ai, isToolResponse)
    print("AI Tool Model Output:" + ai_output)
    return ai_output


def initiate_inbound_message(call_sid):
    initial_prompt_template = get_prompt_template('AGENT_PROMPT_INBOUND_TEMPLATE')
    initial_response = initial_prompt_template.format(
        salesperson_name=salesperson_name,
        company_name=company_name
    )
    conversation_states[call_sid] = {
        'conversation_stage_id': 1
    }
    return initial_response


def process_message(call_sid, message_history, user_input):
    conversation_state = conversation_states.get(call_sid)
    conversation_stage_id = conversation_state['conversation_stage_id']
    if not conversation_state:
        raise ValueError("Conversation state not found for this conversation")

    print('user said:' + user_input)
    stage_tool_output = invoke_stage_tool_analysis(message_history, user_input, conversation_stage_id)
    stage = get_conversation_stage(stage_tool_output)
    conversation_stage_id = get_conversation_stage(stage_tool_output)
    conversation_state['conversation_stage_id'] = conversation_stage_id
    tool_output = ''
    try:
        if is_tool_required(stage_tool_output):
            print('Tool Required is true')
            tool_name, operation_id, tool_parameters, tool_headers, tool_body_parameters = get_tool_details(stage_tool_output)
            print(f'Tool called: {tool_name}, Operation: {operation_id}, Params: {tool_parameters}, tool_headers: {tool_headers}, tool_body_parameters: {tool_body_parameters}')
            
            # Use the dynamically loaded tool if available
            if tool_name in initialized_tools:
                api_response = call_api(tool_name, tool_parameters, operation_id, tool_headers, tool_body_parameters)
                tool_output = f"Tool {tool_name} executed successfully. Response: {api_response}"
                message_history.append({"role": "api_response", "content": tool_output})

    except ValueError as e:
        tool_output = "Some Error Occured In calling the tools. Ask User if its okay that you callback the user later with answer of the query."

    print("Creating inbound prompt template")
    outbound_prompt_template = get_prompt_template('AGENT_PROMPT_OUTBOUND_TEMPLATE')
    inbound_prompt = outbound_prompt_template.format(
        salesperson_name=salesperson_name,
        company_name=company_name,
        company_business=company_business,
        conversation_purpose=conversation_purpose,
        conversation_stage_id=conversation_stage_id,
        company_products_services=company_products_services,
        conversation_stages=json.dumps(conversation_stages, indent=2),
        conversation_history=json.dumps(message_history, indent=2),
        tools_response=tool_output
    )
    message_to_send_to_ai_final = [
        {
            "role": "system",
            "content": inbound_prompt
        },
        {
            "role": "user",
            "content": user_input
        }
    ]
    isToolResponse = "no"
    # Check if caching is enabled
    if Config.CACHE_ENABLED == 'true':
        conversation_cache = CacheManager()
        cache_result = conversation_cache.search(user_input)
        if cache_result is None:
            talkback_response = gen_ai_output(message_to_send_to_ai_final, isToolResponse)
            conversation_cache.put(user_input, talkback_response)
            return talkback_response
    else:
        talkback_response = gen_ai_output(message_to_send_to_ai_final, isToolResponse)
        return talkback_response

