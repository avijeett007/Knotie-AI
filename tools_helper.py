# tools_helper.py

import os
import yaml
import json
import sqlite3
import logging
import importlib
import requests
from config import Config
from cryptography.fernet import Fernet
import sys


GENERATED_TOOLS_DIR = 'generated_tools/'
logger = logging.getLogger(__name__)
# Initialize tools dynamically
initialized_tools = {}
# Use this key to encrypt/decrypt sensitive data
# It's recommended to store this key securely, such as in an environment variable
encryption_key = Config.ENCRYPTION_KEY
cipher = Fernet(encryption_key)
# Tool Initialization Functions

def encrypt_data(data):
    return cipher.encrypt(data.encode()).decode()

def decrypt_data(data):
    return cipher.decrypt(data.encode()).decode()

def fetch_tools_from_db():
    if not os.path.exists('tools.db'):
        logger.warning("Database file 'tools.db' does not exist.")
        return []

    try:
        conn = sqlite3.connect('tools.db')
        cursor = conn.cursor()
        cursor.execute('SELECT name, description, class_name, openapi_spec FROM tools')
        tools = cursor.fetchall()
    except sqlite3.OperationalError as e:
        logger.warning(f"Database error: {e}")
        return []
    finally:
        conn.close()

    return [{"name": row[0], "description": row[1], "class_name": row[2], "openapi_spec": row[3]} for row in tools]

def find_client_module(tool_name):
    """ Dynamically find the client module based on the tool's directory structure. """
    tool_dir = os.path.join(GENERATED_TOOLS_DIR, tool_name)
    
    for root, dirs, files in os.walk(tool_dir):
        if 'client.py' in files:
            relative_path = os.path.relpath(root, GENERATED_TOOLS_DIR)
            module_path = relative_path.replace(os.path.sep, '.')
            return module_path + '.client'
    
    return None

def extract_base_url_from_openapi_file(openapi_spec_path):
    """ Extract the base URL from the OpenAPI spec file. """
    try:
        with open(openapi_spec_path, 'r') as file:
            if openapi_spec_path.endswith('.json'):
                openapi_spec = json.load(file)
            elif openapi_spec_path.endswith('.yaml') or openapi_spec_path.endswith('.yml'):
                openapi_spec = yaml.safe_load(file)
            else:
                logger.error(f"Unsupported file format for OpenAPI spec: {openapi_spec_path}")
                return None
    except Exception as e:
        logger.error(f"Error reading OpenAPI spec file at {openapi_spec_path}: {e}")
        return None
    
    servers = openapi_spec.get('servers', [])
    if servers:
        return servers[0].get('url')
    return None

import logging
import yaml

def load_openapi_spec(openapi_spec_path):
    """Load and validate the OpenAPI spec from a file."""
    try:
        with open(openapi_spec_path, 'r') as file:
            spec_content = file.read()
            spec = yaml.safe_load(spec_content)

            if not isinstance(spec, dict):
                logging.error("The loaded OpenAPI spec is not a dictionary. Check the file content.")
                return None

            return spec

    except FileNotFoundError:
        logging.error(f"OpenAPI spec file not found at path: {openapi_spec_path}")
        return None
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML file: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error while loading OpenAPI spec: {e}")
        return None

def extract_operation_ids_from_openapi(openapi_spec):
    """Extract operation IDs from the OpenAPI spec."""
    try:
        # Load the spec if it's a file path, otherwise assume it's a dictionary
        if isinstance(openapi_spec, str):
            logging.info(f"Loading OpenAPI spec from file: {openapi_spec}")
            spec = load_openapi_spec(openapi_spec)
            if spec is None:
                return {}
        elif isinstance(openapi_spec, dict):
            spec = openapi_spec
        else:
            logging.error("The OpenAPI spec is not a valid string or dictionary.")
            return {}

        operation_ids = {}

        paths = spec.get('paths')
        if not isinstance(paths, dict):
            logging.error("'paths' is not a dictionary.")
            return {}

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                logging.error(f"'path_item' for path {path} is not a dictionary.")
                continue

            for operation, operation_item in path_item.items():
                if not isinstance(operation_item, dict):
                    logging.error(f"'operation_item' for operation {operation} in path {path} is not a dictionary.")
                    continue

                operation_id = operation_item.get('operationId')
                if operation_id:
                    method = operation.upper() if isinstance(operation, str) else None
                    url = extract_url(spec, path)
                    parameters = extract_parameters_from_operation(operation_item)
                    
                    if method and url:
                        operation_ids[operation_id] = {
                            'method': method,
                            'url': url,
                            'parameters': parameters
                        }

        return operation_ids

    except Exception as e:
        logging.error(f"An error occurred while extracting operation IDs: {e}")
        return {}

