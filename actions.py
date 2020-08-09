# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/core/actions/#custom-actions/


# This is a simple example for a custom action which utters "Hello World!"
from mmpy_bot.mattermost import MattermostClient
import json
from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet, ReminderScheduled, ConversationPaused, ConversationResumed, SessionStarted, \
    ActionExecuted, FollowupAction, UserUttered
from rasa_sdk.executor import CollectingDispatcher
import datetime
import urllib.request as rq
import ssl
import feedparser
import xml.etree.ElementTree as ET
from rasa.utils.io import read_config_file


def get_carousel_template():
    """this function get template carousel for facebook
    Returns:
        Dict: return dict carousel template
    """
    return {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "generic",
                "elements": [
                ]
            }
        }
    }


URL_BUY_RSS = 'https://batdongsan.com.vn/Modules/RSS/RssDetail.aspx?catid=324&typeid=1'
URL_RENT_RSS = 'https://batdongsan.com.vn/Modules/RSS/RssDetail.aspx?catid=326&typeid=1'
file_name = './data/tygia.txt'


def get_name_fb(tracker: Tracker):
    """this function get facebook user's name
    Args:
        tracker (Tracker): tracker

    Returns:
        str: facebook user's name 
    """
    credentials_file = './credentials.yml'
    all_credentials = read_config_file(credentials_file)
    fb_access_token = all_credentials['facebook']['page-access-token']
    most_recent_state = tracker.current_state()

    sender_id = most_recent_state['sender_id']

    from fbmessenger import MessengerClient as MC
    mc = MC(fb_access_token)
    name = None
    try:
        name = mc.get_user_data(sender_id, 'name')['name']
    except:
        print('ko lay dc ten facebook')
    return name


def is_bot_agent(tracker: Tracker):
    return True if tracker.get_slot("language") != "human" else False


class ActionQuangCao(Action):
    def name(self):
        return "action_quang_cao"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if not is_bot_agent(tracker):
            return [FollowupAction("action_notify")]
        type_ad = tracker.get_slot("type_ad")
        if not type_ad:
            dispatcher.utter_template(template="utter_quang_cao_all", tracker=tracker)
        elif type_ad == "tin":
            dispatcher.utter_template(template="utter_quang_cao_tin", tracker=tracker)
            return [SlotSet("type_ad", None)]
        elif type_ad == "banner":
            dispatcher.utter_template(template="utter_quang_cao_banner", tracker=tracker)
            return [SlotSet("type_ad", None)]
        else:
            dispatcher.utter_template(template="utter_default", tracker=tracker)

        return []


class ActionBaoGia(Action):
    def name(self):
        return "action_bao_gia"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if not is_bot_agent(tracker):
            return [FollowupAction("action_notify")]
        type_ad = tracker.get_slot("type_ad")
        events = []
        if not type_ad:
            dispatcher.utter_template(template="utter_bao_gia_all", tracker=tracker)
        elif type_ad == "tin":
            events.append(FollowupAction("action_bao_gia_tin_dang"))
            events.append(SlotSet("type_ad", None))
            return events
        elif type_ad == "banner":
            # dispatcher.utter_template(template="utter_bao_gia_banner", tracker=tracker)
            events.append(FollowupAction("action_bao_gia_banner"))
            events.append(SlotSet("type_ad", None))
            return events
        else:
            dispatcher.utter_template(template="utter_default", tracker=tracker)
        return []


class ActionSetReminder(Action):
    """Schedules a reminder, supplied with the last message's entities."""

    def name(self) -> Text:
        return "action_set_reminder"

    async def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        if not is_bot_agent(tracker):
            return [FollowupAction("action_notify")]
        dispatcher.utter_message("I will remind you in 5 seconds.")

        date = datetime.datetime.now() + datetime.timedelta(seconds=5)
        entities = tracker.latest_message.get("entities")

        reminder = ReminderScheduled(
            "EXTERNAL_reminder",
            trigger_date_time=date,
            entities=entities,
            name="my_reminder",
            kill_on_user_message=False,
        )

        return [reminder]


class ActionReactToReminder(Action):

    def name(self) -> Text:
        return "action_react_to_reminder"

    async def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        if not is_bot_agent(tracker):
            return [FollowupAction("action_notify")]
        name = next(tracker.get_latest_entity_values("name"), "someone")
        dispatcher.utter_message(f"Remember to call {name}!")

        return []


