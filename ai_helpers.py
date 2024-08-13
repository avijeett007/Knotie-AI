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


# def find_client_module(tool_name):
#     """ Dynamically find the client module based on the tool's directory structure. """
#     tool_dir = os.path.join(GENERATED_TOOLS_DIR, tool_name)
    
#     # Recursively search for the client.py file
#     for root, dirs, files in os.walk(tool_dir):
#         if 'client.py' in files:
#             # Convert the path to a module path
#             relative_path = os.path.relpath(root, GENERATED_TOOLS_DIR)
#             module_path = relative_path.replace(os.path.sep, '.')
#             return module_path + '.client'
    
#     # If client.py is not found, return None
#     return None

# def fetch_tools_from_db():
#     if not os.path.exists('users.db'):
#         logger.warning("Database file 'users.db' does not exist.")
#         return []

#     try:
#         conn = sqlite3.connect('users.db')
#         cursor = conn.cursor()
#         cursor.execute('SELECT name, description, class_name, openapi_spec FROM tools')
#         tools = cursor.fetchall()
#     except sqlite3.OperationalError as e:
#         logger.warning(f"Database error: {e}")
#         return []
#     finally:
#         conn.close()

#     return [{"name": row[0], "description": row[1], "class_name": row[2], "openapi_spec": row[3]} for row in tools]

# def find_client_module(tool_name):
#     """ Dynamically find the client module based on the tool's directory structure. """
#     tool_dir = os.path.join(GENERATED_TOOLS_DIR, tool_name)
    
#     # Recursively search for the client.py file
#     for root, dirs, files in os.walk(tool_dir):
#         if 'client.py' in files:
#             # Convert the path to a module path
#             relative_path = os.path.relpath(root, GENERATED_TOOLS_DIR)
#             module_path = relative_path.replace(os.path.sep, '.')
#             return module_path + '.client'
    
#     # If client.py is not found, return None
#     return None

# def extract_base_url_from_openapi_file(openapi_spec_path):
#     """ Extract the base URL from the OpenAPI spec file. """
#     try:
#         with open(openapi_spec_path, 'r') as file:
#             # Load the OpenAPI spec as either JSON or YAML
#             if openapi_spec_path.endswith('.json'):
#                 openapi_spec = json.load(file)
#             elif openapi_spec_path.endswith('.yaml') or openapi_spec_path.endswith('.yml'):
#                 openapi_spec = yaml.safe_load(file)
#             else:
#                 logger.error(f"Unsupported file format for OpenAPI spec: {openapi_spec_path}")
#                 return None
#     except Exception as e:
#         logger.error(f"Error reading OpenAPI spec file at {openapi_spec_path}: {e}")
#         return None
    
#     servers = openapi_spec.get('servers', [])
#     if servers:
#         return servers[0].get('url')  # Assuming the first server URL is the base URL
#     return None

# # Initialize tools dynamically
# initialized_tools = {}

# def initialize_tools():
#     tools_from_db = fetch_tools_from_db()

#     for tool in tools_from_db:
#         tool_name = tool["name"]
#         openapi_spec_path = tool.get("openapi_spec")
        
#         # Ensure the OpenAPI spec path is valid
#         if not openapi_spec_path or not os.path.exists(openapi_spec_path):
#             logger.error(f"OpenAPI spec file not found for tool {tool_name} at path: {openapi_spec_path}")
#             continue
        
#         client_module = find_client_module(tool_name)
        
#         if client_module is None:
#             logger.error(f"Client module not found for tool {tool_name}")
#             continue

#         try:
#             # Extract the base URL and operation IDs from the OpenAPI spec
#             base_url = extract_base_url_from_openapi_file(openapi_spec_path)
#             operation_ids = extract_operation_ids_from_openapi(openapi_spec_path)
#             if not base_url:
#                 logger.error(f"Base URL not found in the OpenAPI spec for tool {tool_name}")
#                 continue

#             # Add the root tool directory to sys.path
#             sys.path.append(os.path.join(GENERATED_TOOLS_DIR, tool_name))
#             module = importlib.import_module(client_module)
#             ToolClass = getattr(module, 'Client')  # Assuming the generated class is named 'Client'
            
#             # Initialize the tool with the base URL and available operations
#             initialized_tools[tool["name"]] = {
#                 'client': ToolClass(base_url=base_url),
#                 'operations': operation_ids
#             }
#             logger.info(f"tool initialized successfully with operations: {operation_ids.keys()}")
#             print(f"tool initialized successfully with operations: {operation_ids.keys()}")
#         except ModuleNotFoundError as e:
#             logger.error(f"Error initializing tool {tool_name}: {e}")
#         except AttributeError as e:
#             logger.error(f"Error finding class or method in module {tool_name}: {e}")
#         except Exception as e:
#             logger.error(f"Unexpected error initializing tool {tool_name}: {e}")

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

