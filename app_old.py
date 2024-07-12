# This code is licensed under the Custom License for Paid Community Members.
# For more information, see the LICENSE file in the root directory of this repository.


from flask import Flask, request, jsonify, url_for, after_this_request, session, send_from_directory, abort, Response  # Added Response import
from flask_session import Session
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
from werkzeug.utils import secure_filename
from langchain_core.prompts import PromptTemplate
import os
from audio_helpers import text_to_speech, text_to_speech_stream, save_audio_file
from ai_helpers import process_initial_message, process_message, initiate_inbound_message
from appUtils import clean_response, delayed_delete, save_message_history, get_message_history, process_elevenlabs_audio
from config import Config
import logging
import threading
import time
import redis
import json
from urllib.parse import quote_plus
import uuid
import logging
import time



# redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config.from_object(Config)
# Session configuration
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False  # You can set True for permanent sessions
app.config['SESSION_USE_SIGNER'] = True  # Securely sign the session
app.config['SESSION_REDIS'] = redis.from_url('redis://redis:6379')
Session(app)
app.logger.setLevel(logging.DEBUG)

client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)


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
    if Config.VOICE_MODE == "ELEVENLABS_DIRECT":
        initial_message=clean_response(ai_message)
        audio_filename = process_elevenlabs_audio(initial_message)
        response.play(url_for('serve_audio', filename=secure_filename(audio_filename), _external=True))
    if Config.VOICE_MODE == "ELEVENLABS_STREAM":
        initial_message=clean_response(ai_message)
        audio_url = url_for('audio_stream', text=initial_message, _external=True)
        response.play(audio_url)
    if Config.VOICE_MODE == "TWILIO_DIRECT":
        initial_message=clean_response(ai_message)
        response.say(initial_message, voice='Google.en-GB-Standard-C', language='en-US')
    
    # save message history in redis
    initial_transcript = "Customer Name:" + customer_name + ". Customer's business Details as filled up in the website:" + customer_businessdetails
    message_history.append({"role": "user", "content": initial_transcript})
    message_history.append({"role": "assistant", "content": initial_message})
    save_message_history(unique_id, message_history)

    # redis_client.set(unique_id, json.dumps(message_history))

    redirect_url = f"{Config.APP_PUBLIC_GATHER_URL}?CallSid={unique_id}"
    response.redirect(redirect_url)
    call = client.calls.create(
        twiml=str(response),
        to=customer_phonenumber,
        from_=Config.TWILIO_FROM_NUMBER,
        method="GET",
        status_callback=Config.APP_PUBLIC_EVENT_URL,
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
    # session['message_history'] = []
    message_history = []
    agent_response= initiate_inbound_message(unique_id)

    if Config.VOICE_MODE == "ELEVENLABS_DIRECT":
        audio_filename = process_elevenlabs_audio(agent_response)
        resp.play(url_for('serve_audio', filename=secure_filename(audio_filename), _external=True))
    if Config.VOICE_MODE == "ELEVENLABS_STREAM":
        initial_message=clean_response(agent_response)
        audio_url = url_for('audio_stream', text=agent_response, _external=True)
        resp.play(audio_url)
    if Config.VOICE_MODE == "TWILIO_DIRECT":
        initial_message=clean_response(agent_response)
        resp.say(agent_response, voice='Google.en-GB-Standard-C', language='en-US')

    message_history.append({"role": "assistant", "content": agent_response})
    save_message_history(unique_id, message_history)
    # redis_client.set(unique_id, json.dumps(message_history))
    resp.redirect(url_for('gather_input', CallSid=unique_id))
    return str(resp)


@app.route('/process-speech', methods=['POST'])
def process_speech():
    """Processes customer's speech input and generates a response."""
    
    speech_result = request.values.get('SpeechResult', '').strip()
    call_sid = request.args.get('CallSid', 'default_sid')
    print(call_sid)
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
    if Config.VOICE_MODE == "ELEVENLABS_DIRECT":
        response_text=clean_response(ai_response_text)
        audio_filename = process_elevenlabs_audio(response_text)
        resp.play(url_for('serve_audio', filename=secure_filename(audio_filename), _external=True))
    if Config.VOICE_MODE == "ELEVENLABS_STREAM":
        response_text=clean_response(ai_response_text)
        audio_url = url_for('audio_stream', text=response_text, _external=True)
        resp.play(audio_url)
    if Config.VOICE_MODE == "TWILIO_DIRECT":
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
