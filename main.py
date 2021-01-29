#!/usr/bin/env python
import telegram
from telegram import replymarkup
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    PollHandler,
    Updater,
    MessageHandler,
    ConversationHandler,
    Filters,
)
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.utils.types import HandlerArg
import re

import logging
from enum import IntEnum
import math

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)

cancel_keyboard = ReplyKeyboardMarkup(
    [["Cancel"]],
    one_time_keyboard=True,
    selective=True,
    resize_keyboard=True,
)
time_in_force_keyboard = ReplyKeyboardMarkup(
    [["DAY", "GTC", "FOK", "IOC", "OPG", "CLS"], ["Cancel"]],
    one_time_keyboard=True,
    selective=True,
    resize_keyboard=True,
)


class BuyState(IntEnum):
    SYMBOL = 0
    ORDER_TYPE = 1
    TIME_IN_FORCE = 2
    CASH = 3
    LIMIT = 4
    STOP = 5


class Order:
    def __init__(
        self,
        symbol=None,
        order_type=None,
        time_in_force=None,
        cash=None,
        limit=None,
        stop=None,
    ):
        self.symbol = symbol
        self.order_type = order_type
        self.time_in_force = time_in_force
        self.cash = cash
        self.limit = limit
        self.stop = stop

    def __str__(self):
        return f"{self.symbol}, {self.order_type}, {self.time_in_force}, {self.cash}, ({self.limit}, {self.stop})"


class OrderPoll:
    def __init__(self, poll: telegram.Message = None, user: telegram.User = None):
        self.poll = poll
        self.user = user


open_order = Order()
open_poll = OrderPoll()
vote_majority = 0.5
DEBUG = True


def startBuy(update: telegram.Update, context: CallbackContext) -> BuyState:
    update.message.reply_text("Ticker symbol?", reply_markup=cancel_keyboard)
    return BuyState.SYMBOL


def parseSymbol(update: telegram.Update, context: CallbackContext) -> BuyState:
    open_order.symbol = update.message.text
    # TODO implement stop limit order
    update.message.reply_text(
        f"{open_order.symbol}. Order type?",
        reply_markup=ReplyKeyboardMarkup(
            [["Market", "Limit", "Stop"], ["Cancel"]],
            one_time_keyboard=True,
            selective=True,
            resize_keyboard=True,
        ),
    )
    return BuyState.ORDER_TYPE


def parseOrderType(update: telegram.Update, context: CallbackContext) -> BuyState:
    open_order.order_type = update.message.text
    update.message.reply_text(
        f"{open_order.order_type}. Time in force?", reply_markup=time_in_force_keyboard
    )

    return BuyState.TIME_IN_FORCE


def parseOrderTypeLimit(update: telegram.Update, context: CallbackContext) -> BuyState:
    open_order.order_type = update.message.text
    update.message.reply_text(
        f"{open_order.order_type}. Limit price?", reply_markup=cancel_keyboard
    )
    return BuyState.LIMIT


def parseLimit(update: telegram.Update, context: CallbackContext) -> BuyState:
    open_order.limit = update.message.text
    update.message.reply_text(
        f"{open_order.limit}. Time in force?", reply_markup=time_in_force_keyboard
    )
    return BuyState.TIME_IN_FORCE


def parseOrderTypeStop(update: telegram.Update, context: CallbackContext) -> BuyState:
    open_order.order_type = update.message.text
    update.message.reply_text(
        f"{open_order.order_type}. Stop price?", reply_markup=cancel_keyboard
    )
    return BuyState.STOP


def parseStop(update: telegram.Update, context: CallbackContext) -> BuyState:
    open_order.stop = update.message.text
    update.message.reply_text(
        f"{open_order.stop}. Time in force?", reply_markup=time_in_force_keyboard
    )

    return BuyState.TIME_IN_FORCE


def parseTimeInForce(update: telegram.Update, context: CallbackContext) -> BuyState:
    open_order.time_in_force = update.message.text
    update.message.reply_text(
        f"{open_order.time_in_force}. Cash?", reply_markup=cancel_keyboard
    )
    return BuyState.CASH


