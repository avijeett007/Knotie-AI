from flask import Flask, request, jsonify, render_template, session, redirect, url_for, Response, send_from_directory, abort, after_this_request
from flask_session import Session
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
from werkzeug.utils import secure_filename
from langchain_core.prompts import PromptTemplate
from flask_cors import CORS
import os
import shutil
import subprocess
import requests
from audio_helpers import text_to_speech, text_to_speech_stream, save_audio_file, initialize_elevenlabs_client
from ai_helpers import process_initial_message, process_message, initiate_inbound_message, reinitialize_ai_clients
from tools_helper import initialize_tools, EncryptionHelper
from appUtils import clean_response, delayed_delete, save_message_history, get_message_history, process_elevenlabs_audio, generate_diverse_confirmation
from prompts import AGENT_STARTING_PROMPT_TEMPLATE, STAGE_TOOL_ANALYZER_PROMPT, AGENT_PROMPT_OUTBOUND_TEMPLATE, \
    AGENT_PROMPT_INBOUND_TEMPLATE
from config import Config
import logging
import threading
import time
import redis
import json
from urllib.parse import quote_plus
import uuid
import sqlite3
import importlib
import shutil
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
OPENAPI_DIR = 'openapi_specs/'
# Define the directory for storing generated tools
GENERATED_TOOLS_DIR = 'generated_tools/'

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config.from_object(Config)

# Session configuration
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False  # You can set True for permanent sessions
app.config['SESSION_USE_SIGNER'] = True  # Securely sign the session
app.config['SESSION_REDIS'] = redis.from_url('redis://redis:6379')
Session(app)
app.logger.setLevel(logging.DEBUG)
redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

# Path to the configuration file
config_path = 'config.json'


# Load configuration from JSON file
def load_config():
    if os.path.exists(config_path):
        with open(config_path) as config_file:
            return json.load(config_file)
    else:
        return {}  # Return an empty config if the file doesn't exist

# Global variable to hold the configuration
config_data = load_config()

def is_valid_tool_name(tool_name):
    """Validate the tool name to prevent directory traversal or other path manipulation."""
    # Allow only alphanumeric characters and underscores in the tool name
    # This prevents directory traversal and other malicious input
    return re.match(r'^[\w-]+$', tool_name) is not None

# SQLite setup for user management
def init_sqlite_db():
    # Initialize user database
    conn = sqlite3.connect('knotie.db')
    cursor = conn.cursor()
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
    conn.close()

init_sqlite_db()

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

def initialize_twilio_client():
    logger.info(f"Initiating Twilio client")
    global client
    client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)


# Initialize the clients at the start
initialize_twilio_client()
initialize_elevenlabs_client()

# Remove automatic AI client and tool initialization
# reinitialize_ai_clients()
# initialize_tools()


@app.route('/api/prompts', methods=['GET'])
def get_prompts():
    if 'logged_in' not in session:
        return jsonify({"error": "Not logged in"}), 403

    conn = sqlite3.connect('knotie.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, template FROM prompts')
    prompts = cursor.fetchall()
    conn.close()

    prompts_list = [{"name": prompt[0], "template": prompt[1]} for prompt in prompts]
    return jsonify(prompts_list)


@app.route('/api/prompts', methods=['PUT'])
def update_prompt():
    if 'logged_in' not in session:
        return jsonify({"error": "Not logged in"}), 403

    data = request.json
    prompt_name = data.get('name')
    prompt_template = data.get('template')

    if not prompt_name or not prompt_template:
        return jsonify({"error": "Invalid request data"}), 400

    conn = sqlite3.connect('knotie.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE prompts SET template = ? WHERE name = ?', (prompt_template, prompt_name))
    conn.commit()
    conn.close()

    return jsonify({"message": "Prompt updated successfully"}), 200


@app.route('/api/tools', methods=['GET'])
def get_tools():
    if 'logged_in' not in session:
        return jsonify({"error": "Not logged in"}), 403

    conn = sqlite3.connect('knotie.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, description, openapi_spec FROM tools')
    tools = cursor.fetchall()
    conn.close()

    tools_list = []
    for tool in tools:
        tools_list.append({
            "id": tool[0],
            "name": tool[1],
            "description": tool[2],
            "openapi_spec": tool[3]
        })

    return jsonify(tools_list)