class ActionTellID(Action):
    """Informs the user about the conversation ID."""

    def name(self) -> Text:
        return "action_tell_id"

    async def run(
            self, dispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        if not is_bot_agent(tracker):
            return [FollowupAction("action_notify")]
        conversation_id = tracker.sender_id

        dispatcher.utter_message(
            f"The ID of this conversation is: " f"{conversation_id}."
        )

        dispatcher.utter_message(
            f"Trigger an intent with "
            f'curl -H "Content-Type: application/json" '
            f'-X POST -d \'{{"name": "EXTERNAL_dry_plant", '
            f'"entities": {{"plant": "Orchid"}}}}\' '
            f"http://localhost:5005/conversations/{conversation_id}/"
            f"trigger_intent"
        )

        return []


class ActionWarnDry(Action):
    """Informs the user that a plant needs water."""

    def name(self) -> Text:
        return "action_warn_dry"

    async def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        if not is_bot_agent(tracker):
            return [FollowupAction("action_notify")]
        plant = next(tracker.get_latest_entity_values("plant"), "someone")
        dispatcher.utter_message(f"Your {plant} needs some water!")

        return []


class ActionPause(Action):
    """Informs the user that a plant needs water."""

    def name(self) -> Text:
        return "action_pause"

    async def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        if not is_bot_agent(tracker):
            return [FollowupAction("action_notify")]
        return [ConversationPaused()]


class ActionResume(Action):
    """Informs the user that a plant needs water."""

    def name(self) -> Text:
        return "action_resume"

    async def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        if not is_bot_agent(tracker):
            return [FollowupAction("action_notify")]
        return [ConversationResumed()]


class ActionGetLottery(Action):
    def name(self):
        return "action_get_lottery"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        if not is_bot_agent(tracker):
            return [FollowupAction("action_notify")]
        url = 'https://xskt.com.vn/rss-feed/mien-bac-xsmb.rss'
        date = tracker.get_slot("ngay")
        # month = tracker.get_slot("month")
        # Tien hanh lay thong tin tu URL
        print('-' * 10, date)
        feed_cnt = feedparser.parse(url)
        # print(feed_cnt)
        # Lay ket qua so xo moi nhat
        first_node = feed_cnt['entries']
        # print(first_node)
        # Lay thong tin ve ngay va chi tiet cac giai
        return_msg = 'không tìm thấy ngày cần tìm'
        if not date:
            response = {
                "text": "Bạn muốn tra cứu ngày nào?",
                "quick_replies": [
                ]
            }
            for i in range(len(first_node)):
                ngay = str(first_node[i]['title']).split('/')[0].split(' ')[-1]
                response["quick_replies"].append({
                    "content_type": "text",
                    "title": "ngày " + ngay,
                    "payload": "/ask_lottery{\"ngay\":\"" + ngay + "\"}"
                })
            # return_msg = first_node[0]['title'] + "\n" + first_node[0]['description']
            print(response)
            dispatcher.utter_message(json_message=response)
            return []
        for i in range(len(first_node)):
            ngay = str(first_node[i]['title']).split('/')[0].split(' ')[-1]
            print(ngay)
            if str(ngay) == str(date):
                return_msg = first_node[i]['title'] + "\n" + first_node[i]['description']
        # Tra ve cho nguoi dung
        dispatcher.utter_message(text=return_msg)
        return [SlotSet("ngay", None)]


class ActionGetExchangeRate(Action):
    def name(self):
        return "action_get_exchange_rate"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        if not is_bot_agent(tracker):
            return [FollowupAction("action_notify")]
        tygia = tracker.get_slot("ty_gia")
        print('-' * 10, tygia)
        url = 'https://portal.vietcombank.com.vn/Usercontrols/TVPortal.TyGia/pXML.aspx?b=1'

        data = rq.urlopen(url, context=ssl._create_unverified_context()).read()
        root = ET.fromstring(data)
        return_msg = "Bạn muốn xem tỷ giá nào?"
        file = open(file_name, 'r')
        type_tygia = file.read()
        if tygia == None:
            response = {
                "text": "Bạn muốn tra cứu loại nào?",
                "quick_replies": [
                ]
            }

            i = 0
            for one in type_tygia.split('\n'):
                response["quick_replies"].append({
                    "content_type": "text",
                    "title": one,
                    "payload": "/ask_exchange_rate{\"ty_gia\":\"" + one + "\"}"
                })
                i += 1
                if i > 9:
                    break
            print(response)
            dispatcher.utter_message(json_message=response)
            return []
        return_msg = "Mình chưa được cung cấp thông tin loại tỷ giá này"
        for child in root:
            try:
                code = child.attrib['CurrencyCode']
            except:
                continue
            if code == tygia:
                buy = child.attrib['Buy']
                transfer = child.attrib['Transfer']
                sell = child.attrib['Sell']
                return_msg = "Tỷ giá đồng " + code + "\nMua: " + buy + "\nchuyển đổi: " + transfer + "\nsell: " + sell
        # Lay thong tin ve ngay va chi tiet cac giai
        # Tra ve cho nguoi dung
        dispatcher.utter_message(text=return_msg)
        return [SlotSet("ty_gia", None)]


class ActionBuy(Action):
    def name(self):
        return "action_buy"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        if not is_bot_agent(tracker):
            return [FollowupAction("action_notify")]
        data = feedparser.parse(URL_BUY_RSS)
        root = data['entries']

        response = get_carousel_template()
        i = 0
        for one in root:
            xml = one["summary_detail"]["value"].split('\n')[0]
            url_img = [one for one in xml.split('\"') if one[:4] == 'http']
            url_img = url_img[0] if len(url_img) > 0 else "https://batdongsan.com.vn/Images/nophoto.jpg"
            print(url_img)
            response["attachment"]["payload"]["elements"].append({
                "title": one["title"],
                "image_url": url_img,
                "subtitle": None,
                "default_action": {
                    "type": "web_url",
                    "url": one["link"],
                    "webview_height_ratio": "tall",
                },
                "buttons": None
            })
            i += 1
            if i > 8:
                break
        dispatcher.utter_message(template="utter_mua")
        dispatcher.utter_message(json_message=response)
        return []


class ActionRent(Action):
    def name(self):
        return "action_rent"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        if not is_bot_agent(tracker):
            return [FollowupAction("action_notify")]
        response = get_carousel_template()
        data = feedparser.parse(URL_RENT_RSS)
        root = data['entries']
        i = 0
        for one in root:
            xml = one["summary_detail"]["value"].split('\n')[0]
            url_img = [one for one in xml.split('\"') if one[:4] == 'http']
            url_img = url_img[0] if len(url_img) > 0 else "https://batdongsan.com.vn/Images/nophoto.jpg"
            print(url_img)
            response["attachment"]["payload"]["elements"].append({
                "title": one["title"],
                "image_url": url_img,
                "subtitle": None,
                "default_action": {
                    "type": "web_url",
                    "url": one["link"],
                    "webview_height_ratio": "tall",
                },
                "buttons": None
            })
            i += 1
            if i > 8:
                break

        dispatcher.utter_message(template="utter_thue")
        dispatcher.utter_message(json_message=response)
        return []


class ActionSessionStart(Action):
    def name(self):
        return "action_session_start"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        events = [SessionStarted()]
        events.append(SlotSet("language", "vi"))
        # events.append(UserUttered("/show_menu", {"intent": {"name": "show_menu", "confidence": 1.0}, "entities": {}}))
        # events.append(SlotSet("type_ad", "tin"))
        # events.append(SessionStarted())
        # events.append(FollowupAction("action_show_menu"))
        dispatcher.utter_message(template="utter_set_language")
        # events.append(ActionExecuted("action_listen"))
        # events.append(ActionExecuted("action_listen"))
        return events


class ActionSetLanguage(Action):
    def name(self):
        return "action_set_language"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        lan = tracker.get_slot("language")
        if lan == "en":
            dispatcher.utter_message("Sorry, English is not supported yet!\nVietnamese is chosen!")
        return [SlotSet("language", "vi"), FollowupAction("action_greeting")]


class ActionGreeting(Action):
    def name(self):
        return "action_greeting"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        if not is_bot_agent(tracker):
            return [FollowupAction("action_notify")]
        name = get_name_fb(tracker)
        name = name if name else "bạn"
        dispatcher.utter_message("Chào " + name + "\nMình có thể giúp"
                                                  " gì cho bạn😄👇")
        return [FollowupAction("action_show_menu")]


class ActionCarousel(Action):
    def name(self):
        return "action_carousel"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        if not is_bot_agent(tracker):
            return [FollowupAction("action_notify")]
        payload = {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": [
                        {
                            "title": "Welcome!",
                            "image_url": "https://scontent.fhan5-7.fna.fbcdn.net/v/t1.0-1/p100x100/107600621_104757031310633_4996001997334915551_o.png?_nc_cat=100&_nc_sid=dbb9e7&_nc_ohc=sXoc64VsqdcAX_6SrF8&_nc_ht=scontent.fhan5-7.fna&oh=0507c0c2ef716c90dbd2dd12f21542b2&oe=5F3908FA",
                            "subtitle": "We have the right hat for everyone.",
                            "default_action": {
                                "type": "web_url",
                                "url": "https://dl-media.viber.com/1/sha re/2/long/vibes/icon/image/0x0/90a5/9ea710b2fa914b8409e3b9455924b9580d8ecb6bbb5daedb011ce9d72cd290a5.jpg",
                                "webview_height_ratio": "tall",
                            },
                            "buttons": [
                                {
                                    "type": "web_url",
                                    "url": "https://petersfancybrownhats.com",
                                    "title": "View Website"
                                }, {
                                    "type": "postback",
                                    "title": "Start Chatting",
                                    "payload": "DEVELOPER_DEFINED_PAYLOAD"
                                }
                            ]
                        },
                        {
                            "title": "Welcome!",
                            "image_url": "https://scontent.fhan5-7.fna.fbcdn.net/v/t1.0-1/p100x100/107600621_104757031310633_4996001997334915551_o.png?_nc_cat=100&_nc_sid=dbb9e7&_nc_ohc=sXoc64VsqdcAX_6SrF8&_nc_ht=scontent.fhan5-7.fna&oh=0507c0c2ef716c90dbd2dd12f21542b2&oe=5F3908FA",
                            "subtitle": "We have the right hat for everyone.",
                            "default_action": {
                                "type": "web_url",
                                "url": "https://dl-media.viber.com/1/sha re/2/long/vibes/icon/image/0x0/90a5/9ea710b2fa914b8409e3b9455924b9580d8ecb6bbb5daedb011ce9d72cd290a5.jpg",
                                "webview_height_ratio": "tall",
                            },
                            "buttons": [
                                {
                                    "type": "web_url",
                                    "url": "https://petersfancybrownhats.com",
                                    "title": "View Website"
                                }, {
                                    "type": "postback",
                                    "title": "Start Chatting",
                                    "payload": "DEVELOPER_DEFINED_PAYLOAD"
                                }
                            ]
                        }
                    ]
                }
            }
        }
        dispatcher.utter_message(json_message=payload)
        return []


