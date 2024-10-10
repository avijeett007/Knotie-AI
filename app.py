from fastapi import FastAPI, Request, Response, HTTPException, Depends, File, UploadFile, Form
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import FileResponse
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
from langchain_core.prompts import PromptTemplate
from werkzeug.utils import secure_filename
from urllib.parse import quote
import uvicorn
import os
import shutil
import subprocess
import requests
import logging
import threading
import time
import redis
import json
import uuid
import sqlite3
import importlib
import re
from typing import Optional
from pydantic import BaseModel
import asyncio
import asyncio
from concurrent.futures import ThreadPoolExecutor

from audio_helpers import text_to_speech, text_to_speech_stream, save_audio_file, initialize_elevenlabs_client
from ai_helpers import process_initial_message, process_message, initiate_inbound_message, reinitialize_ai_clients
from tools_helper import initialize_tools, EncryptionHelper
from appUtils import clean_response, delayed_delete, save_message_history, get_message_history, process_elevenlabs_audio, generate_diverse_confirmation, get_redis_client
from prompts import AGENT_STARTING_PROMPT_TEMPLATE, STAGE_TOOL_ANALYZER_PROMPT, AGENT_PROMPT_OUTBOUND_TEMPLATE, \
    AGENT_PROMPT_INBOUND_TEMPLATE
from config import Config


# Create a thread pool executor
executor = ThreadPoolExecutor()
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OPENAPI_DIR = 'openapi_specs/'
GENERATED_TOOLS_DIR = 'generated_tools/'

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=Config.SECRET_KEY)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="templates")

def initialize_twilio_client():
    logger.info(f"Initiating Twilio client")
    global client
    client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)

