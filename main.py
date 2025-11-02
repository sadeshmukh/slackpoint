import logging
import os
import dotenv
from cachetools import TTLCache
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient


dotenv.load_dotenv()

logging.basicConfig(level=logging.INFO)

cache = TTLCache(maxsize=100, ttl=300)

if not os.getenv("SLACK_BOT_TOKEN") or not os.getenv("SLACK_APP_TOKEN"):
    logging.error("SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set in environment variables.")
    exit(1)

app = App(token=os.getenv("SLACK_BOT_TOKEN"))
client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

def get_checkpoints_data(client, channel_id, message_ts, cache):
    """Helper function to get checkpoints data - shared between shortcuts"""
    cache_key = f"{channel_id}:{message_ts}"

    # join if not in channel
    try:    
        membership_cache_key = f"membership:{channel_id}"
        
        if membership_cache_key in cache:
            is_member = cache[membership_cache_key]
        else:
            members_result = client.conversations_members(channel=channel_id, limit=1000)
            bot_user_id = client.auth_test()["user_id"]
            
            members = members_result.get("members", [])
            is_member = bot_user_id in members

            cache[membership_cache_key] = is_member

        if not is_member:
            client.conversations_join(channel=channel_id)
            cache[membership_cache_key] = True
            logging.info(f"Successfully joined channel {channel_id}")
        else:
            logging.info(f"Bot is already a member of channel {channel_id}")
            
    except Exception as channel_error:
        logging.warning(f"Could not check/join channel {channel_id}: {channel_error}")

    if cache_key in cache:
        replies = cache[cache_key]
    else:
        result = client.conversations_replies(channel=channel_id, ts=message_ts, thread_ts=message_ts)
        messages = result.get("messages", [])
        replies = messages[1:] if len(messages) > 1 else []
        cache[cache_key] = replies

    checkpoints = []
    for i in range(99, len(replies), 100):
        reply_ts = replies[i]["ts"]
        link = f"https://hackclub.slack.com/archives/{channel_id}/p{reply_ts.replace('.', '')}?thread_ts={message_ts}&cid={channel_id}"
        checkpoints.append(f"<{link}|{i + 1}>")

    if len(replies) > 0 and (len(replies) - 1) % 100 != 99:
        last_reply_ts = replies[-1]["ts"]
        last_link = f"https://hackclub.slack.com/archives/{channel_id}/p{last_reply_ts.replace('.', '')}?thread_ts={message_ts}&cid={channel_id}"
        checkpoints.append(f"<{last_link}|{len(replies)}>")

    return replies, checkpoints


@app.shortcut("generate_checkpoints")
def generate_checkpoints(ack, body, client: WebClient):
    ack()
    try:
        channel_id = body["channel"]["id"]
        message_ts = body["message"]["ts"]
        
        replies, checkpoints = get_checkpoints_data(client, channel_id, message_ts, cache)

        if checkpoints:
            checkpoint_message = f"Checkpoints for thread with {len(replies)} replies:\n" + " | ".join(checkpoints)
        else:
            checkpoint_message = "Not enough replies to generate checkpoints."

        client.chat_postEphemeral(
            channel=channel_id,
            user=body["user"]["id"],
            text=checkpoint_message
        )
    except Exception as e:
        logging.error(f"Error generating checkpoints: {e}")


@app.shortcut("checkpoints_modal")
def checkpoints_modal(ack, body, client: WebClient):
    ack()
    try:
        channel_id = body["channel"]["id"]
        message_ts = body["message"]["ts"]
        
        replies, checkpoints = get_checkpoints_data(client, channel_id, message_ts, cache)

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Thread Checkpoints ({len(replies)} replies)"
                }
            },
            {
                "type": "divider"
            }
        ]

        if checkpoints:
            checkpoint_buttons = []
            for checkpoint in checkpoints:
                link_start = checkpoint.find('<') + 1
                link_end = checkpoint.find('|')
                reply_end = checkpoint.find('>')
                
                link_url = checkpoint[link_start:link_end]
                reply_number = checkpoint[link_end+1:reply_end]
                
                checkpoint_buttons.append({
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": f"Reply #{reply_number}"
                    },
                    "url": link_url,
                    "style": "primary"
                })
            
            button_groups = [checkpoint_buttons[i:i+5] for i in range(0, len(checkpoint_buttons), 5)]
            
            for group in button_groups:
                blocks.append({
                    "type": "actions",
                    "elements": group
                })
        else:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Not enough replies to generate checkpoints. This thread needs at least 100 replies."
                }
            })

        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "title": {
                    "type": "plain_text",
                    "text": "Thread Checkpoints"
                },
                "close": {
                    "type": "plain_text",
                    "text": "Close"
                },
                "blocks": blocks
            }
        )
    except Exception as e:
        logging.error(f"Error opening checkpoints modal: {e}")


handler = SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN"))
if __name__ == "__main__":
    handler.start()