import io
import json
import math
import random
import re
import logging

import dotenv
import discord
import uwuipy
import feedparser
import easyocr

from datetime import datetime
from dateutil import parser, tz
from enum import Enum
from PIL import Image
from discord.ext import commands
from discord.ext.commands import CommandOnCooldown
from threading import Timer

# TODO: Oh my god this is so bad I need to make this a proper class before GOD HIMSELF SMITES ME

PFP_SIZE = (200, 200)
MAINT_UPDATE_LOOP = 5 * 60  # update every 5 mins

env = dotenv.dotenv_values()
COMMAND_PREFIX = env.get('PREFIX')
OWNER_ID = env.get('OWNER_ID')
BOT_ID = env.get('BOT_ID')
EXPLODE_ID = env.get('EXPLODE')
EXPLODE_MORE_ID = env.get('EXPLODE_MORE')
DEBUG = int(env.get('DEBUG', 0))

log = logging.getLogger('MonoBot')
logging.basicConfig(format='%(asctime)s:%(name)s:%(levelname)s:%(funcName)s:%(message)s',
                    filename='run.log',
                    encoding='utf-8',
                    level=logging.INFO)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.AutoShardedBot(command_prefix='', intents=intents, help_command=None)

stupid_fucking_pillar = dict()
data = {'maint': {}, 'roll mode': {}}
try:
    with open('data.json', 'r') as file:
        data = json.load(file)
except Exception as e:
    log.warning(f'Exception when loading data, resetting: {e}')
    with open('data.json', 'w') as file:
        json.dump(data, file)

uwu_factory = uwuipy.Uwuipy(face_chance=.075)


class GuildStatus(Enum):
    TOUCHSONAR = 0


wildsea_dict = {
    1: 'Failure',
    2: 'Failure',
    3: 'Failure',
    4: 'Conflict',
    5: 'Conflict',
    6: 'Success'
}

fitd_dict = {
    1: 'Failure',
    2: 'Failure',
    3: 'Failure',
    4: 'Success (with consequence)',
    5: 'Success (with consequence)',
    6: 'Success'
}

risk_dict = {
    1: '[2;31ma much worse result[0m',
    2: '[2;33ma worse result[0m',
    3: '[2;33ma worse result[0m',
    4: '[2;32man expected result[0m',
    5: '[2;32man expected result[0m',
    6: '[2;36ma better result[0m'
}

cain_dict = {
    1: 'Failure',
    2: 'Failure',
    3: 'Failure',
    4: 'Success',
    5: 'Success',
    6: 'Success'
}

cain_dict_hard = {
    1: 'Failure',
    2: 'Failure',
    3: 'Failure',
    4: 'Failure',
    5: 'Failure',
    6: 'Success'
}

