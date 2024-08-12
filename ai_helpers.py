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
from prompts import AGENT_STARTING_PROMPT_TEMPLATE, STAGE_TOOL_ANALYZER_PROMPT, AGENT_PROMPT_OUTBOUND_TEMPLATE, \
    AGENT_PROMPT_INBOUND_TEMPLATE
from flask import session  # Uncomment it after testing.
from stages import OUTBOUND_CONVERSATION_STAGES, INBOUND_CONVERSATION_STAGES
import logging
import sqlite3
from openapi_spec_validator import validate_spec
import yaml
import importlib
import requests
import sys
import os

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


def fetch_tools_from_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, description, class_name, openapi_spec FROM tools')
    tools = cursor.fetchall()
    conn.close()
    return [{"name": row[0], "description": row[1], "class_name": row[2], "openapi_spec": row[3]} for row in tools]

# Initialize tools dynamically
initialized_tools = {}

def initialize_tools():
    tools_from_db = fetch_tools_from_db()

    for tool in tools_from_db:
        tool_name = tool["name"]
        module_name = f'{tool_name}.client'
        try:
            # Add tool's directory to sys.path
            sys.path.append(os.path.join(GENERATED_TOOLS_DIR, tool_name))
            module = importlib.import_module(module_name)
            ToolClass = getattr(module, 'Client')  # Assuming the generated class is named 'Client'
            initialized_tools[tool["name"]] = ToolClass()
        except ModuleNotFoundError as e:
            logger.error(f"Error initializing tool {tool_name}: {e}")
        except AttributeError as e:
            logger.error(f"Error finding class in module {tool_name}: {e}")


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

def get_tool_and_spec(tool_name):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, description, class_name, openapi_spec FROM tools WHERE name = ?', (tool_name,))
    tool = cursor.fetchone()
    conn.close()
    
    if tool:
        return {
            "name": tool[0],
            "description": tool[1],
            "class_name": tool[2],
            "openapi_spec": tool[3]
        }
    else:
        raise ValueError(f"Tool with name {tool_name} not found")


def get_api_info_from_openapi(openapi_spec, operation_id):
    spec = yaml.safe_load(openapi_spec)

    for path, path_item in spec['paths'].items():
        for operation, operation_item in path_item.items():
            if 'operationId' in operation_item and operation_item['operationId'] == operation_id:
                method = operation.upper()
                url = spec['servers'][0]['url'] + path
                parameters = operation_item.get('parameters', [])
                return method, url, parameters

    raise ValueError(f"Operation ID {operation_id} not found in OpenAPI spec")


def call_api(tool_name, tool_params):
    logger.info(f"Calling tool: {tool_name}")
    print(f"Calling tool: {tool_name}")

    # Step 1: Get the tool and its OpenAPI spec
    tool_info = get_tool_and_spec(tool_name)
    openapi_spec = tool_info['openapi_spec']
    
    # Step 2: Extract the relevant API information
    operation_id = tool_info['class_name']  # Assuming the operationId matches the class name
    method, url, parameters = get_api_info_from_openapi(openapi_spec, operation_id)
    
    # Step 3: Prepare the request payload
    payload = {}
    for param in parameters:
        param_name = param['name']
        if param_name in tool_params:
            payload[param_name] = tool_params[param_name]
    
    # Step 4: Send the API request
    if method == 'GET':
        response = requests.get(url, params=payload)
    elif method == 'POST':
        response = requests.post(url, json=payload)
    # Add other HTTP methods as needed
    
    # Step 5: Handle the response
    if response.status_code == 200:
        return response.json()  # Assuming the response is in JSON format
    else:
        return {"error": f"API call failed with status code {response.status_code}"}


def extract_parameters_from_openapi(openapi_spec):
    logger.info(f"Extracting Function Parameters")
    parameters = {}
    # Load and parse the OpenAPI specification
    spec = yaml.safe_load(openapi_spec)
    
    # Assuming you're dealing with a single path and operation:
    for path, path_item in spec['paths'].items():
        for operation, operation_item in path_item.items():
            if 'parameters' in operation_item:
                for param in operation_item['parameters']:
                    param_name = param['name']
                    param_schema = param['schema']
                    if 'enum' in param_schema:
                        parameters[param_name] = param_schema['enum']
                    else:
                        parameters[param_name] = param_schema['type']
    return parameters

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
    """Retrieve the tool name and parameters if a tool is required."""
    if not is_tool_required(ai_output):
        return None, None
    try:
        data = json.loads(ai_output)
        tool_name = data.get("tool_name")
        tool_parameters = data.get("tool_parameters")
        return tool_name, tool_parameters
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format in AI output.")


def process_initial_message(call_sid, customer_name, customer_problem):
    initial_prompt = AGENT_STARTING_PROMPT_TEMPLATE.format(
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
        tool_description = f"{tool['name']}: {tool['description']}"
        parameters = extract_parameters_from_openapi(tool['openapi_spec'])
        
        if parameters:
            params_description = f" (Parameters: {', '.join([f'{k} - possible values: {v}' if isinstance(v, list) else f'{k} - type: {v}' for k, v in parameters.items()])})"
            tool_description += params_description

        tools_description += tool_description + "\n"

    # Add dynamically loaded tools to the description
    for tool_name, tool_obj in initialized_tools.items():
        tools_description += f"\n{tool_name}: {tool_obj.description}"

    intent_tool_prompt = STAGE_TOOL_ANALYZER_PROMPT.format(
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
    
    message_to_send_to_ai = [
        {
            "role": "system",
            "content": intent_tool_prompt
        }
    ]
    message_to_send_to_ai.append(
        {"role": "user", "content": "You Must Respond in the json format specified in system prompt"})
    isToolResponse = "yes"
    ai_output = gen_ai_output(message_to_send_to_ai, isToolResponse)
    return ai_output



def initiate_inbound_message(call_sid):
    initial_response = AGENT_PROMPT_INBOUND_TEMPLATE.format(
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
            tool_name, params = get_tool_details(stage_tool_output)
            print('Tool called' + tool_name + 'tool param is: ' + params)
            
            # Use the dynamically loaded tool if available
            if tool_name in initialized_tools:
                api_response = call_api(tool_name, params)
                tool_output = f"Tool {tool_name} executed successfully. Response: {api_response}"
                message_history.append({"role": "api_response", "content": tool_output})

    except ValueError as e:
        tool_output = "Some Error Occured In calling the tools. Ask User if its okay that you callback the user later with answer of the query."

    print("Creating inbound prompt template")
    inbound_prompt = AGENT_PROMPT_OUTBOUND_TEMPLATE.format(
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
