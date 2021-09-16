import datetime
import re
import os
import asyncio
from typing import List, Tuple
from bloxroute_cli.provider.cloud_wss_provider import WsProvider
from twilio.rest import Client
from dotenv import load_dotenv
import logging

# Initialize environment variables
load_dotenv()

# Requires a bloxroute subscription https://portal.bloxroute.com/
BLOXROUTE_AUTH_HEADER = os.environ.get("BLOXROUTE_AUTH_HEADER")
BLOXROUTE_WSS_URI = "wss://api.blxrbdn.com/ws"

# Optional Twilio support
SEND_TEXTS = os.environ.get("SEND_TEXTS", False) == "True"
TWILIO_NUM = os.environ.get("TWILIO_NUM")
MY_NUM = os.environ.get("MY_NUM")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

# Open the dictionary on all unix machines and parse it
file = open("/usr/share/dict/words", "r")
words = set(re.sub("[^\w]", " ", file.read()).split())

COMMON_SPAM = ["Mooncats", "Firebit", "ALBET.IO", "FLUF"]

logging.basicConfig()
logger = logging.getLogger("scraper")
logger.setLevel(logging.DEBUG)


# Check if it is a dictionary word
def is_word(word):
    return word.lower() in words


async def main():
    while True:
        # Constantly retry since websocket connection gets broken occasionally
        try:
            async with WsProvider(
                    uri=BLOXROUTE_WSS_URI,
                    headers={"Authorization": BLOXROUTE_AUTH_HEADER}
            ) as ws:
                subscription_id = await ws.subscribe("newTxs", {"include": ["tx_hash", "tx_contents"]})
                logger.info("feed started")
                while True:
                    next_notification = await ws.get_next_subscription_notification_by_id(subscription_id)
                    tx = next_notification.notification
                    input_data = tx["txContents"]["input"]
                    token_list, utf = get_token_list_utf(input_data)
                    print_string = ""
                    for token in token_list:
                        if len(token) > 1 and is_word(token):
                            print_string += token + " "
                    if len(print_string) > 3:
                        to_from = tx["txContents"]["from"] + " -> " + tx["txContents"]["to"] + "\n"
                        logger.info(to_from + print_string)
                        logger.debug(utf)
                        if SEND_TEXTS:
                            asyncio.create_task(send_text(to_from + print_string))

        except Exception as e:
            logger.error("Disconnection on " + str(datetime.datetime.now()) + str(e))
            await asyncio.sleep(2)


def get_token_list_utf(input_data: str) -> Tuple[List[str], str]:
    token_list = []
    utf = ""
    if len(input_data) > 2:
        utf = bytes.fromhex(input_data[2:]).decode("utf-8", "ignore")
        if utf.isascii():
            token_list = utf.split()
            if len(token_list) >= 2:
                spammy = any([item in token_list for item in COMMON_SPAM])
                if not spammy:
                    return token_list, utf
    return token_list, utf


async def send_text(body: str):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    client.messages \
        .create(
        body=body,
        from_=TWILIO_NUM,
        to=MY_NUM
    )


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
