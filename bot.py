import logging
import json
import os
import httpx
from telethon import TelegramClient, events
from telethon.tl.custom import Button

# Configure logging to file and reduce verbosity for Telethon
logging.basicConfig(filename='bot.log', level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('telethon').setLevel(logging.WARNING)  # Only log warnings and above

#///////////////////////////////////////////////////
#          Made by v0idworks software 2024          
#///////////////////////////////////////////////////
# Define your API credentials and owner ID
API_ID = ''  # Replace with your API ID
API_HASH = ''  # Replace with your API Hash
TOKEN = ''  # Replace with your Bot Token
OWNER_ID = ''  # Replace with your Telegram user ID

# Initialize bot with the bot token
client = TelegramClient('bot', API_ID, API_HASH).start(bot_token=TOKEN)
HISTORY_FILE = "suser_histories.json"
# Load user histories from the file if it exists
if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r") as f:
            user_histories = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logging.error(f"Error loading user histories: {e}")
        user_histories = {}  # Initialize to an empty dictionary if loading fails
else:
    user_histories = {}
def save_histories():
    logging.debug("Saving user histories to file.")
    with open(HISTORY_FILE, "w") as f:
        json.dump(user_histories, f, indent=4)

# Global stream status for all users
stream_status = False
# To track if a user is in session creation or deletion mode
session_creation_mode = {}
session_deletion_mode = {}

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.respond("Hello! Ask me anything using /ask <question>. Use /sessions to manage your sessions (owner only).")

@client.on(events.NewMessage(pattern='/sessions'))
async def manage_sessions(event):
    user_id = str(event.sender_id)

    if user_id not in user_histories:
        user_histories[user_id] = {}

    user_sessions = user_histories[user_id]
    
    # Create a message listing existing sessions
    session_list = "\n".join(user_sessions.keys()) if user_sessions else "No sessions found."
    session_message = f"Your sessions:\n{session_list}\n\nUse the buttons below to create or delete a session."
    
    buttons = [
        Button.inline("Create New Session", b"create_session"),
        Button.inline("Delete Session", b"delete_session"),
    ]

    await event.respond(session_message, buttons=buttons)

@client.on(events.CallbackQuery(data=b"create_session"))
async def create_session(event):
    user_id = str(event.sender_id)
    session_creation_mode[user_id] = True  # Set the user in session creation mode
    await event.respond("Please send the name of the new session:")
    
    @client.on(events.NewMessage())
    async def new_session(session_event):
        if session_event.sender_id != event.sender_id:
            return  # Ignore messages from other users

        if user_id in session_creation_mode and session_creation_mode[user_id]:
            session_name = session_event.message.message.strip()

            if session_name in user_histories.get(user_id, {}):
                await session_event.respond("Session already exists! Choose a different name.")
                return

            # Create a new session
            user_histories[user_id][session_name] = []
            save_histories()
            await session_event.respond(f"Session '{session_name}' created successfully!")

            # Remove session creation mode for the user
            session_creation_mode[user_id] = False
            await manage_sessions(event)

            # Remove the event listener
            client.remove_event_handler(new_session)

@client.on(events.CallbackQuery(data=b"delete_session"))
async def delete_session(event):
    user_id = str(event.sender_id)
    session_deletion_mode[user_id] = True  # Set the user in session deletion mode
    await event.respond("Please send the name of the session you want to delete:")

    @client.on(events.NewMessage())
    async def session_deletion(session_event):
        if session_event.sender_id != event.sender_id:
            return  # Ignore messages from other users

        if user_id in session_deletion_mode and session_deletion_mode[user_id]:
            session_name = session_event.message.message.strip()

            if session_name in user_histories.get(user_id, {}):
                del user_histories[user_id][session_name]  # Delete the session
                save_histories()
                await session_event.respond(f"Session '{session_name}' deleted successfully!")
            else:
                await session_event.respond("Session not found!")

            # Remove session deletion mode for the user
            session_deletion_mode[user_id] = False
            await manage_sessions(event)

            # Remove the event listener
            client.remove_event_handler(session_deletion)

@client.on(events.NewMessage(pattern='/panel'))
async def show_panel(event):
    user_id = str(event.sender_id)

    if user_id != OWNER_ID:
        await event.respond("You are not authorized to access this panel.")
        logging.warning(f"Unauthorized access attempt by user {user_id}.")
        return

    current_status = 'On' if stream_status else 'Off'
    button_stream = Button.inline(f"Toggle Stream Response (Currently {current_status})", b"toggle_stream")
    
    await event.respond("Settings Panel:", buttons=[button_stream])

@client.on(events.CallbackQuery(data=b"toggle_stream"))
async def toggle_stream_response(event):
    global stream_status
    user_id = str(event.sender_id)

    if user_id != OWNER_ID:
        await event.answer("You are not authorized to perform this action.", alert=True)
        logging.warning(f"Unauthorized toggle attempt by user {user_id}.")
        return

    stream_status = not stream_status
    current_status = 'On' if stream_status else 'Off'
    await event.edit("Settings Panel:", buttons=[Button.inline(f"Toggle Stream Response (Currently {current_status})", b"toggle_stream")])
    await event.answer(f"Stream response mode toggled! Currently {current_status}.")

@client.on(events.NewMessage(pattern='/ask'))
async def ask(event):
    question = event.message.message.split(maxsplit=1)[1] if event.message.message else ""

    if not question:
        await event.respond("Please provide a question. Usage: /ask <question>")
        return

    logging.debug(f"Received question: {question}")

    user_id = str(event.sender_id)
    user_sessions = user_histories.get(user_id, {})
    selected_session = user_sessions.get('selected_session', 'default')

    # Retrieve the conversation history for the selected session, or start a new one
    history = user_sessions.get(selected_session, [])

    # Add the user's current message to the conversation history
    history.append({
        "role": "user",
        "content": question
    })

    # Payload for the prompt
    data = {
        "model": "llama3",
        "messages": history,
        "stream": stream_status
    }
    url = "http://localhost:11434/api/chat"

    try:
        thinking_message = await event.respond("🤔 Thinking...")

        # Make the request to the server
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=data)
            response.raise_for_status()

            response_text = response.text
            logging.debug(f"Raw response: {response_text}")

            # JSON Parsing Logic
            try:
                start_index = response_text.find('{')
                end_index = response_text.rfind('}') + 1
                json_part = response_text[start_index:end_index]
                response_data = json.loads(json_part)
                content = response_data.get("message", {}).get("content", "No content found.")

                # Add the assistant's response to the conversation history
                history.append({
                    "role": "assistant",
                    "content": content
                })

                await thinking_message.edit(f"✅ <b>Response:</b>\n{content}")

            except json.JSONDecodeError as e:
                content = f"Failed to parse JSON response: {str(e)}"
                logging.error(content)
                await thinking_message.edit(f"❗ {content}")

        # Save the updated session history
        user_sessions[selected_session] = history
        user_histories[user_id] = user_sessions
        save_histories()

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 500:
            await thinking_message.edit('❗ Timeout Error, please ask the AI to provide a shorter answer.')
            logging.error('Timeout error.')
        else:
            await thinking_message.edit(f"❗ Server error: {exc.response.status_code}")
            logging.error(f"http error: {exc.response.status_code}")
    except Exception as e:
        await thinking_message.edit(f"❗ Epic fail, here's what caused the error: {str(e)}")
        logging.error(f"error: {str(e)}")

if __name__ == '__main__':
    client.run_until_disconnected()