class ActionQuickReply(Action):
    def name(self):
        return "action_quick_reply"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        if not is_bot_agent(tracker):
            return [FollowupAction("action_notify")]
        response = {
            "text": "Pick a color:",
            "quick_replies": [
                {
                    "content_type": "text",
                    "title": "Red",
                    "payload": "<POSTBACK_PAYLOAD>",
                    "image_url": "http://example.com/img/red.png"
                }, {
                    "content_type": "text",
                    "title": "Green",
                    "payload": "<POSTBACK_PAYLOAD>",
                    "image_url": "http://example.com/img/green.png"
                }
            ]
        }

        dispatcher.utter_message(json_message=response)
        return []


class ActionShowMenu(Action):
    def name(self):
        return "action_show_menu"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        if not is_bot_agent(tracker):
            return [FollowupAction("action_notify")]
        carousels = {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": [
                        {
                            "title": "Quảng Cáo",
                            "image_url": "https://dsim.in/blog/wp-content/uploads/2018/09/AdvertiseUs.jpg",
                            "subtitle": "Quảng cáo",
                            "default_action": {
                                "type": "web_url",
                                "url": "https://batdongsan.com.vn/bao-gia-quang-cao",
                                "webview_height_ratio": "tall",
                            },
                            "buttons": [
                                {
                                    "type": "postback",
                                    "title": "Quảng cáo tin đăng",
                                    "payload": "/quang_cao{\"type_ad\":\"tin\"}"
                                }, {
                                    "type": "postback",
                                    "title": "Quảng cáo banner",
                                    "payload": "/quang_cao{\"type_ad\":\"banner\"}"
                                }
                            ]
                        },
                        {
                            "title": "Mua & Thuê!",
                            "image_url": "https://file4.batdongsan.com.vn/resize/745x510/2020/02/21/20200221091638-5911_wm.jpg",
                            "subtitle": "Mua & Thuê",
                            "default_action": {
                                "type": "web_url",
                                "url": "https://batdongsan.com.vn/can-mua-can-thue",
                                "webview_height_ratio": "tall",
                            },
                            "buttons": [
                                {
                                    "type": "postback",
                                    "title": "Mua",
                                    "payload": "/mua"
                                }, {
                                    "type": "postback",
                                    "title": "Thuê",
                                    "payload": "/thue"
                                }
                            ]
                        },
                        {
                            "title": "Bán & Cho thuê",
                            "image_url": "https://file4.batdongsan.com.vn/resize/745x510/2020/02/21/20200221091638-5911_wm.jpg",
                            "subtitle": "Bán & Cho thuê",
                            "default_action": {
                                "type": "web_url",
                                "url": "https://batdongsan.com.vn/dang-tin-rao-vat-ban-nha-dat",
                                "webview_height_ratio": "tall",
                            },
                            "buttons": [
                                {
                                    "type": "postback",
                                    "title": "Bán",
                                    "payload": "/ban"
                                }, {
                                    "type": "postback",
                                    "title": "Cho Thuê",
                                    "payload": "/cho_thue"
                                }
                            ]
                        },
                        {
                            "title": "Tra cứu ngoài",
                            "image_url": "https://img.republicworld.com/republic-prod/stories/promolarge/xxhdpi/6ao0rqs3v5miwzwl_1594839394.jpeg?tr=w-812,h-464",
                            "subtitle": "Tra cứu xổ số, tỷ giá ngoại tệ",
                            "buttons": [
                                {
                                    "type": "postback",
                                    "title": "Tra cứu xổ số",
                                    "payload": "/ask_lottery"
                                }, {
                                    "type": "postback",
                                    "title": "Tra cứu tỷ giá",
                                    "payload": "/ask_exchange_rate"
                                }
                            ]
                        },
                        {
                            "title": "Nhận thông báo",
                            "image_url": "https://miro.medium.com/max/712/1*c3cQvYJrVezv_Az0CoDcbA.jpeg",
                            "subtitle": "Nhận thông báo qua mail, số điện thoại",
                            "buttons": [
                                {
                                    "type": "postback",
                                    "title": "Nhập thông tin",
                                    "payload": "/user"
                                }
                            ]
                        }

                    ]
                }
            }
        }
        dispatcher.utter_message(json_message=carousels)
        return []


