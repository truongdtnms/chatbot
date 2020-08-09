import json
import logging
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional, Text

from rasa.core.channels.channel import InputChannel, OutputChannel, UserMessage
from rasa.utils.common import raise_warning
from sanic import Blueprint, response
from sanic.request import Request
from sanic.response import HTTPResponse
from viberbot import Api
from viberbot.api.bot_configuration import BotConfiguration
from viberbot.api.messages import TextMessage, PictureMessage
from viberbot.api.viber_requests import ViberMessageRequest

logger = logging.getLogger(__name__)


class ViberBot(OutputChannel):

    @classmethod
    def name(cls) -> Text:
        return "viber"

    def __init__(self, name : Text, avatar : Text, token : Text, webhook : Text) -> None:
        bot_configuration = BotConfiguration(auth_token=token, name=name, avatar=avatar)
        self.viber = Api(bot_configuration)
        super().__init__()


    async def send_text_message(
        self, recipient_id: Text, text: Text, **kwargs: Any
    ) -> None:
        print('*'*10, 'send text message')
        for message_part in text.strip().split("\n\n"):
            self.viber.send_messages(recipient_id, messages=[TextMessage(text=message_part)])

    async def send_image_url(
        self, recipient_id: Text, image: Text, **kwargs: Any
    ) -> None:
        await self.viber.send_messages(recipient_id, messages=[PictureMessage(media=image)])

class ViberInput(InputChannel):
    """Slack input channel implementation. Based on the HTTPInputChannel."""

    @classmethod
    def name(cls) -> Text:
        return "viber"

    @classmethod
    def from_credentials(cls, credentials: Optional[Dict[Text, Any]]) -> InputChannel:
        if not credentials:
            cls.raise_missing_credentials_exception()

        # pytype: disable=attribute-error
        return cls(
            credentials.get("name"),
            credentials.get("avatar"),
            credentials.get("auth_token"),
            credentials.get("webhook"),
        )
        # pytype: enable=attribute-error

    def __init__(
        self,
        name: Text,
        avatar: Optional[Text] = None,
        auth_token: Optional[Text] = None,
        webhook: Optional[Text] = None,
    ) -> None:

        self.name_ = name
        self.avatar = avatar
        self.auth_token = auth_token
        self.webhook = webhook
        self.viber = Api(BotConfiguration(self.auth_token, self.name, self.avatar))


    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[Any]]
    ) -> Blueprint:
        viber_webhook = Blueprint("viber_webhook", __name__)

        @viber_webhook.route("/", methods=["GET"])
        async def health(_: Request) -> HTTPResponse:
            return response.json({"status": "ok"})

        @viber_webhook.route("/webhook", methods=["GET", "POST"])
        async def webhook(request: Request) -> HTTPResponse:
            logger.debug("received request. post data: {0}".format(request.body))
            # every viber message is signed, you can verify the signature using this method
            if not self.viber.verify_signature(request.body, request.headers.get('X-Viber-Content-Signature')):
                print('-'*10, 'fail')
                return response.text("not validated")

            # this library supplies a simple way to receive a request object
            viber_request = self.viber.parse_request(request.body)
            print('-'*10, viber_request)
            user_message = UserMessage(
                text=viber_request.message.text,
                output_channel=ViberBot(self.name_, self.avatar, self.auth_token, self.webhook),
                sender_id=viber_request.sender.id,
                input_channel=self.name()
                # message_id=viber_request.message.id
            )
            await on_new_message(user_message)
            return response.text("success")

        return viber_webhook

