import re
from enum import Enum
from re import RegexFlag

import dotenv

PFP_SIZE = (200, 200)
MAINT_UPDATE_LOOP_TIMER = 5 * 60  # update every 5 mins
LEIKA_PATTERN = re.compile(r"<:.*?leika.*?:\d+?>", flags=RegexFlag.IGNORECASE)
MONOBOT_WEBHOOK_NAME = "Monobot Webhook"
EXPLODE_EMOTE = '<:explode:1333259731640258581>'
SOMEONE_EMOTE = '<:SomeoneSmile:1463708490001416375>'

TIMEZONES = ['Africa/Cairo', 'Africa/Johannesburg', 'Africa/Lagos', 'Africa/Monrousing', 'America/Anchorage',
             'America/Chicago', 'America/Denver', 'America/Edmonton', 'America/Jamaica', 'America/Los_Angeles',
             'America/Mexico City', 'America/Montreal', 'America/New_York', 'America/Phoenix', 'America/Puerto_Rico',
             'America/Sao Paulo', 'America/Toronto', 'America/Vancouver', 'Asia/Hong_Kong', 'Asia/Jerusalem',
             'Asia/Manila', 'Asia/Seoul', 'Asia/Taipei', 'Asia/Tokyo', 'Atlantic/Reykjavik', 'Australia/Perth',
             'Australia/Sydney', 'Europe/Athens', 'Europe/Berlin', 'Europe/Brussels', 'Europe/Copenhagen',
             'Europe/Lisbon', 'Europe/London', 'Europe/Madrid', 'Europe/Moscow', 'Europe/Paris', 'Europe/Prague',
             'Europe/Rome', 'Europe/Warsaw', 'Pacific/Auckland', 'Pacific/Guam', 'Pacific/Honolulu', 'UTC']

env = dotenv.dotenv_values()
COMMAND_PREFIX = env.get('PREFIX')
OWNER_ID = env.get('OWNER_ID')
BOT_ID = env.get('BOT_ID')
MEAT_SHIELD_ID = env.get('MEAT_SHIELD')
LEIKA_SMILER_ID = env.get('LEIKA_SMILE')
EXPLODE_ID = env.get('EXPLODE')
DEBUG = int(env.get('DEBUG', 0))

ROLL_HELP = f"""
syntax key: [these are required] (these are optional)
\t**fitd mode**: {COMMAND_PREFIX}[num dice]d(num sides)(! for unsorted rolls) #(message)
\t\texample: {COMMAND_PREFIX}4d! #this will roll 4 d6s unsorted
\t**wildseas mode**: {COMMAND_PREFIX}[num dice]d(num sides)(! for unsorted rolls) -(num dice to cut) #(message)
\t\texample: {COMMAND_PREFIX}3d! -1 #this will roll 3 d6s unsorted with a cut of 1
\t**cain mode**: {COMMAND_PREFIX}[num dice]d(num sides)(! for unsorted rolls) (h for hard)(r for risky) #(message)
\t\texample: {COMMAND_PREFIX}5d hr #this will roll 5 d6s with hard and risky results
\t**hunter mode**: {COMMAND_PREFIX}[num dice]d(num sides)(! for unsorted rolls) (d[num desperation dice]) #(message)
\t\texample: {COMMAND_PREFIX}3d d2 #this will roll 3 d10s with 2 d10 desperation dice
\t**persona mode**: {COMMAND_PREFIX}[num dice]d(num sides)(! for unsorted rolls) #(message)
\t\texample: {COMMAND_PREFIX}4d #this will roll 4 d6s
\t**delta green mode**: use `{COMMAND_PREFIX}help skill` or `{COMMAND_PREFIX}help lethal`
"""


class RollModeEnum(Enum):
    WILDSEAS = "wildseas"
    FITD = "fitd"
    CAIN = "cain"
    HUNTER = "hunter"
    PERSONA = "persona"
    DG = "deltagreen"


WILDSEA_DICT = {
    1: 'Failure',
    2: 'Failure',
    3: 'Failure',
    4: 'Conflict',
    5: 'Conflict',
    6: 'Success'
}
FITD_DICT = {
    1: 'Failure',
    2: 'Failure',
    3: 'Failure',
    4: 'Success (with consequence)',
    5: 'Success (with consequence)',
    6: 'Success'
}
RISK_DICT = {
    1: '[2;31ma much worse result[0m',
    2: '[2;33ma worse result[0m',
    3: '[2;33ma worse result[0m',
    4: '[2;32man expected result[0m',
    5: '[2;32man expected result[0m',
    6: '[2;36ma better result[0m'
}
CAIN_DICT = {
    1: 'Failure',
    2: 'Failure',
    3: 'Failure',
    4: 'Success',
    5: 'Success',
    6: 'Success'
}
CAIN_DICT_HARD = {
    1: 'Failure',
    2: 'Failure',
    3: 'Failure',
    4: 'Failure',
    5: 'Failure',
    6: 'Success'
}
HUNTER_DICT = {
    1: 'Failure',
    2: 'Failure',
    3: 'Failure',
    4: 'Failure',
    5: 'Failure',
    6: 'Success',
    7: 'Success',
    8: 'Success',
    9: 'Success',
    10: 'Success'
}

NUM_TO_EMOTE = {
    1: '1️⃣',
    2: '2️⃣',
    3: '3️⃣',
    4: '4️⃣',
    5: '5️⃣',
    6: '6️⃣',
    7: '7️⃣',
    8: '8️⃣',
    9: '9️⃣'
}

HATE_WEIGHTS = [1, .5, .25, .02, .01, .001]
HATE_LIST = [
    '\neat shit!!!!!',
    '\nexplode???',
    '\n>:3',
    '\nLOL',
    '\nlmao'
]