class ActionBaoGiaBanner(Action):
    def name(self):
        return "action_bao_gia_banner"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        if not is_bot_agent(tracker):
            return [FollowupAction("action_notify")]
        dispatcher.utter_message(template="utter_bao_gia_banner")
        dispatcher.utter_image_url('https://i.ibb.co/xhxh2q3/Screenshot-from-2020-07-21-10-32-13.png')
        dispatcher.utter_image_url('https://i.ibb.co/4mLNFBx/Screenshot-from-2020-07-21-10-32-22.png')
        dispatcher.utter_image_url('https://i.ibb.co/hFyjfRh/Screenshot-from-2020-07-21-10-32-29.png')
        return []


class ActionBaoGiaTinDang(Action):
    def name(self):
        return "action_bao_gia_tin_dang"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        if not is_bot_agent(tracker):
            return [FollowupAction("action_notify")]
        dispatcher.utter_message(template="utter_bao_gia_tin")
        dispatcher.utter_image_url('https://i.ibb.co/DzCcGWK/Screenshot-from-2020-07-22-11-37-38.png')
        dispatcher.utter_image_url('https://i.ibb.co/4RhrG6s/Screenshot-from-2020-07-22-11-38-06.png')
        return []


""" NOTIFY HUMAN AGENT
"""

