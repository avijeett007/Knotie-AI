from flask import Flask, request, jsonify, render_template, session, redirect, url_for, Response, send_from_directory, abort, after_this_request
from flask_session import Session
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
from werkzeug.utils import secure_filename
from langchain_core.prompts import PromptTemplate
from flask_cors import CORS
import os
import subprocess
import requests
from audio_helpers import text_to_speech, text_to_speech_stream, save_audio_file, initialize_elevenlabs_client
from ai_helpers import process_initial_message, process_message, initiate_inbound_message, reinitialize_ai_clients
from appUtils import clean_response, delayed_delete, save_message_history, get_message_history, process_elevenlabs_audio
from config import Config
import logging
import threading
import time
import redis
import json
from urllib.parse import quote_plus
import uuid
import sqlite3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# SQLite setup for user management
def init_sqlite_db():
    conn = sqlite3.connect('users.db')
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
    
    conn.close()

init_sqlite_db()

# Twilio client initialization
client = None

def initialize_twilio_client():
    logger.info(f"Initiating Twilio client")
    global client
    client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)


# Initialize the clients at the start
initialize_twilio_client()
initialize_elevenlabs_client()
reinitialize_ai_clients()


# Route to serve the HTML template
@app.route('/')
def index():
    return render_template('index.html')

# API endpoint for login
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    conn = sqlite3.connect('users.db')
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
    
    conn = sqlite3.connect('users.db')
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

    # Fetch AI Response based on tool calling wherever required.
    start_time = time.time()
    ai_response_text = process_message(call_sid,message_history,speech_result)
    resp = VoiceResponse()
    end_time = time.time()
    elapsed_time_ms = (end_time - start_time) * 1000

    start_time = time.time()
    # Print the elapsed time
    logger.info(f"Elapsed latency by AI Model for producing response: {elapsed_time_ms:.2f} ms")
    if config_data.get("VOICE_MODE") == "ELEVENLABS_DIRECT":
        response_text=clean_response(ai_response_text)
        audio_filename = process_elevenlabs_audio(response_text)
        resp.play(url_for('serve_audio', filename=secure_filename(audio_filename), _external=True))
    if config_data.get("VOICE_MODE") == "ELEVENLABS_STREAM":
        response_text=clean_response(ai_response_text)
        audio_url = url_for('audio_stream', text=response_text, _external=True)
        resp.play(audio_url)
    if config_data.get("VOICE_MODE") == "TWILIO_DIRECT":
        response_text=clean_response(ai_response_text)
        resp.say(response_text, voice='Google.en-GB-Standard-C', language='en-US')

    end_time = time.time()
    elapsed_time_ms = (end_time - start_time) * 1000
    logger.info(f"Elapsed latency for text to speech API: {elapsed_time_ms:.2f} ms")

    if "<END_OF_CALL>" in ai_response_text:
        print("The conversation has ended.")
        resp.hangup()
    resp.redirect(url_for('gather_input', CallSid=call_sid))
    message_history.append({"role": "user", "content": speech_result})
    message_history.append({"role": "assistant", "content": response_text})
    save_message_history(call_sid, message_history)
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
# if __name__ == '__main__':
#     def start_ngrok():
#         # Get the Ngrok auth token from the environment variable or config
#         ngrok_auth_token = os.getenv('NGROK_AUTH_TOKEN', Config.get('NGROK_AUTH_TOKEN'))
        
#         if not ngrok_auth_token:
#             raise ValueError("Ngrok auth token is not set. Please set NGROK_AUTH_TOKEN in config.json or as an environment variable.")

#         # Start ngrok process with auth token
#         ngrok_process = subprocess.Popen(['ngrok', 'http', '5000', '--authtoken', ngrok_auth_token], stdout=subprocess.PIPE)
        
#         # Give ngrok some time to start
#         time.sleep(3)
        
#         # Get the public URL from ngrok's API
#         response = requests.get('http://localhost:4040/api/tunnels')
#         data = response.json()
#         public_url = data['tunnels'][0]['public_url']
#         return public_url

#     # Check if we should use Ngrok
#     if Config.get("USE_NGROK", False):
#         # Start ngrok and get the public URL
#         public_url = start_ngrok()
#         print(f" * ngrok tunnel opened at {public_url}")

#         # Update the configuration with the ngrok public URL
#         Config.APP_PUBLIC_GATHER_URL = public_url + "/gather"
#         Config.APP_PUBLIC_EVENT_URL = public_url + "/event"
#     else:
#         print(" * Ngrok is disabled. Please ensure your own reverse proxy is configured.")

#     # Start the Flask app
#     app.run(debug=True, host='0.0.0.0', port=5000)