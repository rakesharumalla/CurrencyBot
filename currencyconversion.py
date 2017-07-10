import os
import time
import math
import logging
import requests

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


""" --- Helper Functions --- """

def get_slots(intent_request):
    return intent_request['currentIntent']['slots']


def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message
        }
    }


def close(session_attributes, fulfillment_state, message):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': message
        }
    }

    return response


def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }


def get_exchange_rate(base_currency, target_currency):
    if base_currency == target_currency:
        return 1

    api_uri = "https://api.fixer.io/latest?base={}&symbols={}".format(base_currency, target_currency)
    api_response = requests.get(api_uri)

    if api_response.status_code == 200:
        return api_response.json()["rates"][target_currency]


def build_validation_result(is_valid, violated_slot, message_content):
    if message_content is None:
        return {
            "isValid": is_valid,
            "violatedSlot": violated_slot,
        }

    return {
        'isValid': is_valid,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }

def validate_currency_fields(src_currency_type,tgt_currency_type, amount):
    currency_types = ['USD', 'INR', 'GBP', 'CAD', 'AUD', 'EUR']
    if src_currency_type is not None and src_currency_type.upper() not in currency_types:
        return build_validation_result(False,
                                       'SrcCurrency',
                                       'We dont support {}, would you like to check different Currency? '
                                       'Supported currencies are USD,INR,GBP,CAD,AUD,EUR'.format(src_currency_type))
    if tgt_currency_type is not None and tgt_currency_type.upper() not in currency_types:
        return build_validation_result(False,
                                       'TgtCurrency',
                                       'We dont support {}, would you like to check different Currency? '
                                       'Supported currencies are USD,INR,GBP,CAD,AUD,EUR'.format(tgt_currency_type))
    if amount <= 0:
        # Not a valid amount.
        return build_validation_result(False, 'Amount', 'Enter a valid amount to convert')

    return build_validation_result(True, None, None)
    

""" --- Functions that control the bot's behavior --- """

def currency_conversion(intent_request):
    """
    This function validates the user inputs and then performs the fulfillment logic
    """

    src_currency_type = get_slots(intent_request)["SrcCurrency"]
    tgt_currency_type = get_slots(intent_request)["TgtCurrency"]
    amount = get_slots(intent_request)["Amount"]
    source = intent_request['invocationSource']

    if source == 'DialogCodeHook':
        # Perform basic validation on the supplied input slots.
        # Use the elicitSlot dialog action to re-prompt for the first violation detected.
        slots = get_slots(intent_request)

        validation_result = validate_currency_fields(src_currency_type, tgt_currency_type, amount)
        if not validation_result['isValid']:
            slots[validation_result['violatedSlot']] = None
            return elicit_slot(intent_request['sessionAttributes'],
                               intent_request['currentIntent']['name'],
                               slots,
                               validation_result['violatedSlot'],
                               validation_result['message'])

        # Pass back the session attributes to be used in various prompts defined on the bot model.
        output_session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
        return delegate(output_session_attributes, get_slots(intent_request))

    # Convert the amount, and rely on the goodbye message of the bot to define the message to the end user.
    exchange_rate = get_exchange_rate(src_currency_type.upper(), tgt_currency_type.upper())
    converted_amount = float(amount) * exchange_rate
    
    return close(intent_request['sessionAttributes'],
                 'Fulfilled',
                 {'contentType': 'PlainText',
                  'content': 'Thanks, your converted amount is {}. Good Bye!'.format(converted_amount)})


""" --- Intents --- """

def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.debug('dispatch userId={}, intentName={}'.format(intent_request['userId'], intent_request['currentIntent']['name']))

    intent_name = intent_request['currentIntent']['name']

    # Dispatch to your bot's intent handlers
    if intent_name == 'CurrencyConversion':
        return currency_conversion(intent_request)

    raise Exception('Intent with name ' + intent_name + ' not supported')


""" --- Main handler --- """


def lambda_handler(event, context):
    """
    Route the incoming request based on intent.
    The JSON body of the request is provided in the event slot.
    """
    # By default, treat the user request as coming from the America/New_York time zone.
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    logger.debug('event.bot.name={}'.format(event['bot']['name']))

    return dispatch(event)