def extract_url(spec, path):
    """Extract URL from the spec and path."""
    try:
        servers = spec.get('servers')
        if isinstance(servers, list) and servers:
            server_url = servers[0].get('url')
            if isinstance(server_url, str):
                return server_url + path
        logging.error("Failed to extract the base URL from the spec.")
        return None
    except Exception as e:
        logging.error(f"Error extracting URL: {e}")
        return None

def extract_parameters_from_operation(operation_item):
    """Extract parameters from the operation item in the OpenAPI spec."""
    parameters = {
        'query': {},
        'header': {},
        'path': {},
        'body': {}
    }

    try:
        for param in operation_item.get('parameters', []):
            param_name = param.get('name')
            param_in = param.get('in')
            param_schema = param.get('schema', {})
            is_required = param.get('required', False)

            if param_in in parameters and param_name:
                parameters[param_in][param_name] = {
                    'type': param_schema.get('type', 'string'),
                    'enum': param_schema.get('enum', []),
                    'required': is_required
                }

        request_body = operation_item.get('requestBody')
        if isinstance(request_body, dict):
            content = request_body.get('content', {})
            for media_type, media_item in content.items():
                schema = media_item.get('schema', {})
                required_fields = schema.get('required', [])
                if schema.get('type') == 'object':
                    for prop_name, prop_schema in schema.get('properties', {}).items():
                        is_required = prop_name in required_fields
                        parameters['body'][prop_name] = {
                            'type': prop_schema.get('type', 'string'),
                            'enum': prop_schema.get('enum', []),
                            'required': is_required
                        }

    except Exception as e:
        logging.error(f"An error occurred while extracting parameters: {e}")

    return parameters



def initialize_tools():
    tools_from_db = fetch_tools_from_db()
    logger.info(f"step 1")
    for tool in tools_from_db:
        tool_name = tool["name"]
        openapi_spec_path = tool.get("openapi_spec")
        
        if not openapi_spec_path or not os.path.exists(openapi_spec_path):
            logger.error(f"OpenAPI spec file not found for tool {tool_name} at path: {openapi_spec_path}")
            continue
        
        client_module = find_client_module(tool_name)
        logger.info(f"step 2")
        if client_module is None:
            logger.error(f"Client module not found for tool {tool_name}")
            continue

        try:
            base_url = extract_base_url_from_openapi_file(openapi_spec_path)
            logger.info(f"step 3")
            operation_ids = extract_operation_ids_from_openapi(openapi_spec_path)
            logger.info(f"step 4")
            if not base_url:
                logger.error(f"Base URL not found in the OpenAPI spec for tool {tool_name}")
                continue

            sys.path.append(os.path.join(GENERATED_TOOLS_DIR, tool_name))
            module = importlib.import_module(client_module)
            logger.info(f"step 5")
            ToolClass = getattr(module, 'Client')
            
            initialized_tools[tool["name"]] = {
                'client': ToolClass(base_url=base_url),
                'operations': operation_ids
            }
            logger.info(f"step 6")
            logger.info(f"tool initialized successfully with operations: {operation_ids.keys()}")
            print(f"tool initialized successfully with operations: {operation_ids.keys()}")
        except ModuleNotFoundError as e:
            logger.error(f"Error initializing tool {tool_name}: {e}")
        except AttributeError as e:
            logger.error(f"Error finding class or method in module {tool_name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error initializing tool {tool_name}: {e}")

# AI Processing and Tool Usage

def get_tool_and_spec(tool_name):
    conn = sqlite3.connect('tools.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, description, class_name, openapi_spec, sensitive_headers, sensitive_body FROM tools WHERE name = ?', (tool_name,))
    tool = cursor.fetchone()
    conn.close()
    
    if tool:
        return {
            "name": tool[0],
            "description": tool[1],
            "class_name": tool[2],
            "openapi_spec": tool[3],
            "sensitive_headers": decrypt_data(tool[4]) if tool[4] else None,
            "sensitive_body": decrypt_data(tool[5]) if tool[5] else None
        }
    else:
        raise ValueError(f"Tool with name {tool_name} not found")