# SQLite setup for user management
def init_sqlite_db():
    # Initialize user database
    conn = sqlite3.connect('knotie.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL,
                        first_login INTEGER DEFAULT 1)''')
    conn.commit()

    # Check if admin user exists, if not, create one
    cursor.execute('SELECT * FROM users WHERE username = "admin"')
    if cursor.fetchone() is None:
        cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', ('admin', 'admin'))
        conn.commit()

    # Create chat history table
    cursor.execute('''CREATE TABLE IF NOT EXISTS chat_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        transaction_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL)''')
    conn.commit()

    # Create tools table
    cursor.execute('''CREATE TABLE IF NOT EXISTS tools (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        description TEXT NOT NULL,
                        openapi_spec TEXT NOT NULL,
                        class_name TEXT NOT NULL,
                        sensitive_headers TEXT,
                        sensitive_body TEXT)''')
    conn.commit()

    # Create prompts table
    cursor.execute('''CREATE TABLE IF NOT EXISTS prompts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        template TEXT NOT NULL);''')
    conn.commit()

    # Insert the default prompts into the DB if they don't already exist
    prompts = [
        ('AGENT_PROMPT_OUTBOUND_TEMPLATE', AGENT_PROMPT_OUTBOUND_TEMPLATE.template),
        ('AGENT_PROMPT_INBOUND_TEMPLATE', AGENT_PROMPT_INBOUND_TEMPLATE.template),
        ('STAGE_TOOL_ANALYZER_PROMPT', STAGE_TOOL_ANALYZER_PROMPT.template),
        ('AGENT_STARTING_PROMPT_TEMPLATE', AGENT_STARTING_PROMPT_TEMPLATE.template)
    ]

    for name, template in prompts:
        cursor.execute('SELECT * FROM prompts WHERE name = ?', (name,))
        if cursor.fetchone() is None:
            cursor.execute('''INSERT INTO prompts (name, template) VALUES (?, ?)''', (name, template))
            conn.commit()

    # Create config table
    cursor.execute('''CREATE TABLE IF NOT EXISTS config (
                        key TEXT UNIQUE NOT NULL,
                        value TEXT NOT NULL)''')
    conn.commit()

    # Insert default config values if they don't exist
    default_configs = {
        'COMPANY_NAME': 'Knolabs AI Agency',
        'COMPANY_BUSINESS': 'Knolabs is an AI Agency which helps HomeService Businesses & Local Shops automate their business processes based on their need and necesity.',
        'COMPANY_PRODUCTS_SERVICES': 'Premium Consultancy Service - Most Budget offer, where we only provide consultancy to businesses who have their own team of developers (charged hourly), Proven Solution Services - Implements Automated Solutions that are already implemented & Proven for existing clients (Charged Based on Solutions), Custom Solutions - AI Automated Solution which are unique to the business (Price Varies, Charged Based on Agreed Contract)',
        'CONVERSATION_PURPOSE': 'Primarily to get an appointment booked to discuss problems of the customer in details',
        'AISALESAGENT_NAME': 'Andrea',
        'AI_API_KEY': 'Default AI API Key',
        'ENCRYPTION_KEY': 'Default Encryption Key',
        'WHICH_MODEL': 'OpenAI',
        'OPENAI_BASE_URL': 'https://api.openai.com/v1/',
        'VOICE_MODE': 'ELEVENLABS_STREAM',
        'LLM_MODEL': 'gpt-3.5-turbo',
        'OPENAI_FINE_TUNED_MODEL_ID': 'gpt-3.5-turbo',
        'OPENAI_FINE_TUNED_TOOLS_MODEL_ID': 'gpt-4o-mini',
        'USE_LANGCHAIN_TOOL_CLASS': 'false',
        'AGENT_CUSTOM_INSTRUCTIONS': 'Ask and Answer in short sentences to be focused on providing right information and provide fastest way for make deal. Be specific and do not try to answer questions which are not specific to the goal or company info or details available in context',
        'TWILIO_ACCOUNT_SID': 'Default Twilio SID',
        'TWILIO_AUTH_TOKEN': 'Default Twilio Auth Token',
        'TWILIO_FROM_NUMBER': 'Default Twilio Number',
        'ELEVENLABS_API_KEY': 'Default Eleven Labs API Key',
        'NGROK_AUTH_TOKEN': 'NGROK Default Auth Token',
        'USE_NGROK': 'true',
        'VOICE_ID': '21m00Tcm4TlvDq8ikWAM',
        'APP_PUBLIC_URL': 'https://default-url.com',
        'CACHE_ENABLED': 'false',
        'REDIS_URL': 'redis://redis:6379'
    }

    # Insert default configs if not present
    for key, value in default_configs.items():
        cursor.execute('SELECT value FROM config WHERE key = ?', (key,))
        if cursor.fetchone() is None:
            cursor.execute('INSERT INTO config (key, value) VALUES (?, ?)', (key, value))
            conn.commit()

    conn.close()

init_sqlite_db()

def is_valid_tool_name(tool_name):
    """Validate the tool name to prevent directory traversal or other path manipulation."""
    # Allow only alphanumeric characters and underscores in the tool name
    # This prevents directory traversal and other malicious input
    return re.match(r'^[\w-]+$', tool_name) is not None


def generate_tool_client(tool_name, tool_file_path):
    # Validate the tool name
    if not is_valid_tool_name(tool_name):
        raise ValueError(f"Invalid tool name: {tool_name}")

    # Create a unique directory for each tool
    tool_output_dir = os.path.join(GENERATED_TOOLS_DIR, tool_name)
    
    # Check if the directory already exists and delete it if needed
    # if os.path.exists(tool_output_dir):
    #     logger.info(f"Directory {tool_output_dir} exists. Overwriting.")
    #     shutil.rmtree(tool_output_dir)  # Use shutil.rmtree to remove the directory
    
    # Generate the client using the OpenAPI spec
    try:
        subprocess.run(
            ['openapi-python-client', 'generate', '--path', tool_file_path, '--output-path', tool_output_dir],
            check=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to generate client for tool {tool_name}: {e}")
        raise

def add_tool_to_db(tool_name, tool_description, tool_file, tool_sensitive_headers, tool_sensitive_body):
    # Generate client for the tool
    generate_tool_client(tool_name, tool_file)

    # Encrypt sensitive headers and body parameters
    encrypted_headers = EncryptionHelper.encrypt_data(tool_sensitive_headers) if tool_sensitive_headers else None
    encrypted_body = EncryptionHelper.encrypt_data(tool_sensitive_body) if tool_sensitive_body else None

    # Insert tool data into the database
    conn = sqlite3.connect('knotie.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO tools (name, description, openapi_spec, class_name, sensitive_headers, sensitive_body) VALUES (?, ?, ?, ?, ?, ?)',
                   (tool_name, tool_description, tool_file, f'{tool_name}.Client', encrypted_headers, encrypted_body))
    conn.commit()
    conn.close()

    # Initialize the tool after adding it
    initialize_tools()
    
# Twilio client initialization
client = None


# Initialize the clients at the start
initialize_twilio_client()
initialize_elevenlabs_client()

# Remove automatic AI client and tool initialization
# reinitialize_ai_clients()
# initialize_tools()

# Dependency for authentication
security = HTTPBasic()
def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = "admin"
    correct_password = "admin"
    if credentials.username != correct_username or credentials.password != correct_password:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    return credentials.username


# Routes
@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/admin")
async def admin(request: Request):
    if not request.session.get('logged_in'):
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin.html", {"request": request})

# Dependency for checking session authentication
async def get_current_user(request: Request):
    if not request.session.get('logged_in'):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return request.session.get('username')

@app.get("/api/config")
async def get_config(username: str = Depends(get_current_user)):
    configs = Config.load_dynamic_config()
    return JSONResponse(content=configs)

@app.post("/api/config")
async def update_config(request: Request, username: str = Depends(get_current_user)):
    new_config = await request.json()
    Config.save_dynamic_config(new_config)
    Config.initialize()
    initialize_twilio_client()
    initialize_elevenlabs_client()
    reinitialize_ai_clients()
    initialize_tools()
    return JSONResponse(content={"message": "Config updated successfully"})


@app.get("/api/chats")
async def get_chats(username: str = Depends(get_current_user)):
    redis_client = get_redis_client()
    keys = redis_client.keys('*')
    logger.info(f"list of keys are: {keys}")
    return JSONResponse(content=keys)

@app.get("/api/chat/{transaction_id}")
async def get_chat(transaction_id: str, username: str = Depends(get_current_user)):
    chat_history = get_message_history(transaction_id)
    if not chat_history:
        raise HTTPException(status_code=404, detail="No chat history found")
    return JSONResponse(content=chat_history)

@app.get("/api/prompts")
async def get_prompts(username: str = Depends(get_current_user)):
    conn = sqlite3.connect('knotie.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, template FROM prompts')
    prompts = cursor.fetchall()
    conn.close()
    prompts_list = [{"name": prompt[0], "template": prompt[1]} for prompt in prompts]
    return JSONResponse(content=prompts_list)

@app.put("/api/prompts")
async def update_prompt(prompt: dict, username: str = Depends(get_current_user)):
    prompt_name = prompt.get('name')
    prompt_template = prompt.get('template')
    if not prompt_name or not prompt_template:
        raise HTTPException(status_code=400, detail="Invalid request data")
    conn = sqlite3.connect('knotie.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE prompts SET template = ? WHERE name = ?', (prompt_template, prompt_name))
    conn.commit()
    conn.close()
    return JSONResponse(content={"message": "Prompt updated successfully"})

@app.get("/api/tools")
async def get_tools(username: str = Depends(get_current_user)):
    conn = sqlite3.connect('knotie.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, description, openapi_spec FROM tools')
    tools = cursor.fetchall()
    conn.close()
    tools_list = [{"id": tool[0], "name": tool[1], "description": tool[2], "openapi_spec": tool[3]} for tool in tools]
    return JSONResponse(content=tools_list)

@app.post("/api/tools")
async def add_tool(
    request: Request,
    toolName: str = Form(...),
    toolDescription: str = Form(...),
    toolFile: UploadFile = File(...),
    toolSensitiveHeaders: Optional[str] = Form(None),
    toolSensitiveBody: Optional[str] = Form(None),
    username: str = Depends(get_current_user)
):
    os.makedirs(GENERATED_TOOLS_DIR, exist_ok=True)
    filename = secure_filename(toolFile.filename)
    tool_file_path = os.path.join(OPENAPI_DIR, filename)
    with open(tool_file_path, "wb") as buffer:
        shutil.copyfileobj(toolFile.file, buffer)
    add_tool_to_db(toolName, toolDescription, tool_file_path, toolSensitiveHeaders, toolSensitiveBody)
    return JSONResponse(content={"message": "Tool added successfully"})

@app.post("/login")
async def login(request: Request):
    data = await request.json()
    username = data.get('username')
    password = data.get('password')
    conn = sqlite3.connect('knotie.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
    user = cursor.fetchone()
    conn.close()
    if user:
        request.session['logged_in'] = True
        request.session['username'] = username
        first_login = user[3]
        return JSONResponse(content={'success': True, 'message': 'Login successful', 'first_login': first_login == 1})
    else:
        return JSONResponse(content={'success': False, 'message': 'Login failed'})

@app.post("/change_password")
async def change_password(request: Request):
    if 'logged_in' not in request.session:
        raise HTTPException(status_code=403, detail="Not logged in")
    data = await request.json()
    new_password = data.get('new_password')
    conn = sqlite3.connect('knotie.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET password = ?, first_login = 0 WHERE username = ?', (new_password, request.session['username']))
    conn.commit()
    conn.close()
    return JSONResponse(content={'success': True, 'message': 'Password changed successfully'})

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")


@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    directory = 'audio_files'
    file_path = os.path.join(directory, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    def cleanup():
        delayed_delete(file_path)
    
    return FileResponse(file_path, media_type="audio/mpeg", background=cleanup)

@app.get("/audio-stream")
async def audio_stream(text: str):
    audio_stream = text_to_speech_stream(text)
    
    def generate():
        while True:
            chunk = audio_stream.read(1024)
            if not chunk:
                break
            yield chunk
    
    return StreamingResponse(generate(), media_type="audio/mpeg")

@app.post("/start-call")
async def start_call(request: Request):
    data = await request.json()
    unique_id = str(uuid.uuid4())
    message_history = []
    customer_name = data.get('customer_name', 'Valued Customer')
    customer_phonenumber = data.get('customer_phonenumber', '')
    customer_businessdetails = data.get('customer_businessdetails', 'No details provided.')
    
    ai_message = process_initial_message(unique_id, customer_name, customer_businessdetails)
    logger.info(ai_message)
    response = VoiceResponse()
    
    if Config.VOICE_MODE == "ELEVENLABS_DIRECT":
        initial_message = clean_response(ai_message)
        audio_filename = process_elevenlabs_audio(initial_message)
        response.play(f"{request.base_url}audio/{quote(secure_filename(audio_filename))}")
    elif Config.VOICE_MODE == "ELEVENLABS_STREAM":
        initial_message = clean_response(ai_message)
        audio_url = f"{request.base_url}audio-stream?text={quote(initial_message)}"
        logger.info(audio_url)
        response.play(audio_url)
    elif Config.VOICE_MODE == "TWILIO_DIRECT":
        initial_message = clean_response(ai_message)
        response.say(initial_message, voice='Google.en-GB-Standard-C', language='en-US')
    
    initial_transcript = f"Customer Name: {customer_name}. Customer's business Details as filled up in the website: {customer_businessdetails}"
    message_history.append({"role": "user", "content": initial_transcript})
    message_history.append({"role": "assistant", "content": initial_message})
    save_message_history(unique_id, message_history)

    redirect_url = f"{Config.APP_PUBLIC_GATHER_URL}?CallSid={unique_id}"
    public_url = f"{Config.APP_PUBLIC_EVENT_URL}"
    response.redirect(redirect_url)
    
    client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
    call = client.calls.create(
        twiml=str(response),
        to=customer_phonenumber,
        from_=Config.TWILIO_FROM_NUMBER,
        method="GET",
        status_callback=public_url,
        status_callback_method="POST"
    )
    return JSONResponse(content={'message': 'Call initiated', 'call_sid': call.sid})

@app.post("/gather")
@app.get("/gather")
async def gather_input(request: Request):
    call_sid = request.query_params.get('CallSid', 'default_sid')
    resp = VoiceResponse()
    gather = Gather(input='speech', action=f"/process-speech?CallSid={call_sid}", speechTimeout='auto', method="POST")
    resp.append(gather)
    resp.redirect(f"/gather?CallSid={call_sid}")
    return Response(content=str(resp), media_type="application/xml")

@app.post("/gather-inbound")
@app.get("/gather-inbound")
async def gather_input_inbound(request: Request):
    resp = VoiceResponse()
    unique_id = str(uuid.uuid4())
    message_history = []
    agent_response = initiate_inbound_message(unique_id)

    if Config.VOICE_MODE == "ELEVENLABS_DIRECT":
        audio_filename = process_elevenlabs_audio(agent_response)
        resp.play(f"{request.base_url}audio/{quote(secure_filename(audio_filename))}")
    elif Config.VOICE_MODE == "ELEVENLABS_STREAM":
        initial_message = clean_response(agent_response)
        audio_url = f"{request.base_url}audio-stream?text={quote(agent_response)}"
        resp.play(audio_url)
    elif Config.VOICE_MODE == "TWILIO_DIRECT":
        initial_message = clean_response(agent_response)
        resp.say(agent_response, voice='Google.en-GB-Standard-C', language='en-US')

    message_history.append({"role": "assistant", "content": agent_response})
    save_message_history(unique_id, message_history)
    resp.redirect(f"/gather?CallSid={unique_id}")
    return Response(content=str(resp), media_type="application/xml")


@app.post("/process-speech")
async def process_speech(request: Request):
    form_data = await request.form()
    speech_result = form_data.get('SpeechResult', '').strip()
    call_sid = request.query_params.get('CallSid', 'default_sid')
    message_history = get_message_history(call_sid)
    message_history.append({"role": "user", "content": speech_result})
    # Run the background task in a separate thread
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(executor, generate_response_in_background, call_sid, message_history, speech_result)


    confirmation_prompt = generate_diverse_confirmation(speech_result)
    resp = VoiceResponse()
    response_text = clean_response(confirmation_prompt)
    
    audio_url = f"{request.base_url}audio-stream?text={quote(response_text)}"
    resp.play(audio_url)

    gather = Gather(
        input='speech',
        action=f"/process-confirmation?CallSid={call_sid}",
        speechTimeout='2',
        method='POST'
    )
    resp.append(gather)

    resp.redirect(f"/handle-confirmation?CallSid={call_sid}")

    return Response(content=str(resp), media_type="application/xml")

def generate_response_in_background(call_sid: str, message_history: list, user_input: str):
    redis_client = get_redis_client()  
    ai_response_text = process_message(call_sid, message_history, user_input)
    redis_client.set(f"response:{call_sid}", ai_response_text)
    redis_client.expire(f"response:{call_sid}", 300)  # Expires in 5 minutes

@app.post("/handle-confirmation")
@app.get("/handle-confirmation")
async def handle_confirmation(request: Request):
    call_sid = request.query_params.get('CallSid', 'default_sid')
    resp = VoiceResponse()
    gather = Gather(
        input='speech',
        action=f"/process-confirmation?CallSid={call_sid}",
        speechTimeout='auto',
        method='POST'
    )
    resp.append(gather)
    return Response(content=str(resp), media_type="application/xml")

@app.post("/process-confirmation")
async def process_confirmation(request: Request):
    form_data = await request.form()
    confirmation_result = form_data.get('SpeechResult', '').strip().lower()
    call_sid = request.query_params.get('CallSid', 'default_sid')
    resp = VoiceResponse()
    message_history = get_message_history(call_sid)

    positive_keywords = ["yes", "correct", "you're right", "ahha", "that's right", "right", "yeah", "yep", "affirmative", "sure", "absolutely", "indeed", "aha", "uh-huh", "mmm", "okay", "ok", "alright", "got it"]
    negative_keywords = ["no", "incorrect", "that's wrong", "wrong", "nope", "not quite", "negative", "not really", "no way", "uh-oh", "nah", "hmm", "huh-uh"]

    if any(keyword in confirmation_result for keyword in positive_keywords):
        logger.info(f'User confirmed yes')
        redis_client = get_redis_client()
        ai_response_bytes = redis_client.get(f"response:{call_sid}")

        wait_time = 0
        max_wait_time = 100

        while ai_response_bytes is None and wait_time < max_wait_time:
            logger.info(f'waiting for response from AI')
            await asyncio.sleep(5)
            wait_time += 1
            ai_response_bytes = redis_client.get(f"response:{call_sid}")

        if ai_response_bytes:
            ai_response_text = ai_response_bytes.decode('utf-8')
            response_text = clean_response(ai_response_text)
            audio_url = f"{request.base_url}audio-stream?text={quote(response_text)}"
            resp.play(audio_url)

            redis_client.delete(f"response:{call_sid}")
            message_history.append({"role": "assistant", "content": response_text})
            save_message_history(call_sid, message_history)
            resp.redirect(f"/gather?CallSid={call_sid}")
        else:
            resp.say("I'm sorry, I'm still processing your request. Please hold for a moment.")
            resp.redirect(f"/handle-confirmation?CallSid={call_sid}")
    
    elif any(keyword in confirmation_result for keyword in negative_keywords):
        gather = Gather(
            input='speech',
            action=f"/process-speech?CallSid={call_sid}",
            speechTimeout='auto',
            method="POST"
        )
        gather.say("I'm sorry, could you please repeat your input?")
        resp.append(gather)
    else:
        gather = Gather(
            input='speech',
            action=f"/process-confirmation?CallSid={call_sid}",
            speechTimeout='auto',
            method="POST"
        )
        gather.say("I didn't catch that. Could you please say 'yes' or 'no'?")
        resp.append(gather)

    return Response(content=str(resp), media_type="application/xml")

@app.post("/event")
async def event(request: Request):
    form_data = await request.form()
    call_status = form_data.get('CallStatus', '')
    if call_status in ['completed', 'busy', 'failed']:
        request.session.pop('message_history', None)
        logger.info(f"Call completed with status: {call_status}")
    return Response(status_code=204)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)