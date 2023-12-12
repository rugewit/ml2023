#!/usr/bin/python3

import os
import json
import uuid
import requests

from flask import Flask
from flask import request
from flask import Response
from pyngrok import ngrok
from dotenv  import load_dotenv

from api_wrapper import MlApi

# from googletrans import Translator

from telegram_api import SimpleTelegramApi
from model_formatter import ModelFormatter

# config = configparser.ConfigParser()
# config.read('telegram_bot.ini')
load_dotenv()

telegram_token = os.getenv("tg_token")
api_url  = os.getenv('api_url')
api_port = os.getenv('api_port')
print('telegram token:', telegram_token)

# translator = Translator()
ml_api = MlApi(api_url, api_port)

model_formatter = ModelFormatter()

class TunneledApp(Flask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.http_tunnel = None
        self.last_msg_id = None
        self.telapi = SimpleTelegramApi(telegram_token)

        self.http_tunnel = ngrok.connect('5000', "http")
        self.telapi.setup_webhook(self.http_tunnel.public_url)
        print('Ngrok url:', self.http_tunnel.public_url)
        print()

    def parse_message(self, message):
        print("message -->", json.dumps(message, indent=4, ensure_ascii=False))

        message_key = 'message'
        if 'edited_message' in message:
            message_key = 'edited_message'

        sjon = {
            'chat_id': message[message_key]['chat']['id'],
            'msg_id':  message[message_key]['message_id'],
            'msg_txt': message[message_key]['text'],
        }

        return sjon

    def tel_send_message(self, chat_id, text):
        r = self.telapi.send_message(chat_id, text)
        if r.get('ok'):
            self.last_msg_id = r['result']['message_id']

        print('last_msg_id:', self.last_msg_id)

    def process_message_text(self, chat_id, msg_id, text):
        # response = translator.translate(text)

        try:
            tokens = text.split()
            print('tokens:', tokens)
            if tokens[0].lower() in ['raw_get', 'get', 'rawget']:
                _id = tokens[-1]
                text = ml_api.get_car(uuid.UUID(_id)).text
                text = model_formatter.format(text)
            else:
                text = '=^.^='
        except Exception as e:
            text = str(e)

        return text

    def process_message(self, msg):
        sjson = self.parse_message(msg)
        response = app.process_message_text(
            sjson['chat_id'],
            sjson['msg_id'],
            sjson['msg_txt'],
        )

        # self.telapi.delete_message(sjson['chat_id'], sjson['msg_id'])
        # if self.last_msg_id:
        #     print('last_msg_id:', self.last_msg_id)
        #     r = self.telapi.edit_message(sjson['chat_id'], self.last_msg_id, response)
        #     if not r.get('ok') and r.get(
        #             'description') != 'Bad Request: message is not modified: specified new message content and reply markup are exactly the same as a current content and reply markup of the message':
        #         self.tel_send_message(sjson['chat_id'], response)
        # else:
        self.tel_send_message(sjson['chat_id'], response)

def create_app():
    tele_app = TunneledApp(__name__)
    # app.setup_webhook()

    @tele_app.route('/', methods=['GET', 'POST'])
    def index():
        if request.method == 'POST':
            msg = request.get_json()

            tele_app.process_message(msg)
        
            return Response('ok', status=200)
        else:
            return "<h1>Welcome!</h1>"
 
    return tele_app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, use_reloader=False)