def get_api_info_from_openapi(spec, operation_id):
    for path, path_item in spec['paths'].items():
        for operation, operation_item in path_item.items():
            if 'operationId' in operation_item and operation_item['operationId'] == operation_id:
                method = operation.upper()
                url = spec['servers'][0]['url'] + path
                parameters = extract_parameters_from_operation(operation_item)
                return method, url, parameters

    raise ValueError(f"Operation ID {operation_id} not found in OpenAPI spec")


def call_api(tool_name, tool_parameters, operation_id, tool_headers, tool_body_parameters):
    logger.info(f"Calling tool: {tool_name}")
    print(f"Calling tool: {tool_name}")

    # Step 1: Get the tool and its OpenAPI spec
    tool_info = get_tool_and_spec(tool_name)
    openapi_spec = tool_info['openapi_spec']

    # Ensure the OpenAPI spec is loaded correctly as a dictionary
    if isinstance(openapi_spec, str):
        spec = load_openapi_spec(openapi_spec)
    else:
        spec = openapi_spec
    
    if not isinstance(spec, dict):
        raise ValueError("Invalid OpenAPI spec format. Expected a dictionary.")

    # Step 2: Extract the relevant API information
    method, url, parameters = get_api_info_from_openapi(spec, operation_id)
    
    query_params = {}
    headers = tool_headers if tool_headers else {}
    body = tool_body_parameters if tool_body_parameters else {}

    # Assign parameters from tool_body_parameters to the body
    for param_name, param_value in tool_body_parameters.items():
        if param_name in parameters['body']:
            body[param_name] = param_value

    # Assign header parameters from tool_headers to the headers
    for param_name, param_value in tool_headers.items():
        if param_name in parameters['header']:
            headers[param_name] = param_value

    # Assign query parameters from tool_parameters to the query_params
    for param_name, param_value in tool_parameters.items():
        if param_name in parameters['query']:
            query_params[param_name] = param_value

    # Step 3: Replace sensitive values in headers and body
    headers, body = replace_sensitive_values(headers, body, tool_name)
    
    # Debugging: Log the request details
    logger.info(f"Request Method: {method}")
    logger.info(f"Request URL: {url}")
    logger.info(f"Request Headers: {headers}")
    logger.info(f"Request Query Params: {query_params}")
    logger.info(f"Request Body: {json.dumps(body)}")  # Convert body to JSON string for logging
    
    # Step 4: Send the API request
    try:
        if method == 'GET':
            logger.debug('Sending GET request')
            response = requests.get(url, params=query_params, headers=headers)
        elif method == 'POST':
            logger.debug(f'Sending POST request to URL: {url}, with Body: {json.dumps(body)}, Params: {query_params}, Headers: {headers}')
            response = requests.post(url, json=body, params=query_params, headers=headers)
        # Add other HTTP methods as needed
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        # Step 5: Handle the response
        if response.status_code == 200:
            return response.json()  # Assuming the response is in JSON format
        else:
            logger.error(f"API call failed with status code {response.status_code}: {response.text}")
            return {"error": f"API call failed with status code {response.status_code}"}
    except Exception as e:
        logger.error(f"Error during API call: {e}")
        return {"error": str(e)}



def replace_sensitive_values(headers, body_parameters, tool_name):
    tool_info = get_tool_and_spec(tool_name)

    # Handle None values by providing an empty string or JSON object
    sensitive_headers = json.loads(tool_info.get('sensitive_headers', '{}') or '{}')
    sensitive_body = json.loads(tool_info.get('sensitive_body', '{}') or '{}')

    # Replace sensitive headers
    for key, value in headers.items():
        if value == "sensitive_value" and key in sensitive_headers:
            headers[key] = sensitive_headers[key]

    # Replace sensitive body parameters
    for key, value in body_parameters.items():
        if value == "sensitive_value" and key in sensitive_body:
            body_parameters[key] = sensitive_body[key]

    return headers, body_parameters