def parseCash(update: telegram.Update, context: CallbackContext) -> BuyState:
    global open_poll
    open_order.cash = update.message.text
    logger.info(open_order)
    open_poll.poll = update.message.reply_poll(
        f"Buy {open_order.cash} of {open_order.symbol} in a {open_order.order_type}, {open_order.time_in_force} order?",
        ["Yes", "No"],
        False,
        reply_markup=ReplyKeyboardRemove(),
    )
    open_poll.user = update.message.from_user
    return ConversationHandler.END


def onPollUpdate(update: HandlerArg, context: CallbackContext):
    global open_poll
    yes_count = -1
    if (open_poll.poll is not None) and update.poll == open_poll.poll.poll:
        for opt in update.poll.options:
            if opt.text == "Yes":
                yes_count = opt.voter_count
    if yes_count == -1:
        return

    needed_count = math.ceil(open_poll.poll.chat.get_members_count() * vote_majority)
    if DEBUG:
        needed_count = 1

    if yes_count >= needed_count:
        open_poll.poll.reply_text("Purchased.")
        open_poll = OrderPoll()


def cancelBuy(update: telegram.Update, context: CallbackContext) -> int:
    update.message.reply_text("Canceled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def cancelPoll(update: telegram.Update, context: CallbackContext):
    global open_poll
    reply = update.message.reply_to_message
    if (reply is not None) and (reply.poll is not None) and (reply == open_poll.poll):
        if update.message.from_user == open_poll.user:
            update.message.reply_text("Cancelling poll.")
            open_poll = OrderPoll()
        else:
            update.message.reply_text(
                f"Only @{open_poll.user.username} can cancel this poll."
            )


def testHandler(update: telegram.Update, context: CallbackContext):
    logger.info(update.effective_chat.get_members_count())


def main():
    with open("token.txt", "r") as token_file:
        token = token_file.read().rstrip("\n")
        updater = Updater(token, use_context=True)

    dp = updater.dispatcher

    buy_conversation = ConversationHandler(
        entry_points=[CommandHandler("buy", startBuy)],
        states={
            BuyState.SYMBOL: [
                MessageHandler(Filters.regex("^(Cancel)$"), cancelBuy),
                MessageHandler(Filters.regex("^\$[A-Z]*$"), parseSymbol),
            ],
            BuyState.ORDER_TYPE: [
                MessageHandler(Filters.regex("^(Cancel)$"), cancelBuy),
                MessageHandler(Filters.regex("^(Market|Stop Limit)$"), parseOrderType),
                MessageHandler(Filters.regex("^Limit$"), parseOrderTypeLimit),
                MessageHandler(Filters.regex("^Stop$"), parseOrderTypeStop),
            ],
            BuyState.LIMIT: [
                MessageHandler(Filters.regex("^(Cancel)$"), cancelBuy),
                MessageHandler(Filters.regex("^\$?[0-9]*(\.[0-9]*)?$"), parseLimit),
            ],
            BuyState.STOP: [
                MessageHandler(Filters.regex("^(Cancel)$"), cancelBuy),
                MessageHandler(Filters.regex("^\$?[0-9]*(\.[0-9]*)?$"), parseStop),
            ],
            BuyState.TIME_IN_FORCE: [
                MessageHandler(Filters.regex("^(Cancel)$"), cancelBuy),
                MessageHandler(
                    Filters.regex("^(DAY|GTC|FOK|IOC|OPG|CLS)$"), parseTimeInForce
                ),
            ],
            BuyState.CASH: [
                MessageHandler(Filters.regex("^(Cancel)$"), cancelBuy),
                MessageHandler(Filters.regex("^\$?[0-9]*(\.[0-9]*)?$"), parseCash),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancelBuy)],
    )
    dp.add_handler(buy_conversation)

    dp.add_handler(PollHandler(onPollUpdate))
    dp.add_handler(CommandHandler("cancel", cancelPoll))
    dp.add_handler(CommandHandler("test", testHandler))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
