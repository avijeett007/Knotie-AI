from openai import OpenAI, AssistantEventHandler
from typing_extensions import override
import time
from io import BytesIO
from audio_helpers import text_to_speech_stream

global assistant_id

class StreamingEventHandler(AssistantEventHandler):
    def __init__(self):
        self.partial_sentence = ""
        self.audio_stream = BytesIO()

    def get_audio_stream(self):
        self.audio_stream.seek(0)
        while True:
            chunk = self.audio_stream.read(1024)
            if not chunk:
                time.sleep(0.1)  # Wait briefly if there's no data yet
                continue
            yield chunk

    @override
    def on_text_delta(self, delta, snapshot):
        self.partial_sentence += delta.value

        if self.partial_sentence.endswith(('. ', '! ', '? ', '.\n', '!\n', '?\n')):
            speech_chunk = text_to_speech_stream(self.partial_sentence)
            for chunk in speech_chunk:
                self.audio_stream.write(chunk)
            self.audio_stream.flush()  # Ensure all data is written
            self.partial_sentence = ""  # Reset the sentence buffer

def add_message_to_thread(thread_id, user_input):
    """Add user input as a message to the thread and stream the assistant's response."""
    # Add the user message to the thread
    message = openai.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_input
    )
    print("User Message Added:", message)

    # Stream the assistant's response
    audio_stream_generator = gen_ai_output_stream(thread_id)
    return audio_stream_generator  # Return the audio stream generator for real-time playback


def gen_ai_output_stream(thread_id, instructions=None):
    event_handler = StreamingEventHandler()
    
    with openai.beta.threads.runs.stream(
        thread_id=thread_id,
        assistant_id=assistant_id,
        event_handler=event_handler,
        instructions=instructions,  # These are run-specific instructions
    ) as stream:
        stream.until_done()
    
    return event_handler.get_audio_stream()  # Return the generator


def add_message_to_thread(thread_id, user_input):
    event_handler = StreamingEventHandler()
    
    with openai.beta.threads.runs.stream(
        thread_id=thread_id,
        assistant_id=assistant_id,
        event_handler=event_handler,
        instructions=instructions,  # These are run-specific instructions
    ) as stream:
        stream.until_done()
    
    return event_handler.get_audio_stream()  # Return the generator

def initiate_assistant():
    """Create/Initiate Assistant During Application Start Up When Assistant is Enabled using Assistant Prompt. Save the
    assistant id as global variable to access it anywhere across the app."""
    global assistant_id
    conn = sqlite3.connect('knotie.db')
    cursor = conn.cursor()

    # Load the system prompt from the database
    cursor.execute('SELECT template FROM prompts WHERE name = "AGENT_STARTING_PROMPT_TEMPLATE"')
    result = cursor.fetchone()
    initial_prompt = result[0] if result else ""

    # Create the assistant
    assistant = openai.beta.assistants.create(
        model="gpt-4o-mini",  # Or whichever model you're using
        temperature=0.2,
        instructions=initial_prompt,
    )
    assistant_id = assistant.id  # Save the assistant ID globally
    conn.close()
    print(f"Assistant Created: {assistant_id}")


def update_assistant_prompt():
    """Update assistant when system prompt for the assistant is changed. It should load the Assistant System Prompt from
    the database as latest available and then call OpenAI Assistant update API to update the assistant"""
    global assistant_id
    conn = sqlite3.connect('knotie.db')
    cursor = conn.cursor()

    # Load the updated system prompt
    cursor.execute('SELECT template FROM prompts WHERE name = "AGENT_STARTING_PROMPT_TEMPLATE"')
    result = cursor.fetchone()
    updated_prompt = result[0] if result else ""

    # Update the assistant with the new prompt
    openai.beta.assistants.update(
        assistant_id=assistant_id,
        instructions=updated_prompt,
    )
    conn.close()
    print("Assistant Prompt Updated.")

def update_assistant_tools():
    """Update assistant when new tools/custom functions are added to assistant. It should load all the tool names, tool descriptions 
    and openapi specs then transform it into required custom functions to update OpenAI Assistant with all the tools"""
    global assistant_id
    conn = sqlite3.connect('knotie.db')
    cursor = conn.cursor()

    # Load all the tools and their specifications
    cursor.execute('SELECT name, description, openapi_spec FROM tools')
    tools = cursor.fetchall()

    # Prepare tools list for OpenAI API
    tools_list = []
    for tool in tools:
        tools_list.append({
            "type": "function",
            "name": tool[0],
            "description": tool[1],
            "spec": tool[2],
        })

    # Update the assistant with the new tools
    openai.beta.assistants.update(
        assistant_id=assistant_id,
        tools=tools_list,
    )
    conn.close()
    print("Assistant Tools Updated.")

def create_thread(call_sid):
    """Create a OpenAI Thread by using OpenAI Thread API. Then Save it against the call_sid and assistant id"""
    thread = openai.beta.threads.create()
    
    # Save thread ID and associate it with the call SID
    conn = sqlite3.connect('knotie.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO assistants (assistant_id, conversation_id, thread_id) VALUES (?, ?, ?)',
                   (assistant_id, call_sid, thread.id))
    conn.commit()
    conn.close()
    
    print(f"Thread Created for Call SID {call_sid}: {thread.id}")
    return thread.id






