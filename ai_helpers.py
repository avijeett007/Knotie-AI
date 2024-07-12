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
from tools import tools_info, OnsiteAppointmentTool, FetchProductPriceTool, CalendlyMeetingTool, \
    AppointmentAvailabilityTool

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

# Instantiate the tools if using BaseTool classes
if Config.USE_LANGCHAIN_TOOL_CLASS:
    OnsiteAppointmentTool = OnsiteAppointmentTool()
    FetchProductPriceTool = FetchProductPriceTool()
    CalendlyMeetingTool = CalendlyMeetingTool()
    AppointmentAvailabilityTool = AppointmentAvailabilityTool()

if which_model == "GROQ":
    ai = Groq(api_key=ai_api_key)
    params = {
        "model": llm_model,
        "temperature": 0.5,
        "max_tokens": 100,
        "stream": False,
        "top_p": 1
    }  # params["messages"] = prompt
elif which_model == "OpenAI" or which_model == "OpenRouter":
    openai.api_key = Config.AI_API_KEY
    openai.base_url = Config.OPENAI_BASE_URL
    params = {
        "model": llm_model,
        "temperature": 0.5,
        "max_tokens": 100,
    }  # params["messages"] = prompt
elif which_model == "Anthropic":
    ai = Anthropic(api_key=ai_api_key)
    params = {
        "model": llm_model,
        "temperature": 0.5,
        "max_tokens": 100,
    }


def gen_ai_output(prompt):
    """Generate AI output based on the prompt."""

    print("model selected is: ", which_model)

    if which_model == "OpenAI" or which_model == "OpenRouter":
        params["messages"] = prompt
        configuration = Configuration()
        if configuration.OPENAI_FINE_TUNED_MODEL_ID:
            print(f"Fine tuned model selected: {configuration.OPENAI_FINE_TUNED_MODEL_ID}")
            params['model'] = configuration.OPENAI_FINE_TUNED_MODEL_ID
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

    response = gen_ai_output(message_to_send_to_ai)
    return response


def invoke_stage_tool_analysis(message_history, user_input, conversation_stage_id):
    tools_description = "\n".join([
        f"{tool['name']}: {tool['description']}" +
        (
            f" (Parameters: {', '.join([f'{k} - possible values: {v}' if isinstance(v, list) else f'{k} - format: {v}' for k, v in tool.get('parameters', {}).items()])})" if 'parameters' in tool else "")
        for tool in tools_info.values()
    ])

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
    ai_output = gen_ai_output(message_to_send_to_ai)
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
    # if 'message_history' not in session:
    #     session['message_history'] = []
    # print("AI Tool and Conversation stage is decided: ", ai_output)
    """Process the AI decision to either call a tool or handle conversation stages."""
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
            if tool_name == "MeetingScheduler":
                tool_output = CalendlyMeetingTool._run() if Config.USE_LANGCHAIN_TOOL_CLASS else CalendlyMeetingTool()  # Assuming no parameters needed
                message_history.append({"role": "api_response", "content": tool_output})
            elif tool_name == "OnsiteAppointment":
                tool_output = OnsiteAppointmentTool._run() if Config.USE_LANGCHAIN_TOOL_CLASS else OnsiteAppointmentTool()  # Assuming no parameters needed
                message_history.append({"role": "api_response", "content": tool_output})
            elif tool_name == "GymAppointmentAvailability":
                tool_output = AppointmentAvailabilityTool._run() if Config.USE_LANGCHAIN_TOOL_CLASS else AppointmentAvailabilityTool()  # Assuming no parameters needed
                message_history.append({"role": "api_response", "content": tool_output})
            elif tool_name == "PriceInquiry":
                # Ensure params is a dictionary and contains 'product_name'
                tool_output = FetchProductPriceTool._run(
                    params) if Config.USE_LANGCHAIN_TOOL_CLASS else FetchProductPriceTool()
                message_history.append({"role": "api_response", "content": tool_output})
            else:
                return ""
    except ValueError as e:
        tool_output = "Some Error Occured In calling the tools. Ask User if its okay that you callback the user later with answer of the query."

    # conversation_stage_id = session.get('conversation_stage_id', 1)
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
        }
    ]
    message_to_send_to_ai_final.append({"role": "user", "content": user_input})
    # session['message_history'].append({"role": "user", "content": user_input})
    print("Calling With inbound template: ", json.dumps(message_history))
    conversation_cache = CacheManager()
    cache_result = conversation_cache.search(user_input)
    if cache_result is None:
        talkback_response = gen_ai_output(message_to_send_to_ai_final)
        conversation_cache.put(user_input, talkback_response)
        return talkback_response
    else:
        return cache_result