# def get_tool_and_spec(tool_name):
#     conn = sqlite3.connect('users.db')
#     cursor = conn.cursor()
#     cursor.execute('SELECT name, description, class_name, openapi_spec FROM tools WHERE name = ?', (tool_name,))
#     tool = cursor.fetchone()
#     conn.close()
    
#     if tool:
#         return {
#             "name": tool[0],
#             "description": tool[1],
#             "class_name": tool[2],
#             "openapi_spec": tool[3]
#         }
#     else:
#         raise ValueError(f"Tool with name {tool_name} not found")


# def get_api_info_from_openapi(openapi_spec, operation_id):
#     spec = yaml.safe_load(openapi_spec)

#     for path, path_item in spec['paths'].items():
#         for operation, operation_item in path_item.items():
#             if 'operationId' in operation_item and operation_item['operationId'] == operation_id:
#                 method = operation.upper()
#                 url = spec['servers'][0]['url'] + path
#                 parameters = extract_parameters_from_openapi(openapi_spec)
#                 return method, url, parameters

#     raise ValueError(f"Operation ID {operation_id} not found in OpenAPI spec")


# def call_api(tool_name, tool_params):
#     logger.info(f"Calling tool: {tool_name}")
#     print(f"Calling tool: {tool_name}")

#     # Step 1: Get the tool and its OpenAPI spec
#     tool_info = get_tool_and_spec(tool_name)
#     openapi_spec = tool_info['openapi_spec']
    
#     # Step 2: Extract the relevant API information
#     operation_id = tool_info['class_name']  # Assuming the operationId matches the class name
#     method, url, parameters = get_api_info_from_openapi(openapi_spec, operation_id)
    
#     # Step 3: Prepare the request payload
#     query_params = {}
#     headers = {}
#     body = {}

#     # Assign parameters from tool_params to appropriate places (query, headers, body)
#     for param_name, param_value in tool_params.items():
#         if param_name in parameters['query']:
#             query_params[param_name] = param_value
#         elif param_name in parameters['header']:
#             headers[param_name] = param_value
#         elif param_name in parameters['body']:
#             body[param_name] = param_value
    
#     # Step 4: Send the API request
#     if method == 'GET':
#         response = requests.get(url, params=query_params, headers=headers)
#     elif method == 'POST':
#         response = requests.post(url, json=body, params=query_params, headers=headers)
#     # Add other HTTP methods as needed
    
#     # Step 5: Handle the response
#     if response.status_code == 200:
#         return response.json()  # Assuming the response is in JSON format
#     else:
#         return {"error": f"API call failed with status code {response.status_code}"}

# def extract_parameters_from_operation(operation_item):
#     """Extract parameters from the operation item in the OpenAPI spec."""
#     parameters = {
#         'query': {},
#         'header': {},
#         'path': {},
#         'body': {}
#     }

#     # Handle 'parameters' (query, header, path)
#     for param in operation_item.get('parameters', []):
#         param_name = param['name']
#         param_in = param['in']  # This could be 'query', 'header', 'path'
#         param_schema = param.get('schema', {})

#         if param_in in parameters:
#             if 'enum' in param_schema:
#                 parameters[param_in][param_name] = param_schema['enum']
#             else:
#                 parameters[param_in][param_name] = param_schema.get('type', 'string')

#     # Handle 'requestBody' (body parameters)
#     request_body = operation_item.get('requestBody', {})
#     if request_body:
#         content = request_body.get('content', {})
#         for media_type, media_item in content.items():
#             schema = media_item.get('schema', {})
#             if schema.get('type') == 'object':
#                 for prop_name, prop_schema in schema.get('properties', {}).items():
#                     if 'enum' in prop_schema:
#                         parameters['body'][prop_name] = prop_schema['enum']
#                     else:
#                         parameters['body'][prop_name] = prop_schema.get('type', 'string')

#     return parameters

# def extract_operation_ids_from_openapi(openapi_spec):
#     """ Extract operation IDs from the OpenAPI spec. """
#     spec = yaml.safe_load(openapi_spec)
#     operation_ids = {}

#     for path, path_item in spec.get('paths', {}).items():
#         for operation, operation_item in path_item.items():
#             operation_id = operation_item.get('operationId')
#             if operation_id:
#                 operation_ids[operation_id] = {
#                     'method': operation.upper(),
#                     'url': spec['servers'][0]['url'] + path,
#                     'parameters': extract_parameters_from_operation(operation_item)
#                 }

#     return operation_ids

# def extract_parameters_from_openapi(openapi_spec):
#     logger.info(f"Extracting Function Parameters")
    
