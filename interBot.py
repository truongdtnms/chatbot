# -*- coding: utf-8 -*-
from __future__ import absolute_import

import imp
import importlib
import logging
import os
import re
import time
import traceback
import json
import sys
from glob import glob
from six.moves import _thread, queue
from six import iteritems
from mmpy_bot.mattermost import MattermostAPI
from mmpy_bot import settings
from mmpy_bot.dispatcher import MessageDispatcher
from mmpy_bot.mattermost import MattermostClient
from mmpy_bot.scheduler import schedule

from functools import wraps

teams = {}
default_team_id = None
teams_channels_ids = {}
teams_names = {}
channels_names = {}
channels_members = {}
mm_members = {}
rasa_mapping = {}  # user_id -> conversation_id & channel_id
rasa_channel_id = None
rasa_conversation_id = None
rasa_url = 'http://localhost:5005'

ADMIN_ID = '7ey16tgu1jbyp8pdzuiwphohao'
WORKER_ID = '7ao9ctoga7g9fxxwj3fes86r4o'

logger = logging.getLogger(__name__)

MESSAGE_MATCHER = re.compile(r'^(@.*?\:?)\s(.*)', re.MULTILINE | re.DOTALL)
BOT_ICON = settings.BOT_ICON if hasattr(settings, 'BOT_ICON') else None
BOT_EMOJI = settings.BOT_EMOJI if hasattr(settings, 'BOT_EMOJI') else None
BOT_URL = 'http://192.168.88.187:8065/api/v4'
BOT_LOGIN = 'worker@nms.com.vn'
BOT_PASSWORD = 'Password@worker1'
BOT_TEAM = 'rasabot'
BOT_CHANNEL = 'bot'
map = []
users_sp = []
channels_mm = []


class WorkerPool(object):
    def __init__(self, func, num_worker=10):
        self.num_worker = num_worker
        self.func = func
        self.queue = queue.Queue()
        self.busy_workers = queue.Queue()

    def start(self):
        for _ in range(self.num_worker):
            _thread.start_new_thread(self.do_work, tuple())

    def add_task(self, msg):
        self.queue.put(msg)

    def get_busy_workers(self):
        return self.busy_workers.qsize()

    def do_work(self):
        while True:
            msg = self.queue.get()
            self.busy_workers.put(1)
            self.func(msg)
            self.busy_workers.get()


