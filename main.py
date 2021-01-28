#!/usr/bin/env python
import telegram
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    PollHandler,
    PollAnswerHandler,
    Updater,
    MessageHandler,
    ConversationHandler,
    Filters,
)
from telegram.utils.types import HandlerArg
import re
import yfinance as yf

# gme = yf.Ticker("GME")
import logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


valid_ticker = re.compile("^\$[A-Z]*$")
valid_amount = re.compile("^[0-9]*$")


TICKER, AMOUNT, POLL, ORDER = range(4)

open_poll: telegram.message.Message = None


def onBuy(update: telegram.Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "What would you like to buy? Please send a ticker symbol (ex: $APPL, $TSLA, $GME)"
    )

    return TICKER


def onTicker(update: telegram.Update, context: CallbackContext) -> int:
    text = update.message.text
    if valid_ticker.match(text) is not None:
        for e in update.message.entities:
            if e.type == "cashtag":
                start = e.offset
                end = start + e.length
                ticker = update.message.text[start:end]
                update.message.reply_text(
                    f"You requested {ticker}. How much do you want to buy?"
                )
                return AMOUNT
    update.message.reply_text("Please send a valid ticker symbol")
    return TICKER


def onAmount(update: telegram.Update, context: CallbackContext) -> int:
    global open_poll
    text = update.message.text
    if valid_amount.match(text) is not None:
        update.message.reply_text(f"You want to buy {update.message.text}")
        poll = update.message.reply_poll(f"Vote?", ["Yes", "No"], False)
        open_poll = poll
        return ConversationHandler.END
    update.message.reply_text("Please send a valid amount")
    return AMOUNT


def onPoll(update: HandlerArg, context: CallbackContext):
    global open_poll
    if update.poll == None or open_poll == None:
        return
    yes_count = -1
    if update.poll.id == open_poll.poll.id:
        for opt in update.poll.options:
            if opt.text == "Yes":
                yes_count = opt.voter_count
                logger.info(yes_count)
    if yes_count >= 1:
        open_poll.reply_text("Purchased")
        open_poll = None
        return ConversationHandler.END


def onHoldings(update: HandlerArg, context: CallbackContext):    
    update.message.reply_text(
        "You have 69 in $DEEZNUTS. Current value is (INSERT YAHOO STUFF)"
    )


def cancel(update: telegram.Update, context: CallbackContext) -> int:
    update.message.reply_text("CANCELED")
    return ConversationHandler.END


def main():
    with open("token.txt", "r") as token_file:
        token = token_file.read().rstrip("\n")
        updater = Updater(token, use_context=True)

    updater.dispatcher.add_handler(CommandHandler("holdings", onHoldings))
    updater.dispatcher.add_handler(PollHandler(onPoll))
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("buy", onBuy)],
        states={
            TICKER: [
                MessageHandler(Filters.text, onTicker),
            ],
            AMOUNT: [
                MessageHandler(Filters.text, onAmount),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    updater.dispatcher.add_handler(conv_handler)
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