# Route to serve the HTML template
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tools', methods=['POST'])
def add_tool():
    if 'logged_in' not in session:
        return jsonify({"error": "Not logged in"}), 403

    # Create the directory if it doesn't exist
    os.makedirs(GENERATED_TOOLS_DIR, exist_ok=True)

    tool_count = 0
    for key in request.form:
        if key.startswith('toolName'):
            tool_count += 1

    for i in range(1, tool_count + 1):
        tool_name = request.form[f'toolName{i}'].strip().replace(" ", "")
        tool_description = request.form[f'toolDescription{i}']
        tool_file = request.files[f'toolFile{i}']

        tool_sensitive_headers = request.form.get(f'toolSensitiveHeaders{i}', '')
        tool_sensitive_body = request.form.get(f'toolSensitiveBody{i}', '')

        # Save the OpenAPI spec file
        filename = secure_filename(tool_file.filename)
        tool_file_path = os.path.join(OPENAPI_DIR, filename)
        tool_file.save(tool_file_path)

        # Add tool to database and generate client
        add_tool_to_db(tool_name, tool_description, tool_file_path, tool_sensitive_headers, tool_sensitive_body)

    return jsonify({"message": "Tools added successfully"}), 200

# API endpoint for login
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    conn = sqlite3.connect('knotie.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        session['logged_in'] = True
        session['username'] = username
        first_login = user[3]
        return jsonify({'success': True, 'message': 'Login successful', 'first_login': first_login == 1})
    else:
        return jsonify({'success': False, 'message': 'Login failed'})

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'logged_in' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 403
    
    data = request.json
    new_password = data.get('new_password')
    
    conn = sqlite3.connect('knotie.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET password = ?, first_login = 0 WHERE username = ?', (new_password, session['username']))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Password changed successfully'})

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    return redirect(url_for('index'))

# Admin dashboard route
@app.route('/admin')
def admin():
    if 'logged_in' not in session:
        return redirect(url_for('index'))
    return render_template('admin.html')

# API endpoints for configuration
@app.route('/api/config', methods=['GET'])
def get_config():
    if 'logged_in' not in session:
        return jsonify({"error": "Not logged in"}), 403

    global config_data
    config_data = load_config()
    if not config_data:
        return jsonify({"error": "Configuration not set up"}), 404
    return jsonify(config_data)

@app.route('/api/config', methods=['POST'])
def update_config():
    if 'logged_in' not in session:
        return jsonify({"error": "Not logged in"}), 403

    new_config = request.json
    with open(config_path, 'w') as config_file:
        json.dump(new_config, config_file)

    global config_data
    config_data = new_config
    # Reload the configuration and reinitialize the Twilio client
    Config.update_dynamic_config()
    initialize_twilio_client()
    initialize_elevenlabs_client()
    reinitialize_ai_clients()
    initialize_tools()
    return jsonify({"message": "Config updated successfully"}), 200

@app.route('/api/chats', methods=['GET'])
def get_chats():
    if 'logged_in' not in session:
        return jsonify({"error": "Not logged in"}), 403

    # Fetch all keys (transaction IDs) from Redis
    keys = redis_client.keys('*')
    logger.info(f"list of keys are:  {keys}")
    return jsonify(keys)

@app.route('/api/chat/<transaction_id>', methods=['GET'])
def get_chat(transaction_id):
    if 'logged_in' not in session:
        return jsonify({"error": "Not logged in"}), 403

    # Fetch chat history for the given transaction ID from Redis
    chat_history = get_message_history(transaction_id)
    
    if not chat_history:
        return jsonify({"error": "No chat history found"}), 404
    
    return jsonify(chat_history)

@app.route('/audio/<filename>')
def serve_audio(filename):
    """Serve audio files from directory."""
    directory = 'audio_files'

    @after_this_request
    def remove_file(response):
        full_path = os.path.join(directory, filename)
        delayed_delete(full_path)
        return response

    try:
        return send_from_directory(directory, filename)
    except FileNotFoundError:
        logger.error(f"Audio file not found: {filename}")
        abort(404)
        
@app.route('/audio-stream')
def audio_stream():
    """Serve audio stream from text-to-speech conversion."""
    text = request.args.get('text')
    audio_stream = text_to_speech_stream(text)

    def generate():
        while True:
            chunk = audio_stream.read(1024)
            if not chunk:
                break
            yield chunk

    return Response(generate(), mimetype="audio/mpeg")

@app.route('/start-call', methods=['POST'])
def start_call():
    logger.info("Request recieved")
    """Endpoint to initiate a call."""
    unique_id = str(uuid.uuid4())
    message_history = []
    data = request.json
    customer_name = data.get('customer_name', 'Valued Customer')
    customer_phonenumber = data.get('customer_phonenumber', '')
    customer_businessdetails = data.get('customer_businessdetails', 'No details provided.')
    # Call AI_Helpers with customer_name, customer_businessdetails to create the initial response and return the response
    ai_message=process_initial_message(unique_id,customer_name,customer_businessdetails)
    response = VoiceResponse()
    if config_data.get("VOICE_MODE") == "ELEVENLABS_DIRECT":
        initial_message=clean_response(ai_message)
        audio_filename = process_elevenlabs_audio(initial_message)
        response.play(url_for('serve_audio', filename=secure_filename(audio_filename), _external=True))
    if config_data.get("VOICE_MODE") == "ELEVENLABS_STREAM":
        initial_message=clean_response(ai_message)
        audio_url = url_for('audio_stream', text=initial_message, _external=True)
        response.play(audio_url)
    if config_data.get("VOICE_MODE") == "TWILIO_DIRECT":
        initial_message=clean_response(ai_message)
        response.say(initial_message, voice='Google.en-GB-Standard-C', language='en-US')
    
    # save message history in redis
    initial_transcript = "Customer Name:" + customer_name + ". Customer's business Details as filled up in the website:" + customer_businessdetails
    logger.info(f"redirect url is:  {initial_transcript}")
    message_history.append({"role": "user", "content": initial_transcript})
    message_history.append({"role": "assistant", "content": initial_message})
    save_message_history(unique_id, message_history)

    redirect_url = f"{Config.APP_PUBLIC_GATHER_URL}?CallSid={unique_id}"
    public_url = f"{Config.APP_PUBLIC_EVENT_URL}"
    logger.info(f"redirect url is:  {redirect_url}")
    logger.info(f"App public url is:  {public_url}")
    response.redirect(redirect_url)
    call = client.calls.create(
        twiml=str(response),
        to=customer_phonenumber,
        from_=config_data.get("TWILIO_FROM_NUMBER"),
        method="GET",
        status_callback=public_url,
        status_callback_method="POST"
    )
    return jsonify({'message': 'Call initiated', 'call_sid': call.sid})

@app.route('/gather', methods=['GET', 'POST'])
def gather_input():
    """Endpoint to gather customer's speech input."""
    call_sid = request.args.get('CallSid', 'default_sid')
    resp = VoiceResponse()
    gather = Gather(input='speech', action=url_for('process_speech', CallSid=call_sid), speechTimeout='auto', method="POST")
    resp.append(gather)
    resp.redirect(url_for('gather_input', CallSid=call_sid))  # Redirect to itself to keep gathering if needed
    return str(resp)

@app.route('/gather-inbound', methods=['GET', 'POST'])
def gather_input_inbound():
    """Gathers customer's speech input for both inbound and outbound calls."""
    resp = VoiceResponse()
    print("Initializing for inbound call...")
    unique_id = str(uuid.uuid4())
    message_history = []
    agent_response= initiate_inbound_message(unique_id)

    if config_data.get("VOICE_MODE") == "ELEVENLABS_DIRECT":
        audio_filename = process_elevenlabs_audio(agent_response)
        resp.play(url_for('serve_audio', filename=secure_filename(audio_filename), _external=True))
    if config_data.get("VOICE_MODE") == "ELEVENLABS_STREAM":
        initial_message=clean_response(agent_response)
        audio_url = url_for('audio_stream', text=agent_response, _external=True)
        resp.play(audio_url)
    if config_data.get("VOICE_MODE") == "TWILIO_DIRECT":
        initial_message=clean_response(agent_response)
        resp.say(agent_response, voice='Google.en-GB-Standard-C', language='en-US')

    message_history.append({"role": "assistant", "content": agent_response})
    save_message_history(unique_id, message_history)
    resp.redirect(url_for('gather_input', CallSid=unique_id))
    return str(resp)

@app.route('/process-speech', methods=['POST'])
def process_speech():
    """Processes customer's speech input and generates a response."""
    speech_result = request.values.get('SpeechResult', '').strip()
    call_sid = request.args.get('CallSid', 'default_sid')
    message_history = get_message_history(call_sid)
    message_history.append({"role": "user", "content": speech_result})

    # 1. Generate a confirmation prompt (diverse)
    confirmation_prompt = generate_diverse_confirmation(speech_result)

    # 2. Play the confirmation prompt using ElevenLabs
    resp = VoiceResponse()
    response_text = clean_response(confirmation_prompt)
    
    audio_url = url_for('audio_stream', text=response_text, _external=True)
    resp.play(audio_url)
    

    # 3. Use Gather to listen for the user's confirmation response
    gather = Gather(
        input='speech',
        action=url_for('process_confirmation', CallSid=call_sid),  # Redirect to process_confirmation
        speechTimeout='2',  # Automatically stop gathering after the user has stopped speaking
        method='POST'
    )
    resp.append(gather)

    # 4. Start response generation in a separate thread
    thread = threading.Thread(target=generate_response_in_background, args=(call_sid, message_history, speech_result))
    thread.start()

    # Redirect to itself if no input is detected
    resp.redirect(url_for('handle_confirmation', CallSid=call_sid))

    return str(resp)

def generate_response_in_background(call_sid, message_history, user_input):
    """Generate AI response in the background while awaiting confirmation."""
    # Preprocess the next response while waiting for confirmation
    ai_response_text = process_message(call_sid, message_history, user_input)

    # Store the preprocessed response in Redis
    redis_client.set(f"response:{call_sid}", ai_response_text)

    # Optionally, set a timeout for the temporary storage in Redis
    redis_client.expire(f"response:{call_sid}", 300)  # Expires in 5 minutes

@app.route('/handle-confirmation', methods=['GET', 'POST'])
def handle_confirmation():
    """Handles the case where no input was detected during confirmation gathering."""
    call_sid = request.args.get('CallSid', 'default_sid')
    resp = VoiceResponse()

    # Repeat the prompt if no input was detected
    gather = Gather(
        input='speech',
        action=url_for('process_confirmation', CallSid=call_sid),  # Handle confirmation input again
        speechTimeout='auto',
        method='POST'
    )
    resp.append(gather)
    return str(resp)


@app.route('/process-confirmation', methods=['POST'])
def process_confirmation():
    """Processes the user's confirmation response."""
    confirmation_result = request.values.get('SpeechResult', '').strip().lower()
    call_sid = request.args.get('CallSid', 'default_sid')
    resp = VoiceResponse()

    # Fetch message history
    message_history = get_message_history(call_sid)

        # Define lists of positive and negative keywords
    positive_keywords = ["yes", "correct", "you're right", "ahha", "that's right", "right", "yeah", "yep", "affirmative", "sure", "absolutely", "indeed", "aha", "uh-huh", "mmm", "okay", "ok", "alright", "got it"]
    negative_keywords = ["no", "incorrect", "that's wrong", "wrong", "nope", "not quite", "negative", "not really", "no way", "uh-oh", "nah", "hmm", "huh-uh"]

    # 1. Check if the user's response indicates confirmation or correction
    if any(keyword in confirmation_result for keyword in positive_keywords):
        # User confirmed the AI's understanding
        logger.info(f'User confirmed yes')
        # Attempt to fetch the preprocessed AI response from Redis
        ai_response_text = redis_client.get(f"response:{call_sid}")

        # If the response is not ready yet, wait for a short period
        wait_time = 0  # Initialize wait time counter
        max_wait_time = 10  # Maximum time to wait in seconds

        while ai_response_text is None and wait_time < max_wait_time:
            logger.info(f'waiting for response from AI')
            time.sleep(1)  # Wait for 1 second
            wait_time += 1
            ai_response_text = redis_client.get(f"response:{call_sid}")  # Re-check if the response is ready

        # Handle if the response is still not available after waiting
        if ai_response_text:
            # Play the response using ElevenLabs
            response_text = clean_response(ai_response_text)
            audio_url = url_for('audio_stream', text=response_text, _external=True)
            resp.play(audio_url)

            # Clear the stored response after it has been played
            redis_client.delete(f"response:{call_sid}")
            message_history.append({"role": "assistant", "content": response_text})
            save_message_history(call_sid, message_history)
            # After playing the response, redirect to gather_input to continue the conversation
            resp.redirect(url_for('gather_input', CallSid=call_sid))
        else:
            # If response is still not available, apologize to the user
            resp.say("I'm sorry, I'm still processing your request. Please hold for a moment.")
            resp.redirect(url_for('handle_confirmation', CallSid=call_sid))
    
    elif any(keyword in confirmation_result for keyword in negative_keywords):
        # User indicated the AI's understanding was incorrect
        # Ask for input again
        gather = Gather(
            input='speech',
            action=url_for('process_speech', CallSid=call_sid),
            speechTimeout='auto',
            method="POST"
        )
        gather.say("I'm sorry, could you please repeat your input?")
        resp.append(gather)
    else:
        # If the input is not clearly positive or negative, prompt the user again
        gather = Gather(
            input='speech',
            action=url_for('process_confirmation', CallSid=call_sid),
            speechTimeout='auto',
            method="POST"
        )
        gather.say("I didn't catch that. Could you please say 'yes' or 'no'?")
        resp.append(gather)

    return str(resp)


@app.route('/event', methods=['POST'])
def event():
    """Handle status callback from Twilio calls."""
    call_status = request.values.get('CallStatus', '')
    if call_status in ['completed', 'busy', 'failed']:
        session.pop('message_history', None)  # Clean up session after the call
        logger.info(f"Call completed with status: {call_status}")
    return '', 204

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)