class MessageDispatcher(object):
    def __init__(self, client):
        self._client = client
        self._pool = WorkerPool(self.dispatch_msg, settings.WORKERS_NUM)
        self._channel_info = {}
        self.event = None

    def start(self):
        self._pool.start()

    @staticmethod
    def get_message(msg):
        return msg.get('data', {}).get('post', {}).get('message', '').strip()

    @staticmethod
    def get_sender(msg):
        return msg.get('data', {}).get('sender_name', '').strip()

    def ignore(self, _msg):
        return self._ignore_notifies(_msg) or self._ignore_sender(_msg)

    def _ignore_notifies(self, _msg):
        # ignore message containing specified item, such as "@all"
        msg = self.get_message(_msg)
        return True if any(
            item in msg for item in settings.IGNORE_NOTIFIES) else False

    def _ignore_sender(self, _msg):
        # ignore message from senders specified in settings
        sender_name = self.get_sender(_msg)
        return True if sender_name.lower() in (
            name.lower() for name in settings.IGNORE_USERS) else False

    def is_mentioned(self, msg):
        mentions = msg.get('data', {}).get('mentions', [])
        return self._client.user['id'] in mentions

    def is_personal(self, msg):
        try:
            channel_id = msg['data']['post']['channel_id']
            if channel_id in self._channel_info:
                channel_type = self._channel_info[channel_id]
            else:
                channel = self._client.api.channel(channel_id)
                channel_type = channel['channel']['type']
                self._channel_info[channel_id] = channel_type
            return channel_type == 'D'
        except KeyError:
            logger.info('Once time workpool exception caused by \
                         bot [added to/leave] [team/channel].')
            return False

    def dispatch_msg(self, msg):
        category = msg[0]
        msg = msg[1]
        text = self.get_message(msg)
        responded = False
        msg['message_type'] = '?'
        if self.is_personal(msg):
            msg['message_type'] = 'D'
        # print(msg)
        self.reply(msg)

    def _on_new_message(self, msg):
        if self.ignore(msg) is True:
            return

        msg = self.filter_text(msg)
        if self.is_mentioned(msg) or self.is_personal(msg):
            self._pool.add_task(('respond_to', msg))
        else:
            self._pool.add_task(('listen_to', msg))

    def filter_text(self, msg):
        text = self.get_message(msg)
        if self.is_mentioned(msg):
            m = MESSAGE_MATCHER.match(text)
            if m:
                msg['data']['post']['message'] = m.group(2).strip()
        return msg

    def load_json(self):
        for item in ['post', 'mentions']:
            if self.event.get('data', {}).get(item):
                self.event['data'][item] = json.loads(
                    self.event['data'][item])

    def loop(self):
        logger.info('start loop in class MessageDispatcher')
        for self.event in \
                self._client.messages(False, ['posted', 'added_to_team',
                                              'leave_team', 'user_added',
                                              'user_removed']):
            if self.event:
                # logger.info(str(self.event))
                # logger.info(type(self.event))
                self.load_json()
                self._on_new_message(self.event)
        logger.info('Loop')

    @staticmethod
    def post_message_to_rasa(message, rasa_conversation_id, rasa_channel_id):
        import requests
        url = "{}/conversations/{}/trigger_intent?output_channel={}".format(rasa_url, rasa_conversation_id,
                                                                            rasa_channel_id)
        payload = ''
        if message == "done":
            payload = {"name": "active_bot_agent", "entities": {}}
        else:
            payload = {"name": "human_reply", "entities": {"text": "{}".format(message)}}

        headers = {
            'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=json.dumps(payload))

    def post_message_to_mattermost(self, message, channel_id):
        self._client.channel_msg(channel_id, message)

    def load_users_channels(self):
        # while True:
        global users_sp, channels_mm, map
        channels_mm = self._client.get_channels_mm()
        users_sp = self._client.get_users_sp()
            # logger.info('-------' + str(users_sp) + " " + str(channels_mm) + str(map))
            # time.sleep(5)
    def reply(self, msg):
        global users_sp
        global map
        if channels_names[msg['data']['post']['channel_id']] == 'bot':
            # logger.info("----------" + str(msg))
            _user = mm_members[msg['data']['post']['user_id']]
            # logger.info("----------" + str(_user))
            if (_user['username']) == 'bot1':
                _text = self.get_message(msg)
                try:
                    data = json.loads(_text)
                except:
                    return
                if data['channel_id']:
                    rasa_channel_id = data['channel_id']
                    rasa_conversation_id = data['conversation_id']
                    self.load_users_channels()
                    if rasa_conversation_id in [m['rasa_conversation_id'] for m in map]:
                        user_id = [m['user_id'] for m in map if m['rasa_conversation_id'] == rasa_conversation_id][0]
                        if [user['status'] for user in users_sp if user['user_id'] == user_id][0] == 'online':
                            user_id, channel_id = [(m['user_id'], m['channel_id']) for m in map if m['rasa_conversation_id'] == rasa_conversation_id][0]
                            message = json.loads(msg['data']['post']['message'])['text']
                            self.post_message_to_mattermost(message, channel_id)
                            return
                        else:
                            # need lock map ----------------------------------------------------
                            map.pop([i for i, v in enumerate(map) if v['user_id'] == user_id][0])
                    no_user_online = True
                    check = True
                    while check:
                        self.load_users_channels()
                        # logger.info('-------'+str(users_sp) + str(map))
                        for user in users_sp:
                            logger.info(str(user))
                            if user['status'] == 'online' and user['user_id'] not in [m['user_id'] for m in map]:
                                logger.info('vao if')
                                # logger.info('----user_id: ' + str(user['user_id']))
                                # logger.info('----map: ' + str(map))
                                channel_id = self._client.api.create_direct_message_channel(WORKER_ID, user['user_id'])
                                map.append({
                                    "user_id": user['user_id'],
                                    "channel_id": channel_id,
                                    "rasa_conversation_id": rasa_conversation_id,
                                    "rasa_channel_id": rasa_channel_id
                                })
                                message = json.loads(msg['data']['post']['message'])['text']
                                self.post_message_to_mattermost(message, channel_id)
                                self.load_users_channels()
                                if user['status'] == 'online':
                                    no_user_online = False
                                    check = False
                                break
                        if no_user_online:
                            self.post_message_to_rasa("Hiện tại các tư vấn viên đều bận.\nHội thoại sẽ tự động chuyển sang bot!", rasa_conversation_id, rasa_channel_id)
                            self.post_message_to_rasa("done", rasa_conversation_id, rasa_channel_id)
                            break
            return
            # else:
            #     self._client.channel_msg(
            #     msg['data']['post']['channel_id'], '\n'.join(default_reply))
            #     return
            # elif _user['username']=='help':
            #     if rasa_channel_id:
            #         _text = self.get_message(msg)
            #
            #         # print(response.text.encode('utf8'))
            #     # default_reply = [
            #     # u'Member "%s"' % self.get_message(msg),
            #     # ]
            #     # self._client.channel_msg(
            #     # msg['data']['post']['channel_id'], '\n'.join(default_reply))
            #     return

            # case 2: user is other
        else :

            user_id = msg['data']['post']['user_id']
            channel_id = msg['data']['post']['channel_id']
            # logger.info('-----' + str(map))
            # logger.info('-----' + str(user_id))
            # if user_id in [u['user_id'] for u in map] and msg['data']['post']['channel_id'] == [m['channel_id'] for m in map][0]:
            if (user_id, channel_id) in [(m['user_id'], m['channel_id']) for m in map]:
                one_map = [u for u in map if u['user_id'] == user_id][0]
                message = msg['data']['post']['message']
                if message == 'done':
                    map.pop([i for i, v in enumerate(map) if v['user_id'] == user_id][0])
                self.post_message_to_rasa(message, one_map['rasa_conversation_id'],
                                          one_map['rasa_channel_id'])

            return
        # busy = self._pool.get_busy_workers() - 1
        # default_reply = [
        #     u'Your text is "%s"' % self.get_message(msg),
        # ]
        # for key in channels_names:
        #     default_reply += ['Channel [{}]: {}'.format(key,channels_names[key])]
        #     for member_id in channels_members[key]:
        #         member = mm_members[member_id]
        #         default_reply += ['- Member [{}]: {}-{}-{}'.format(key,member['email'],member['username'],member['status'])]

        # self._client.channel_msg(
        #     msg['data']['post']['channel_id'], '\n'.join(default_reply))

        # print(default_reply)


class Message(object):
    users = {}
    channels = {}

    def __init__(self, client, body, pool):
        self._client = client
        self._body = body
        self._pool = pool

    def get_user_info(self, key, user_id=None):
        user_id = user_id or self._body['data']['post']['user_id']
        user_info = self._client.api.get_user_info(user_id)
        return user_info[key]

    def get_username(self, user_id=None):
        if user_id is None:
            return self._get_sender_name()
        return self.get_user_info('username', user_id)

    def get_user_mail(self, user_id=None):
        return self.get_user_info('email', user_id)

    def get_user_id(self, user_id=None):
        return self.get_user_info('id', user_id)

    def get_channel_name(self, channel_id=None):
        channel_id = channel_id or self.channel
        if channel_id in self.channels:
            channel_name = self.channels[channel_id]
        else:
            channel = self._client.api.channel(channel_id)
            channel_name = channel['channel']['name']
            self.channels[channel_id] = channel_name
        return channel_name

    def get_channel_display_name(self, channel_id=None):
        channel_id = channel_id or self.channel
        channel = self._client.api.channel(channel_id)
        return channel['channel']['display_name']

    def get_team_id(self):
        return self._body['data'].get('team_id', '').strip()

    def get_message(self):
        return self._body['data']['post']['message'].strip()

    def is_direct_message(self):
        return self._body['message_type'] == 'D'

    def get_busy_workers(self):
        return self._pool.get_busy_workers()

    def get_mentions(self):
        return self._body['data'].get('mentions')

    def get_file_link(self, file_id):
        return self._client.api.get_file_link(file_id)

    def upload_file(self, file):
        return self._client.api.upload_file(file, self.channel)

    def _gen_at_message(self, text):
        return '@{}: {}'.format(self.get_username(), text)

    def _gen_reply(self, text):
        if self._body['message_type'] == '?':
            return self._gen_at_message(text)
        return text

    def _get_sender_name(self):
        return self._body['data'].get('sender_name', '').strip()

    @staticmethod
    def _get_webhook_url_by_id(hook_id):
        base = '/'.join(settings.BOT_URL.split('/')[:3])
        return '%s/hooks/%s' % (base, hook_id)

    def reply_webapi(self, text, *args, **kwargs):
        self.send_webapi(self._gen_reply(text), *args, **kwargs)

    def send_webapi(self, text, attachments=None, channel_id=None, **kwargs):
        webhook_id = kwargs.get('webhook_id', settings.WEBHOOK_ID)
        if not webhook_id:
            logger.warning(
                'send_webapi with webhook_id={}. message "{}" is not sent.'
                    .format(webhook_id, text)
            )
            return
        url = self._get_webhook_url_by_id(webhook_id)
        kwargs['username'] = kwargs.get(
            'username', self.get_username(self._client.user['id']))
        kwargs['icon_url'] = kwargs.get('icon_url', BOT_ICON)
        kwargs['icon_emoji'] = kwargs.get('icon_emoji', BOT_EMOJI)
        self._client.api.in_webhook(
            url, self.get_channel_name(channel_id), text,
            attachments=attachments, ssl_verify=self._client.api.ssl_verify,
            **kwargs)

    def reply(self, text, files=None, props=None):
        self.send(self._gen_reply(text), files=files, props=props or {})

    def reply_thread(self, text, files=None, props=None):
        self.send(self._gen_reply(text), files=files, props=props or {},
                  pid=self._body['data']['post']['id'])

    def send(self, text, channel_id=None, files=None, props=None, pid=''):
        return self._client.channel_msg(
            channel_id or self.channel, text,
            files=files, pid=pid, props=props or {})

    def update(self, text, message_id, channel_id=None):
        return self._client.update_msg(
            message_id, channel_id or self.channel,
            text
        )

    def react(self, emoji_name):
        self._client.react_msg(
            self._body['data']['post']['id'], emoji_name)

    def comment(self, message):
        self.react(message)

    def docs_reply(self, docs_format='    • `{0}` {1}'):
        return

    @property
    def channel(self):
        return self._body['data']['post']['channel_id']

    @property
    def body(self):
        return self._body


class MCAPI(MattermostAPI):
    def __init__(self, url, ssl_verify, token):
        super().__init__(url, ssl_verify, token)

    def get_all_users_in_channel(self, channel_id):
        return self.get('/channels/{}/members'.format(channel_id))

    def get_user_status(self, user_id):
        return self.get(f"/users/{user_id}/status")

    def create_direct_message_channel(self, user_id1, user_id2):
        """
        :param user_id1:
        :param user_id2:
        :return: channel id for direct message between user1 and user2
        """
        tmp = self.post('/channels/direct',[user_id1, user_id2])['id']
        return tmp


class MC(MattermostClient):
    def __init__(self, url, team, email, password, ssl_verify=True, token=None, ws_origin=None):
        # super(MC, self).__init__(url, team, email, password, ssl_verify, token, ws_origin)
        self.users = {}
        self.channels = {}
        self.mentions = {}
        self.api = MCAPI(url, ssl_verify, token)
        self.user = None
        self.websocket = None
        self.email = None
        self.team = team
        self.email = email
        self.password = password
        self.ws_origin = ws_origin

        if token:
            self.user = self.api.me()
        else:
            self.login(team, email, password)

    def get_users_sp(self):
        """
        :return: [{
                    "user_id": <user_id>,
                    "status": <user_status>
                   }, ...
                  ]
        """
        team_id = self.api.get_team_by_name("rasabot")["id"]
        # logger.info("-----team_id:" + str(team_id))
        channel_sp_desk_id = self.api.get_channel_by_name("support_desk", team_id)["id"]
        # logger.info("------channel_id:"+channel_sp_desk_id)
        users = self.api.get_all_users_in_channel(channel_sp_desk_id)
        rs = []
        # logger.info('--------'+str(users))
        for user in users:
            user_id = user["user_id"]
            if user_id in [ADMIN_ID, WORKER_ID]:
                continue
            status = self.api.get_user_status(user_id)["status"]
            rs.append({"user_id": user_id, "status": status})
        return rs

    def get_channels_mm(self):
        """
        :return: [channel1_id, channel2_id, ...]
        """
        team_id = self.api.get_team_by_name("rasabot")["id"]
        channels = self.api.get_channels(team_id)
        # logger.info("-------cha" + str(channels))
        return [channel["id"] for channel in channels if channel["display_name"][:7] == "channel"]


class InterBot(object):
    def __init__(self):
        if settings.MATTERMOST_API_VERSION < 4:
            raise ValueError('This app only supports API Version 4+')
        self._client = MC(
            BOT_URL, BOT_TEAM,
            BOT_LOGIN, BOT_PASSWORD,
            settings.SSL_VERIFY, settings.BOT_TOKEN,
            settings.WS_ORIGIN)
        logger.info('connected to mattermost')
        self.load_initial_data()
        self._dispatcher = MessageDispatcher(self._client)
        # _thread.start_new_thread(self.load_users_channels, tuple())

    # def load_users_channels(self):
    #     # while True:
    #     global users_sp, channels_mm, map
    #     channels_mm = self._client.get_channels_mm()
    #     users_sp = self._client.get_users_sp()
            # logger.info('-------' + str(users_sp) + " " + str(channels_mm) + str(map))
            # time.sleep(5)

    def run(self):
        logger.info('start run in class InterBot')
        self._dispatcher.start()
        _thread.start_new_thread(self._keep_active, tuple())
        self._dispatcher.loop()

    def _keep_active(self):
        logger.info('keep active thread started')
        while True:
            # logger.info('Send ping to keep alive')
            time.sleep(5)
            self._client.ping()

    def load_initial_data(self):
        global teams
        global default_team_id
        global teams_channels_ids
        global teams_names
        global channels_names
        global channels_members
        global mm_members

        teams = self._client.api.get('/users/me/teams')
        if len(teams) == 0:
            raise AssertionError(
                'User account of this bot does not join any team yet.')
        default_team_id = teams[0]['id']
        teams_channels_ids = {}
        channels_names = {}
        channels_members = {}
        for team in teams:
            teams_channels_ids[team['id']] = []
            for channel in self._client.api.get_channels(team['id']):
                # print('------------',channel)
                teams_channels_ids[team['id']].append(channel['id'])
                channels_names[channel['id']] = channel['name']
                members = self._client.api.get('/channels/{}/members'.format(channel['id']))
                channels_members[channel['id']] = []
                for member in members:
                    channels_members[channel['id']].append(member['user_id'])
                    if member['user_id'] not in mm_members:
                        mm_user = self._client.api.get('/users/{}'.format(member['user_id']))
                        mm_user_status = self._client.api.get('/users/{}/status'.format(member['user_id']))
                        # print(mm_user)
                        mm_members[member['user_id']] = []
                        mm_members[member['user_id']] = {'email': mm_user['email'], 'username': mm_user['username'],
                                                         'status': mm_user_status['status']}


def main():
    logging.basicConfig(**{
        'format': '[%(asctime)s] %(message)s',
        'datefmt': '%m/%d/%Y %H:%M:%S',
        'level': logging.DEBUG if settings.DEBUG else logging.INFO,
        'stream': sys.stdout,
    })

    try:
        b = InterBot()
        b.run()

    except KeyboardInterrupt:
        print("Press Ctrl-C to terminate while statement")
        pass


if __name__ == "__main__":
    # execute only if run as a script
    main()
