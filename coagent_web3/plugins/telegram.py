#!/usr/bin/env python
# pylint: disable=unused-argument
# This program is dedicated to the public domain under the CC0 license.

"""
Simple Bot to reply to Telegram messages.

First, a few handler functions are defined. Then, those functions are passed to
the Application and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.

Usage:
Basic Echobot example, repeats messages.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import logging
import os

from coagent.core import AgentSpec
from coagent.agents import ChatMessage
from coagent.core.types import Runtime
from telegram import ForceReply, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from coagent_web3 import Service

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# Define a few command handlers. These usually take the two arguments update and
# context.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help!")


class Plugin(Service):
    def __init__(self, runtime: Runtime, agent: AgentSpec) -> None:
        self.agent = agent

        # Create the Application and pass it your bot's token.
        token = os.getenv("TELEGRAM_TOKEN")
        self.app = Application.builder().token(token).build()

    async def start(self) -> None:
        """Start the bot."""

        # on different commands - answer in Telegram
        self.app.add_handler(CommandHandler("start", start))
        self.app.add_handler(CommandHandler("help", help_command))

        # on non command i.e message - echo the message on Telegram
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.chat))

        # Run the bot until the user presses Ctrl-C
        await self.app.initialize()
        await self.app.updater.start_polling()
        await self.app.start()

    async def stop(self) -> None:
        """Stop the bot."""
        await self.app.stop()
        await self.app.updater.stop()
        await self.app.shutdown()

    async def chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Chat with the agent."""
        result = await self.agent.run(
            ChatMessage(role="user", content=update.message.text).encode(),
            session_id=str(update.message.chat.id),
        )
        msg = ChatMessage.decode(result)
        await update.message.reply_text(msg.content)
        """
        await update.effective_chat.send_message(
            msg.content,
            parse_mode=ParseMode.MARKDOWN_V2,
            # parse_mode=ParseMode.HTML,
        )
        """