#     # If `openapi_spec` is a path, load the content first
#     if isinstance(openapi_spec, str):
#         if os.path.exists(openapi_spec):
#             with open(openapi_spec, 'r') as file:
#                 if openapi_spec.endswith('.json'):
#                     spec = json.load(file)
#                 elif openapi_spec.endswith('.yaml') or openapi_spec.endswith('.yml'):
#                     spec = yaml.safe_load(file)
#                 else:
#                     logger.error(f"Unsupported file format for OpenAPI spec: {openapi_spec}")
#                     return {}
#         else:
#             # If the string is not a path, assume it's a direct YAML/JSON content
#             try:
#                 spec = yaml.safe_load(openapi_spec)
#             except Exception as e:
#                 logger.error(f"Failed to parse OpenAPI spec content: {e}")
#                 return {}
#     else:
#         # If `openapi_spec` is already a dict (parsed JSON/YAML), just use it
#         spec = openapi_spec

#     # Now extract parameters from the spec
#     parameters = {
#         'query': {},
#         'header': {},
#         'path': {},
#         'body': {}
#     }

#     for path, path_item in spec.get('paths', {}).items():
#         for operation, operation_item in path_item.items():
#             # Handle 'parameters' in the operation (e.g., query, header, path)
#             for param in operation_item.get('parameters', []):
#                 param_name = param['name']
#                 param_in = param['in']  # This could be 'query', 'header', 'path'
#                 param_schema = param.get('schema', {})
                
#                 if param_in in parameters:
#                     if 'enum' in param_schema:
#                         parameters[param_in][param_name] = param_schema['enum']
#                     else:
#                         parameters[param_in][param_name] = param_schema.get('type', 'string')
            
#             # Handle 'requestBody' in the operation (e.g., body parameters)
#             request_body = operation_item.get('requestBody', {})
#             if request_body:
#                 content = request_body.get('content', {})
#                 for content_type, media_type in content.items():
#                     schema = media_type.get('schema', {})
#                     if schema.get('type') == 'object':
#                         for prop_name, prop_schema in schema.get('properties', {}).items():
#                             if 'enum' in prop_schema:
#                                 parameters['body'][prop_name] = prop_schema['enum']
#                             else:
#                                 parameters['body'][prop_name] = prop_schema.get('type', 'string')

#     return parameters

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

# def replace_sensitive_values(tool_headers, tool_body_parameters):
#     # Replace the placeholder "sensitive_value" with the actual sensitive data
#     actual_sensitive_data = get_sensitive_data_from_db()  # Retrieve actual data from your DB
#     for key, value in tool_headers.items():
#         if value == "sensitive_value":
#             tool_headers[key] = actual_sensitive_data.get(key)

#     for key, value in tool_body_parameters.items():
#         if value == "sensitive_value":
#             tool_body_parameters[key] = actual_sensitive_data.get(key)

#     return tool_headers, tool_body_parameters

# def get_sensitive_data_from_db(key):
#     """
#     Retrieves sensitive data from the database based on the provided key.

#     :param key: The identifier for the sensitive data to retrieve.
#     :return: The sensitive data corresponding to the key, or None if not found.
#     """
#     try:
#         # Establish a connection to the database
#         conn = sqlite3.connect('sensitive_data.db')  # Make sure the database file exists
#         cursor = conn.cursor()

#         # Query to fetch the sensitive value based on the provided key
#         cursor.execute('SELECT value FROM sensitive_data WHERE key = ?', (key,))
#         result = cursor.fetchone()

#         # Check if the result is found
#         if result:
#             return result[0]  # Return the sensitive value
#         else:
#             logger.warning(f"No sensitive data found for key: {key}")
#             return None

#     except sqlite3.Error as e:
#         logger.error(f"Database error: {e}")
#         return None

#     finally:
#         # Close the database connection
#         if conn:
#             conn.close()

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
        tool_name = tool['name']
        tool_description = f"{tool_name}: {tool['description']}\nAvailable Operations:\n"
        
        # Extracting operations and their details
        operation_ids = initialized_tools[tool_name]['operations']

        for operation_id, operation_details in operation_ids.items():
            tool_description += f"  - {operation_id}: {operation_details['method']} {operation_details['url']}\n"
            
            # Adding headers, query parameters, and path parameters
            headers_description = ', '.join([f"{header}: {details}" for header, details in operation_details['parameters'].get('header', {}).items()])
            query_description = ', '.join([f"{param}: {details}" for param, details in operation_details['parameters'].get('query', {}).items()])
            path_description = ', '.join([f"{param}: {details}" for param, details in operation_details['parameters'].get('path', {}).items()])
            body_description = ', '.join([f"{param}: {details}" for param, details in operation_details['parameters'].get('body', {}).items()])

            if headers_description:
                tool_description += f"    Headers: {headers_description}\n"
            if query_description:
                tool_description += f"    Query Parameters: {query_description}\n"
            if path_description:
                tool_description += f"    Path Parameters: {path_description}\n"
            if body_description:
                tool_description += f"    Body Parameters: {body_description}\n"

        tools_description += tool_description + "\n"
    print("tool description is:" + tools_description)
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