hunter_dict = {
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


@bot.event
async def on_ready():
    log.info(f'{bot.user} has connected to Discord!')
    activity = discord.Activity(type=discord.ActivityType.playing, name="actual suffering")
    await bot.change_presence(activity=activity)


@bot.event
async def on_command_error(ctx, error):
    log.error(f'command error: {error}')
    if isinstance(error, CommandOnCooldown):
        await ctx.send(f'<:explode:1333259731640258581>')


@bot.event
async def on_message(message: discord.Message):
    if message.author.id == int(BOT_ID):
        return

    if message.content == f'{COMMAND_PREFIX}':
        await nodice(message)
    elif message.content and message.content[0] == COMMAND_PREFIX:
        if f'{message.guild.id}' not in data['roll mode']:
            await __default_mode(message)
        # check for dice rolls
        if await roll_dice(message):
            return
        message.content = message.content[1:]
        await bot.process_commands(message)

    elif (message.guild.id in stupid_fucking_pillar and
          stupid_fucking_pillar[message.guild.id]['status'] == GuildStatus.TOUCHSONAR and
          message.content and
          message.content[0] != 'f' and
          message.content[0] != 'F'):
        try:
            await message.delete()
        except Exception as e:
            log.error(f'error deleting on message in touchsonar: {e}')


@bot.event
async def on_message_edit(before: discord.Message, message: discord.Message):
    if (message.guild.id in stupid_fucking_pillar and
            message.author.id != int(BOT_ID) and
            stupid_fucking_pillar[message.guild.id]['status'] == GuildStatus.TOUCHSONAR and
            message.created_at.timestamp() > stupid_fucking_pillar[message.guild.id]['start'] and
            message.content and
            message.content[0] != 'f' and
            message.content[0] != 'F'):
        try:
            await message.delete()
        except Exception as e:
            log.error(f'error deleting on edit in touchsonar: {e}')


@bot.command(help='sends this message', usage=['help', 'help CMD'])
async def help(ctx: discord.ext.commands.Context):
    cmd = ctx.message.content.split()
    if len(cmd) <= 1:
        help_message = ''
        for command in sorted(bot.commands, key=lambda c: c.name):
            help_message += f"**{COMMAND_PREFIX}{command.name}**: {command.help or 'no description provided'}\n"
        help_message += f'`or you can {COMMAND_PREFIX}help CMD to learn more about a specific command`'
        await ctx.send(help_message)
        return

    cmd_name = cmd[1].strip()
    if cmd_name in bot.all_commands:
        help_cmd = bot.all_commands[cmd_name]
        help_msg = f'[{COMMAND_PREFIX}{help_cmd.name} |'
        for alias in help_cmd.aliases:
            help_msg += f' {COMMAND_PREFIX}{alias} |'
        help_msg = f'{help_msg[:-2]}]\n'

        help_msg += f"\t**help**: {help_cmd.help or 'no description provided'}\n"
        if help_cmd.usage:
            help_msg += f"\t**usage**:"
            for usage in help_cmd.usage:
                help_msg += f' {COMMAND_PREFIX}{usage} |'
            help_msg = f'{help_msg[:-2]}'

        await ctx.send(help_msg)
    else:
        await ctx.send(f'command "{cmd_name}" not found')


if not DEBUG:
    ocr_reader = easyocr.Reader(['en'])
    rss_url = 'https://store.steampowered.com/feeds/news/app/1973530/'


def maint_update(curr_news):
    date_str = curr_news.title.replace('Scheduled Update Notice', '')
    image_url = curr_news.summary.split('"')[1]
    detection = ocr_reader.readtext(image_url)

    detect_str = ''
    for txt in detection:
        detect_str += txt[1].strip() + ' '
    detect_str = detect_str.strip()

    time_strs = [w for w in detect_str.split('from') if '[AM]' in w][0]
    time_strs = time_strs.split('on')[0].split('through')

    from_time_str = time_strs[0].replace('[', '').replace(']', '')
    to_time_str = time_strs[1].replace('[', '').replace(']', '')

    data['maint']['curr maint'] = curr_news.title
    data['maint']['from time'] = from_time_str
    data['maint']['to time'] = to_time_str
    data['maint']['date'] = date_str
    with open('data.json', 'w') as file:
        json.dump(data, file)


def headless_maint_update():
    feed = feedparser.parse(rss_url)
    if feed.bozo:
        log.error('failed to fetch steam news stream')
        return
    update_news = [news for news in feed.entries if 'Scheduled Update Notice' in news.title]

    curr_news = update_news[0]
    if 'curr maint' not in data['maint'] or data['maint']['curr maint'] != curr_news.title:
        log.info('cached maint news out of date, fetching and parsing online news headlessly...')
        maint_update(curr_news)
        log.info('headlessly updated maint news')
    else:
        log.debug('cached maint up to date')


maint_update_timer = Timer(MAINT_UPDATE_LOOP, headless_maint_update)
maint_update_timer.daemon = True
maint_update_timer.start()


@bot.command(help='get time of Limbus maintenance', usage=['maint'])
async def maint(ctx: discord.ext.commands.Context):
    feed = feedparser.parse(rss_url)
    if feed.bozo:
        await ctx.send('failed to fetch steam news stream')
        return

    update_news = [news for news in feed.entries if 'Scheduled Update Notice' in news.title]
    if len(update_news) == 0:
        await ctx.send('no recent scheduled updates found')
        return

    curr_news = update_news[0]
    if 'curr maint' in data['maint'] and data['maint']['curr maint'] == curr_news.title:
        log.info('fetching cached current maint news...')
        from_time_str = data['maint']['from time']
        to_time_str = data['maint']['to time']
        date_str = data['maint']['date']
    else:
        log.info('cached maint news out of date, fetching and parsing online news...')
        await ctx.send('fetching current maintenance news, this may take a second...')
        maint_update(curr_news)
        date_str = data['maint']['date']
        from_time_str = data['maint']['from time']
        to_time_str = data['maint']['to time']

    from_time = parser.parse(date_str + ' ' + from_time_str).replace(tzinfo=tz.gettz('Asia/Seoul'))
    to_time = parser.parse(date_str + ' ' + to_time_str).replace(tzinfo=tz.gettz('Asia/Seoul'))

    now = int(datetime.now().timestamp())
    from_timestamp = int(from_time.timestamp())
    to_timestamp = int(to_time.timestamp())
    if now < from_timestamp:
        await ctx.send(f'the next maintenance begins <t:{from_timestamp}:R> at <t:{from_timestamp}> and ends at '
                       f'<t:{to_timestamp}>')
    elif from_timestamp <= now < to_timestamp:
        await ctx.send(f'the current maintenance ends <t:{to_timestamp}:R> at <t:{to_timestamp}>')
    else:
        await ctx.send(f'the last maintenance ended <t:{to_timestamp}:R> at <t:{to_timestamp}>')


@bot.command(help='forces all messages to start with f (admins only)')
async def touchsonar(ctx: discord.ext.commands.Context, *, msg=''):
    if not ctx.author.guild_permissions.administrator and not f'{ctx.author.id}' == OWNER_ID:
        await ctx.send(f'turning on touch sonar can only be done by admins & mono')
        return

    global stupid_fucking_pillar
    if (ctx.guild.id in stupid_fucking_pillar and
            not stupid_fucking_pillar[ctx.guild.id]['status'] == GuildStatus.TOUCHSONAR):
        await ctx.send('another status is currently being applied to this server!')
    elif ctx.guild.id in stupid_fucking_pillar:
        del stupid_fucking_pillar[ctx.guild.id]
        await ctx.send('touch based sonar now optional')
    else:
        stupid_fucking_pillar[ctx.guild.id] = {
            'status': GuildStatus.TOUCHSONAR,
            'start': datetime.now().timestamp()
        }
        await ctx.send('touch based sonar now enforced')


@bot.command(help='chooses from list of comma-separated choices', usage=['choose CHOICE, CHOICE, CHOICE, ...'])
async def choose(ctx: discord.ext.commands.Context, *, msg=''):
    split = [x.strip() for x in ctx.message.content[7:].split(',')]
    if len(split) == 0:
        await ctx.send("you'll need to give me a list of comma-separated choices for me to choose from")
    else:
        await ctx.send(f'{ctx.message.author.mention}, i choose `{random.choice(split)}` for you')


class RollModeEnum(Enum):
    WILDSEAS = "wildseas"
    FITD = "fitd"
    CAIN = "cain"
    HUNTER = "hunter"


modes = {e.value for e in RollModeEnum}


def __get_curr_roll_mode(message: discord.Message) -> str:
    guild_id = data['roll mode'][f'{message.guild.id}']
    if f'{message.channel.category.id}' in guild_id['category']:
        return guild_id['category'][f'{message.channel.category.id}']
    else:
        return guild_id['server']


async def __default_mode(message: discord.Message):
    data['roll mode'][f'{message.channel.guild.id}'] = {"server": RollModeEnum.FITD.value, "category": {}}
    with open('data.json', 'w') as file:
        json.dump(data, file)
    await message.channel.send(f'server currently has no rolling mode, setting to "fitd" by default')


async def __remove_local_roll_mode(ctx: discord.ext.commands.Context):
    try:
        del data['roll mode'][f'{ctx.guild.id}']['category'][f'{ctx.channel.category.id}']
        await ctx.send('removing local rolling mode...')
    except KeyError:
        await ctx.send("local rolling mode doesn't exist!")


@bot.command(help='set rolling mode of the server/category (channel managers only)',
             usage=['mode MODE', 'mode local MODE'])
async def mode(ctx: discord.ext.commands.Context, *, msg=''):
    split = ctx.message.content.split(' ')
    if len(split) == 1:
        if f'{ctx.guild.id}' in data['roll mode']:
            send_str = f'current server rolling mode: "{data["roll mode"][str(ctx.guild.id)]["server"]}"'
            if f'{ctx.channel.category.id}' in data['roll mode'][str(ctx.guild.id)]['category']:
                send_str += f'\ncurrent category rolling mode: "{data["roll mode"][str(ctx.guild.id)]["category"][str(ctx.channel.category.id)]}"'
            await ctx.send(send_str)
        else:
            await __default_mode(ctx.message)
        return

    if not ctx.author.guild_permissions.manage_channels and not f'{ctx.author.id}' == OWNER_ID:
        await ctx.send(f'setting the rolling mode of this server can only be done by channel managers & mono')
        return

    mode = split[1]
    server_scope = True
    if mode == 'local':
        if len(split) <= 2:
            await __remove_local_roll_mode(ctx)
            return
        mode = split[2]
        server_scope = False

    if mode not in modes:
        await ctx.send(f'mode does not exist!\nallowed rolling modes: *{", ".join(sorted(modes))}*')
    else:
        if server_scope:
            data['roll mode'][f'{ctx.guild.id}']['server'] = mode
        else:
            if mode == data['roll mode'][f'{ctx.guild.id}']['server']:
                await __remove_local_roll_mode(ctx)
            else:
                data['roll mode'][f'{ctx.guild.id}']['category'][f'{ctx.channel.category.id}'] = mode

        with open('data.json', 'w') as file:
            json.dump(data, file)
        if server_scope:
            await ctx.send(f'successfully set rolling mode of this server to "{mode}"')
        else:
            await ctx.send(f'successfully set rolling mode of this category to "{mode}"')


@bot.command(help='good advice')
async def touchgrass(ctx: discord.ext.commands.Context, *, msg=''):
    await ctx.send('https://hard-drive.net/hd/video-games/top-10-grasses-to-go-touch/')


@bot.command(help='uwu someone by replying to them or uwu your own message', usage=['uwu', 'uwu MSG'])
async def uwu(ctx: discord.ext.commands.Context, *, msg=''):
    if ctx.message.reference:
        raw_msg = await ctx.fetch_message(ctx.message.reference.message_id)
        uwu_msg = uwu_factory.uwuify(raw_msg.content)
    else:
        uwu_msg = uwu_factory.uwuify(ctx.message.content[4:])
    await ctx.send(uwu_msg)


async def nodice(message: discord.Message):
    choice = [
        'got dice?',
        'gonna roll anything there buddy?',
        'you think i can roll null dice?',
        'did you forget to write something there'
    ]
    await message.channel.send(f'{message.author.mention} {random.choice(choice)}')


num_to_word = {
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


@bot.command(aliases=['p'],
             help='sets up a poll, add options by passing a list of comma-separated choices (limit of 9)',
             usage=['poll CHOICE, CHOICE, CHOICE, ...'])
async def poll(ctx: discord.ext.commands.Context, *, msg=''):
    options = [s.strip() for s in msg.strip().split(',') if len(s) > 0]
    if len(options) > 9:
        await ctx.send('do you really need that many options in a poll?')
        return
    if len(options) < 1:
        await ctx.send('you gonna put any options in that poll? (ps. you can add them through a comma-separated list)')
        return
    if len(options) == 1:
        await ctx.send(
            'a poll with only one option is kinda boring isn\'t it? (ps. you can add more through a comma-separated list)'
        )
        return

    message = ''
    for i in range(len(options)):
        message += f'{num_to_word[i + 1]}: {options[i]}\n'
    sent_msg = await ctx.send(message)

    for i in range(len(options)):
        await sent_msg.add_reaction(f'{num_to_word[i + 1]}')


@bot.command(aliases=['qp'], help='sets up a yes/no poll')
async def quickpoll(ctx: discord.ext.commands.Context, *, msg=''):
    await ctx.message.add_reaction("✅")
    await ctx.message.add_reaction("❌")


@bot.command(help='reply/mention someone to make them a wee bit yellow', usage=['pee', 'pee @USER'])
async def pee(ctx: discord.ext.commands.Context, *, msg=''):
    def make_pee():
        pee_mask = Image.new('RGBA', PFP_SIZE, (255, 255, 0, 100))
        pfp.paste(pee_mask, (0, 0), pee_mask)
        pee_pfp_bytes = io.BytesIO()
        pfp.save(pee_pfp_bytes, format="PNG")
        pee_pfp_bytes.seek(0)
        return pee_pfp_bytes

    if ctx.message.mentions:
        author_pfp = await ctx.message.mentions[0].display_avatar.with_static_format('png').read()
        pfp = Image.open(io.BytesIO(author_pfp)).resize(PFP_SIZE)
        await ctx.send(file=discord.File(make_pee(), filename='boom.gif'))
    elif ctx.message.reference:
        ref = await ctx.fetch_message(ctx.message.reference.message_id)
        author_pfp = await ref.author.display_avatar.with_static_format('png').read()
        pfp = Image.open(io.BytesIO(author_pfp)).resize(PFP_SIZE)
        await ctx.send(file=discord.File(make_pee(), filename='boom.gif'))
    else:
        author_pfp = await ctx.author.display_avatar.with_static_format('png').read()
        pfp = Image.open(io.BytesIO(author_pfp)).resize(PFP_SIZE)

        mask = Image.new('RGBA', PFP_SIZE, (255, 255, 0, 100))
        pfp.paste(mask, (0, 0), mask)
        pfp_bytes = io.BytesIO()
        pfp.save(pfp_bytes, format="PNG")
        pfp_bytes.seek(0)
        await ctx.send(file=discord.File(pfp_bytes, filename='gun.png'))


@bot.command(help='mention mono')
@commands.cooldown(5, 300)
async def a(ctx: discord.ext.commands.Context, *, msg=''):
    await ctx.send(f'<@{OWNER_ID}>')


@bot.command(help='give yourself a gun, as a treat')
async def gun(ctx: discord.ext.commands.Context, *, msg=''):
    author_pfp = await ctx.author.display_avatar.with_static_format('png').read()
    gun = Image.open('./img/gun.png').resize((150, 150))
    pfp = Image.open(io.BytesIO(author_pfp)).resize(PFP_SIZE)
    pfp.paste(gun, (90, 50), gun)

    pfp_bytes = io.BytesIO()
    pfp.save(pfp_bytes, format="PNG")
    pfp_bytes.seek(0)
    await ctx.send(file=discord.File(pfp_bytes, filename='gun.png'))


@bot.command(help='show the bot a bit of love (some exceptions apply)')
async def love(ctx: discord.ext.commands.Context, *, msg=''):
    if ctx.message.author.id == int(EXPLODE_ID):
        if random.random() < 0.05:
            love = ['💕', '💝', '💖']
            await ctx.message.add_reaction(random.choice(love))
        else:
            await ctx.message.add_reaction('<:explode:1333259731640258581>')

    elif ctx.message.author.id == int(EXPLODE_MORE_ID):
        if random.random() < 0.5:
            await ctx.message.add_reaction('<:explode:1333259731640258581>')
        else:
            love = ['⭐', '✨', '💕', '💝', '💖']
            for lv in love:
                await ctx.message.add_reaction(random.choice(lv))

    else:
        if random.random() < 0.05:
            await ctx.message.add_reaction('<:explode:1333259731640258581>')
        else:
            love = ['💕', '💝', '💖']
            await ctx.message.add_reaction(random.choice(love))


@bot.command(help='reply/mention someone to blow them up, or send some nyukes',
             usage=['explode', 'explode @USER', 'explode NUM'])
async def explode(ctx: discord.ext.commands.Context, *, msg=""):
    def make_explode(boom_pfp):
        frames = []
        for frame_name in range(17):
            frame = Image.open(f'./img/explosion/{frame_name + 1}.png')
            static_copy = boom_pfp.copy()
            static_copy.paste(frame.convert("RGBA"), (0, 0), frame.convert("RGBA"))
            frames.append(static_copy)

        pfp_boom_buffer = io.BytesIO()
        frames[0].save(pfp_boom_buffer, format="GIF", save_all=True, append_images=frames[1:], loop=0, duration=10,
                       disposal=2)
        pfp_boom_buffer.seek(0)
        return pfp_boom_buffer

    if ctx.message.mentions or ctx.message.reference:
        message = ''
        if ctx.message.mentions:
            if ctx.message.mentions[0].id == int(OWNER_ID):
                author_pfp = await (
                    await bot.fetch_user(int(EXPLODE_ID))).display_avatar.with_static_format('png').read()
                message = 'MEAT SHIELD GO'
            else:
                author_pfp = await ctx.message.mentions[0].display_avatar.with_static_format('png').read()
        else:
            ref = await ctx.fetch_message(ctx.message.reference.message_id)
            if ref.author.id == int(OWNER_ID):
                author_pfp = await (
                    await bot.fetch_user(int(EXPLODE_ID))).display_avatar.with_static_format('png').read()
                message = 'MEAT SHIELD GO'
            else:
                author_pfp = await ref.author.display_avatar.with_static_format('png').read()
        pfp = Image.open(io.BytesIO(author_pfp)).resize(PFP_SIZE)
        await ctx.send(message, file=discord.File(make_explode(pfp), filename='boom.gif'))
    else:
        count = 1
        if len(msg) >= 1:
            count = int(msg)

        if count > 30:
            await ctx.send('i do not permit you to blow up the server')
            count = 30
        message = ''
        limit = 0
        for _ in range(count):
            message += '<:explode:1333259731640258581> '
            limit += 1
            if limit >= 30:
                await ctx.send(message)
                message = ''
                limit = 0

        if len(message) > 0:
            await ctx.send(message)


def __has_duplicates(lst):
    counts = {}
    for num in lst:
        if num in counts:
            return True
        counts[num] = 1
    return False


weights = [1, .5, .25, .02, .01, .001]
hate_list = [
    '\neat shit!!!!!',
    '\nexplode???',
    '\n>:3',
    '\nLOL',
    '\nlmao'
]


def __roll_hate(fstr, fval, pool, roll_mode):
    fstr += f' [`10d`: **{fval}**; '
    for x in pool:
        fstr += f'`{x}`, '
    fstr = fstr[:-2] + "]"
    if fval <= 3:
        c = random.choice(hate_list)
        fstr += c
    elif roll_mode != RollModeEnum.CAIN.value:
        if fval == 6:
            fstr += '\ndamn...'
    else:
        if fval > 3:
            fstr += '\ndamn...'
    return fstr


def __hate_wildseas(ctx: discord.ext.commands.Context, pool, fval):
    twist = __has_duplicates(pool)
    if not twist:
        fstr = f'{ctx.message.author.mention}, you rolled 10d for a **{wildsea_dict[fval]}**.'
    else:
        fstr = f'{ctx.message.author.mention}, you rolled 10d for a **Twist** and a **{wildsea_dict[fval]}**.'
    return __roll_hate(fstr, fval, pool, RollModeEnum.WILDSEAS.value)


def __hate_fitd(ctx: discord.ext.commands.Context, pool, fval):
    crit = pool.count(6) >= 2
    if not crit:
        fstr = f'{ctx.message.author.mention}, you rolled 10d for a **{fitd_dict[fval]}**.'
    else:
        fstr = f'{ctx.message.author.mention}, you rolled 10d for a **Critical Success**.'
    return __roll_hate(fstr, fval, pool, RollModeEnum.FITD.value)


def __hate_cain(ctx: discord.ext.commands.Context, pool, fval):
    num_success = len([x for x in pool if x > 3])
    if num_success <= 1:
        fstr = f'{ctx.message.author.mention}, you rolled 10d for a **{cain_dict[fval]}**.'
    else:
        fstr = f'{ctx.message.author.mention}, you rolled 10d for {num_success} **Successes**.'
    return __roll_hate(fstr, fval, pool, RollModeEnum.CAIN.value)


@bot.command(help='let the bot vent some rage, may or may not improve your rolls')
async def hate(ctx: discord.ext.commands.Context, *, msg=""):
    pool = [random.choices(range(1, 7), weights=weights)[0] for _ in range(10)]
    pool = sorted(pool, reverse=True)
    fval = max(pool)

    roll_mode = __get_curr_roll_mode(ctx.message)
    if roll_mode == RollModeEnum.WILDSEAS.value:
        await ctx.send(__hate_wildseas(ctx, pool, fval))
    elif roll_mode == RollModeEnum.FITD.value:
        await ctx.send(__hate_fitd(ctx, pool, fval))
    elif roll_mode == RollModeEnum.CAIN.value:
        await ctx.send(__hate_cain(ctx, pool, fval))
    else:
        await ctx.send("invalid roll mode: " + roll_mode)


def __roll_risk_msg():
    roll = random.randint(1, 6)
    return """
```ansi
[1mRisk[0m: You rolled {roll} for {risk}
```""".format(roll=roll, risk=risk_dict[roll])


@bot.command(aliases=['r'], help='roll risk (only usable with Cain)')
async def risk(ctx: discord.ext.commands.Context, *, msg=""):
    if __get_curr_roll_mode(ctx.message) == RollModeEnum.CAIN.value:
        await ctx.send(__roll_risk_msg())
    else:
        await ctx.send('only available for "cain" roll mode')


def __roll_cain(original_msg: discord.Message,
                message: str,
                dice: int,
                is_risky: bool,
                is_hard: bool,
                sort_dice: bool,
                sides: int = 6):
    if dice > 0:
        pool = [random.randint(1, sides) for _ in range(dice)]
        fval = max(pool)

        if is_hard:
            num_success = pool.count(6)
        else:
            num_success = sum(pool.count(i) for i in range(4, 7))

        fstr = f'{original_msg.author.mention}, you rolled {dice}d{sides if sides != 6 else ""}'
        if is_hard:
            fstr += ' with *hard*'
        if sides == 6:
            if num_success <= 1:
                fstr += f' for a **{cain_dict_hard[fval] if is_hard else cain_dict[fval]}**'
            else:
                fstr += f' for {num_success} **Successes**'
        fstr += f'{f"; roll for `{message}`" if message else ""}.'

        fstr += f' [`{dice}d`: **{fval}**; '
        for x in (sorted(pool, reverse=True) if sort_dice else pool):
            fstr += f'`{x}`, '
    else:
        pool = [random.randint(1, 6) for _ in range(2 - dice)]
        fval = min(pool)
        fstr = f'{original_msg.author.mention}, you rolled {dice}d{sides if sides != 6 else ""}'
        if is_hard:
            fstr += ' with *hard*'
        if sides == 6:
            fstr += f' for a **{cain_dict_hard[fval] if is_hard else cain_dict[fval]}**'
        fstr += f'{f"; roll for `{message}`" if message else ""}.'
        fstr += f' [`{dice}d`: **{fval}**; `{sorted(pool)[0]}`, '
        for x in sorted(pool)[1:]:
            fstr += f'~~`{x}`~~, '

    fstr = fstr[:-2] + "]"
    if is_risky:
        fstr += __roll_risk_msg()
    return fstr


def __roll_wildsea(original_msg: discord.Message, message: str, cut: int, dice: int, sort_dice: bool, sides: int = 6):
    if cut > 0:
        if dice - cut <= 0:
            if random.random() < .1:
                return (f'{original_msg.author.mention}, you cut all your dice for a **{wildsea_dict[1]}** like the '
                        f'fool you are')
            else:
                return f'{original_msg.author.mention}, you cut all your dice for a **{wildsea_dict[1]}**'

    if dice > 0:
        pool = [random.randint(1, sides) for _ in range(dice)]

        if cut > 0:
            pool = sorted(pool, reverse=True)
            fval = pool[cut]
            twist = __has_duplicates(pool[cut:])

            if not twist:
                fstr = (f'{original_msg.author.mention}, you rolled {dice}d'
                        f'{sides if sides != 6 else ""}'
                        f'{f" with cut of {cut} for a **{wildsea_dict[fval]}**" if sides == 6 else ""}'
                        f'{f"; roll for `{message}`" if message else ""}.')
            else:
                fstr = (f'{original_msg.author.mention}, you rolled {dice}d'
                        f'{sides if sides != 6 else ""}'
                        f'{f" with cut of {cut} for a **Twist** and a **{wildsea_dict[fval]}**"}'
                        f'{f"; roll for `{message}`" if message else ""}.')

            cut_count = 0
            fstr += f' [`{dice}d`: **{fval}**; '
            for x in pool:
                if cut_count < cut:
                    fstr += f'~~`{x}`~~, '
                    cut_count += 1
                else:
                    fstr += f'`{x}`, '
            return fstr[:-2] + "]"
        else:
            fval = max(pool)
            twist = __has_duplicates(pool)

            if not twist:
                fstr = (f'{original_msg.author.mention}, you rolled {dice}d'
                        f'{sides if sides != 6 else ""}'
                        f'{f" for a **{wildsea_dict[fval]}**" if sides == 6 else ""}'
                        f'{f"; roll for `{message}`" if message else ""}.')
            else:
                fstr = (f'{original_msg.author.mention}, you rolled {dice}d'
                        f'{sides if sides != 6 else ""}'
                        f'{f" for a **Twist** and a **{wildsea_dict[fval]}**" if sides == 6 else ""}'
                        f'{f"; roll for `{message}`" if message else ""}.')

            fstr += f' [`{dice}d`: **{fval}**; '
            for x in (sorted(pool, reverse=True) if sort_dice else pool):
                fstr += f'`{x}`, '
            return fstr[:-2] + "]"
    else:
        pool = [random.randint(1, 6) for _ in range(2 - dice)]
        fval = min(pool)
        fstr = (f'{original_msg.author.mention}, you rolled {dice}d'
                f'{sides if sides != 6 else ""}'
                f'{f" for a **{wildsea_dict[fval]}**" if sides == 6 else ""}'
                f'{f"; roll for `{message}`" if message else ""}.')

        fstr += f' [`{dice}d`: **{fval}**; `{sorted(pool)[0]}`, '
        for x in sorted(pool)[1:]:
            fstr += f'~~`{x}`~~, '
        return fstr[:-2] + "]"


def __roll_fitd(original_msg: discord.Message, message: str, dice: int, sort_dice: bool, sides: int = 6):
    if dice > 0:
        pool = [random.randint(1, sides) for _ in range(dice)]
        fval = max(pool)

        crit = pool.count(6) >= 2
        if not crit:
            fstr = (f'{original_msg.author.mention}, you rolled {dice}d'
                    f'{sides if sides != 6 else ""}'
                    f'{f" for a **{fitd_dict[fval]}**" if sides == 6 else ""}'
                    f'{f"; roll for `{message}`" if message else ""}.')
        else:
            fstr = (f'{original_msg.author.mention}, you rolled {dice}d'
                    f'{sides if sides != 6 else ""}'
                    f'{f" for a **Critical Success**" if sides == 6 else ""}'
                    f'{f"; roll for `{message}`" if message else ""}.')

        fstr += f' [`{dice}d`: **{fval}**; '
        for x in (sorted(pool, reverse=True) if sort_dice else pool):
            fstr += f'`{x}`, '
        return fstr[:-2] + "]"
    else:
        pool = [random.randint(1, 6) for _ in range(2 - dice)]
        fval = min(pool)
        fstr = (f'{original_msg.author.mention}, you rolled {dice}d'
                f'{sides if sides != 6 else ""}'
                f'{f" for a **{fitd_dict[fval]}**" if sides == 6 else ""}'
                f'{f"; roll for `{message}`" if message else ""}.')

        fstr += f' [`{dice}d`: **{fval}**; `{sorted(pool)[0]}`, '
        for x in sorted(pool)[1:]:
            fstr += f'~~`{x}`~~, '
        return fstr[:-2] + "]"


def __roll_hunter(original_msg: discord.Message, message: str, dice: int, desp_dice: int, sort_dice: bool):
    pool = [random.randint(1, 10) for _ in range(dice)]
    desp_pool = [random.randint(1, 10) for _ in range(desp_dice)]
    agg_pool = pool + desp_pool

    num_success = sum(agg_pool.count(i) for i in range(6, 11)) + math.floor(agg_pool.count(10) / 2) * 2
    min_val_desp = min(desp_pool) if desp_dice > 0 else -1

    fstr = f'{original_msg.author.mention}, you rolled {dice}d{f" | {desp_dice}d" if desp_dice > 0 else ""}'
    if num_success == 1:
        fstr += f' for **{num_success}** success'
    else:
        fstr += f' for **{num_success}** successes'

    if min_val_desp == 1:
        fstr += f' and you are in for a world of darkness'
    fstr += f'{f"; roll for `{message}`" if message else ""}.'

    fstr += f' [`{dice}d{f" | {desp_dice}d" if desp_dice > 0 else ""}`: '
    for x in (sorted(pool, reverse=True) if sort_dice else pool):
        fstr += f'`{x}`, '

    if desp_dice > 0:
        fstr = fstr[:-2] + ' | '
        for x in (sorted(desp_pool, reverse=True) if sort_dice else desp_pool):
            fstr += f'`{x}`, '

    return fstr[:-2] + "]"


async def roll_dice(message: discord.Message) -> bool:
    """Return true if roll pattern matched/do not continue"""
    try:
        roll_mode = __get_curr_roll_mode(message)
        if ((match := re.match(r'~(\d+)[dD](\d*)(!?)( ?-\d*)?( h| r| hr| rh)?($| ?#.*)', message.content)) and
                roll_mode == RollModeEnum.CAIN.value):
            dice = int(match.group(1).strip())
            sides = int(match.group(2).strip()) if len(match.group(2)) > 0 else 6
            sort_dice = '!' not in match.group(3)
            difficulty = match.group(5).strip() if match.group(5) else ""
            msg = match.group(6).strip().replace('#', '')
            if dice and dice > 100:
                await message.channel.send('in what world do you need to roll that many dice?')
                return True
            await message.channel.send(__roll_cain(message, msg, dice, 'r' in difficulty, 'h' in difficulty,
                                                   sort_dice, sides))
            return True
        elif ((match := re.match(r'~(\d+)[dD](!?)(\s?[dD]([0-9]))?($| ?#.*)', message.content)) and
              roll_mode == RollModeEnum.HUNTER.value):
            dice = int(match.group(1).strip())
            sort_dice = '!' not in match.group(2)
            desp_dice = int(match.group(4).strip()) if match.group(4) else 0
            msg = match.group(5).strip().replace('#', '')
            if dice and dice > 100:
                await message.channel.send('in what world do you need to roll that many dice?')
                return True
            await message.channel.send(__roll_hunter(message, msg, dice, desp_dice, sort_dice))
            return True
        elif ((match := re.match(r'~(-?)(\d+)[dD](\d*)(!?)( ?-\d*)?($| ?#.*)', message.content)) and
              (roll_mode == RollModeEnum.WILDSEAS.value or roll_mode == RollModeEnum.FITD.value)):
            dice = int(f'{match.group(1)}{match.group(2).strip()}')
            sides = int(match.group(3).strip()) if len(match.group(3)) > 0 else 6
            sort_dice = '!' not in match.group(4)
            cut = int(match.group(5).strip().replace('-', '')) if match.group(5) else 0
            msg = match.group(6).strip().replace('#', '')
            if dice and dice > 100:
                await message.channel.send('in what world do you need to roll that many dice?')
                return True
            if roll_mode == RollModeEnum.FITD.value:
                await message.channel.send(__roll_fitd(message, msg, dice, sort_dice, sides=sides))
            else:
                await message.channel.send(__roll_wildsea(message, msg, cut, dice, sort_dice, sides=sides))
            return True

        # continue executing other possible commands
        return False
    except ValueError as e:
        log.warning(f'ValueError when rolling: {e}')
        await message.channel.send("that doesnt look like a valid integer")
        return True


@bot.command(help="sends monobot's invite link (mono only)")
async def invite(ctx: discord.ext.commands.Context, *, msg=""):
    if ctx.message.author.id == int(OWNER_ID):
        await ctx.send(f'use this [invite](https://discord.com/oauth2/authorize?client_id=1208179071624941578'
                       f'&permissions=8&scope=bot) to add monobot to your server')
    else:
        await ctx.send('this method is only usable by mono')


bot.run(env.get("CLIENT_TOKEN"))