MATTERMOST_API_VERSION = 4
BOT_URL = 'http://192.168.88.187:8065/api/v4'
BOT_LOGIN = 'bot@nms.com.vn'
BOT_PASSWORD = 'Password@bot1'
BOT_TOKEN = None
BOT_TEAM = 'rasabot'
BOT_CHANNEL = 'bot'
SSL_VERIFY = True
WS_ORIGIN = None
conversation_ids_stores = {}


class ActionNotify(Action):
    def name(self):
        return 'action_notify'

    def run(self, dispatcher, tracker, domain):
        global conversation_ids_stores
        rasa_channel_id = tracker.get_latest_input_channel()
        rasa_conversation_id = tracker.sender_id
        if rasa_conversation_id not in conversation_ids_stores:
            conversation_ids_stores[rasa_conversation_id] = rasa_channel_id
        else:
            for item in conversation_ids_stores:
                # print('channel is {} and id is {}'.format(conversation_ids_stores[item],item))
                pass
        m = MattermostClient(BOT_URL, BOT_TEAM, BOT_LOGIN, BOT_PASSWORD)
        team_id = m.api.get_team_by_name(BOT_TEAM)
        team_id = team_id['id']
        channel_id = m.api.get_channel_by_name(BOT_CHANNEL, team_id)
        channel_id = channel_id['id']
        me = m.api.me()
        msg = {"conversation_id": rasa_conversation_id, "channel_id": rasa_channel_id,
               "text": tracker.latest_message["text"]}
        m.api.create_post(me["id"], channel_id, "{}".format(json.dumps(msg)))
        # dispatcher.utter_message(template="utter_lien_he_bds")
        return [SlotSet("language", "human")]


class ActionHumanReply(Action):
    def name(self):
        return 'action_human_reply'

    def run(self, dispatcher, tracker, domain):
        if is_bot_agent(tracker):
            return []
        text = next(tracker.get_latest_entity_values("text"), ".")
        dispatcher.utter_message("{}".format(text))
        return []


class ActionActiveBotAgent(Action):
    def name(self):
        return "action_active_bot_agent"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        return [SlotSet("language", "vi")]


from sqlalchemy import create_engine
from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

db_string = 'postgres://nms_user:nms_password@localhost/rasa'
db = create_engine(db_string)
base = declarative_base()


class User(base):
    __tablename__ = 'user'
    user_id = Column(String, primary_key=True)
    name = Column(String)
    email = Column(String)
    phone_number = Column(String)

base.metadata.create_all(db)

from rasa_sdk.forms import FormAction

REQUESTED_SLOT = 'requested_slot'


class ActionForm(FormAction):
    def name(self):
        return "user_form"

    @staticmethod
    def required_slots(tracker: Tracker) -> List[Text]:
        """A list of required slots that the form has to fill"""

        return ["user_name", "user_email", "user_phone"]

    def validate_email(self, value: Text, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        return {"user_email": value}

    def validate_user_name(self, value: Text, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        return {"user_name": value}

    def validate_phone(self, value: Text, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        return {"user_phone": value}

    def slot_mappings(self):
        return {
            "user_name": self.from_entity(entity="user_name", intent="intent_user_name"),
            "user_email": self.from_entity(entity="user_email", intent="intent_user_email"),
            "user_phone": self.from_entity(entity="user_phone", intent="intent_user_phone")
        }

    def request_next_slot(self, dispatcher: "CollectingDispatcher", tracker: "Tracker", domain: Dict[Text, Any]):
        for slot in self.required_slots(tracker):
            if self._should_request_slot(tracker, slot):
                dispatcher.utter_message(template="utter_ask_{}".format(slot))
                return [SlotSet(REQUESTED_SLOT, slot)]
        return None

    def submit(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        base.metadata.create_all(db)
        Session = sessionmaker(db)
        session = Session()
        most_recent_state = tracker.current_state()

        user_id = most_recent_state['sender_id']
        user_name = tracker.get_slot("user_name")
        user_phone = tracker.get_slot("user_phone")
        user_email = tracker.get_slot("user_email")
        user = User(user_id=user_id, name=user_name, phone_number=user_phone, email=user_email)
        try:
            session.add(user)
            session.commit()
        except:
            session.rollback()
            user = session.query(User).filter(User.user_id == user_id)[0]
            user.name = user_name
            user.phone_number = user_phone
            user.email = user_email
            session.commit()
        dispatcher.utter_message("Bạn đã cung cấp thông tin sau:\nTên: {}\nemail: {}\nSĐT: {}.\nThông tin mới nhất sẽ được gửi vào mail hoặc sđt cho bạn!".format(user_name, user_email, user_phone))
        return [SlotSet("user_name", None), SlotSet("user_phone", None), SlotSet("user_email", None)]
