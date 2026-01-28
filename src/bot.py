import asyncio
import io
import json
import math
import random
import re
import logging
import uuid

import dateparser
import discord
import pytz
import uwuipy
import feedparser
import easyocr

from datetime import datetime, timedelta
from dateutil import parser, tz
from PIL import Image
from discord.ext import commands
from discord.ext.commands import CommandOnCooldown, Context
from simpleeval import simple_eval, InvalidExpression

from const import PFP_SIZE, \
    MAINT_UPDATE_LOOP_TIMER, \
    TIMEZONES, \
    env, \
    COMMAND_PREFIX, \
    OWNER_ID, \
    BOT_ID, \
    MEAT_SHIELD_ID, \
    LEIKA_SMILER_ID, \
    EXPLODE_ID, \
    DEBUG, \
    LEIKA_PATTERN, \
    ROLL_HELP, \
    MONOBOT_WEBHOOK_NAME, \
    RollModeEnum, \
    NUM_TO_EMOTE, \
    HATE_WEIGHTS, \
    HATE_LIST, \
    FITD_DICT, \
    WILDSEA_DICT, \
    CAIN_DICT, \
    RISK_DICT, \
    CAIN_DICT_HARD, \
    EXPLODE_EMOTE, SOMEONE_EMOTE

log = logging.getLogger('MonoBot')
logging.basicConfig(format='%(asctime)s:%(name)s:%(levelname)s:%(funcName)s:%(message)s',
                    filename='run.log',
                    encoding='utf-8',
                    level=logging.INFO)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.AutoShardedBot(command_prefix='', intents=intents, help_command=None)

alarms = {}
webhook_cache = {}
leika_privilege = True

# TODO: Setup sqlite for data
data = {
    'maint': {
        # curr maint: steam post title str
        # from time: str
        # to time: str
        # date: str
    },
    'roll mode': {
        # guild id:
        #    server: mode str
        #    category:
        #        channel id: mode str
    },
    'reminders': {
        # reminder id:
        #   original channel id: int
        #   original message id: int
        #   posix timestamp: float
        #   author id: int
        #   message: str
    },
    'timezones': {
        # user id: timezone str
    },
    'react roles': {
        # server id:
        #   message:
        #     id: int message id of react role msg
        #     channel: int channel id of react role msg
        #     link: str link to react role msg
        #   roles: dict of roles in order on rr msg
        #     emote id:
        #       role id: role id int
        #       emote name: str or '' if emote is non-custom
        #       caption: caption str
    }
}

data_keys = data.keys()

try:
    with open('data.json', 'r') as file:
        fetched_data = json.load(file)
    for k in data_keys:
        if k not in fetched_data:
            fetched_data[k] = {}
    data = fetched_data
except Exception as e:
    log.warning(f'Exception when loading data, resetting: {e}')
    with open('data.json', 'w') as file:
        json.dump(data, file)

uwu_factory = uwuipy.Uwuipy(face_chance=.075)

if not DEBUG:
    ocr_reader = easyocr.Reader(['en'])
    rss_url = 'https://store.steampowered.com/feeds/news/app/1973530/'


@bot.event
async def on_ready():
    log.info(f'{bot.user} has connected to Discord!')
    activity = discord.Activity(type=discord.ActivityType.playing, name="actual suffering")
    await bot.change_presence(activity=activity)

    if not DEBUG:
        asyncio.create_task(__headless_maint_update())

        bad_reminders = []
        for reminder_id, reminder in data['reminders'].items():
            try:
                channel = bot.get_channel(int(reminder['channel id']))
                if not channel:
                    channel = await bot.fetch_channel(int(reminder['channel id']))

                msg = await channel.fetch_message(int(reminder['message id']))

                author = channel.guild.get_member(int(reminder['author id']))
                if not author:
                    author = await bot.fetch_user(int(reminder['author id']))

                alarms[str(reminder_id)] = asyncio.create_task(
                    __reminder_task(reminder_id,
                                    msg,
                                    datetime.fromtimestamp(reminder['timestamp']).astimezone(pytz.timezone(
                                        data['timezones'][str(reminder['author id'])])),
                                    author,
                                    reminder['alarm message'])
                )
            except Exception as e:
                bad_reminders.append(str(reminder_id))
                log.error(e)

        for k in bad_reminders:
            del data['reminders'][k]

        with open('data.json', 'w') as file:
            json.dump(data, file)


@bot.event
async def on_command_error(ctx, error):
    log.error(f'command error: {error}')
    if isinstance(error, CommandOnCooldown):
        await ctx.reply(f'you must wait before using that command again {EXPLODE_EMOTE}',
                        mention_author=False)


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

    await process_message(message)


async def process_message(message: discord.Message):
    await __slop_spotted(message)

    if not leika_privilege:
        await __leika_filter(message)


@bot.event
async def on_raw_reaction_add(event: discord.RawReactionActionEvent):
    if event.user_id == int(BOT_ID):
        return

    if not leika_privilege:
        if await __process_reaction_add_leika_emote(event):
            return

    await __process_reaction_add_react_roles(event)


@bot.event
async def on_raw_reaction_remove(event: discord.RawReactionActionEvent):
    if event.user_id == int(BOT_ID):
        return

    react_roles = data['react roles']
    if str(event.guild_id) not in react_roles or 'message' not in react_roles[str(event.guild_id)]:
        return

    guild_rr = react_roles[str(event.guild_id)]
    if event.message_id == guild_rr['message']['id']:
        member, role = await __get_member_and_role(event.guild_id,
                                                   event.user_id,
                                                   int(guild_rr['roles']
                                                       [str(event.emoji.id) if event.emoji.id else event.emoji.name][
                                                           'role id']))
        await member.remove_roles(role, atomic=True)


@bot.event
async def on_guild_role_delete(role: discord.Role):
    guild = role.guild
    guild_id = str(guild.id)

    if guild_id in data['react roles'] and 'message' in data['react roles'][guild_id]:
        guild_rr = data['react roles'][guild_id]
        rr_dict = guild_rr['roles']

        try:
            channel = guild.get_channel(guild_rr['message']['channel'])
            if not channel:
                channel = await guild.fetch_channel(guild_rr['message']['channel'])
            rr_msg = await channel.fetch_message(guild_rr['message']['id'])
        except discord.NotFound:
            log.debug('role deleted, but no rr msg')
            return

        for emote_id, vals in rr_dict.items():
            if vals['role id'] == role.id:
                del rr_dict[emote_id]
                reaction_emote = guild.get_emoji(int(emote_id)) if vals['emote name'] else emote_id
                await rr_msg.clear_reaction(reaction_emote)

                log.info(f'rr deleted - emote_id: {emote_id}, role_id: {vals["role id"]}')
                break

        await rr_msg.edit(content=__create_rr_msg(rr_dict))

        with open('data.json', 'w') as file:
            json.dump(data, file)


@bot.command(help='sends this message', usage=['help', 'help CMD'])
async def help(ctx: Context):
    cmd = ctx.message.content.split()
    if len(cmd) <= 1:
        help_message = ''
        for command in sorted(bot.commands, key=lambda c: c.name):
            help_message += f"**{COMMAND_PREFIX}{command.name}**: {command.help or 'no description provided'}\n"
        help_message += (f'`or you can {COMMAND_PREFIX}help CMD to learn more about a specific command or '
                         f'{COMMAND_PREFIX}help roll to learn rolling syntax`')
        await ctx.reply(help_message, mention_author=False)
        return

    cmd_name = cmd[1].strip()
    if cmd_name == 'roll':
        await ctx.reply(ROLL_HELP, mention_author=False)
    elif cmd_name in bot.all_commands:
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

        await ctx.reply(help_msg, mention_author=False)
    else:
        await ctx.reply(f'command "{cmd_name}" not found', mention_author=False)


@bot.command(usage=['leika'],
             help='toggle leika privileges')
async def leika(ctx: commands.Context, *, msg=''):
    global leika_privilege
    leika_privilege = not leika_privilege
    if leika_privilege:
        await ctx.send('your leika privileges are given')
    else:
        await ctx.send('your leika privileges are TAKEN AWAY')


async def __slop_spotted(message: discord.Message):
    if 'slop' in message.content and random.random() < 0.025:
        await message.reply(f'SLOP SPOTTED {EXPLODE_EMOTE} {EXPLODE_EMOTE} {EXPLODE_EMOTE} {EXPLODE_EMOTE} {EXPLODE_EMOTE} {EXPLODE_EMOTE} {EXPLODE_EMOTE} {EXPLODE_EMOTE} {EXPLODE_EMOTE} {EXPLODE_EMOTE}')


async def __leika_filter(message: discord.Message) -> bool:
    """remove leika smile for only nugget, returns true if a message is edited"""
    if message.author.id == int(LEIKA_SMILER_ID) and (
            cleaned_msg := re.sub(LEIKA_PATTERN, '', message.content)
    ) != message.content:
        if len(cleaned_msg) > 0:
            await __say_with_webhook(cleaned_msg,
                                     message.author.display_name,
                                     message.author.avatar.url,
                                     message.channel)
        await message.delete()
        return True
    return False


async def __process_reaction_add_leika_emote(event: discord.RawReactionActionEvent) -> bool:
    """if an emote is removed, returns true"""
    if event.user_id == int(LEIKA_SMILER_ID) and re.match(LEIKA_PATTERN, str(event.emoji)):
        channel = bot.get_channel(event.channel_id)
        message = await channel.fetch_message(event.message_id)
        user = await bot.fetch_user(event.user_id)
        await message.remove_reaction(event.emoji, user)
        await message.add_reaction(SOMEONE_EMOTE)
        return True
    return False


async def __process_reaction_add_react_roles(event: discord.RawReactionActionEvent):
    react_roles = data['react roles']
    if str(event.guild_id) not in react_roles or 'message' not in react_roles[str(event.guild_id)]:
        return

    guild_rr = react_roles[str(event.guild_id)]
    if event.message_id == guild_rr['message']['id']:
        member, role = await __get_member_and_role(event.guild_id,
                                                   event.user_id,
                                                   int(guild_rr['roles']
                                                       [str(event.emoji.id) if event.emoji.id else event.emoji.name][
                                                           'role id']))
        await member.add_roles(role, atomic=True)


async def __say_with_webhook(content: str, username: str, avatar_url: str, channel: discord.TextChannel):
    webhook = await __get_webhook(channel)
    await webhook.send(
        content=content,
        username=username,
        avatar_url=avatar_url
    )


async def __get_webhook(channel: discord.TextChannel):
    if channel.id in webhook_cache:
        return webhook_cache[channel.id]

    webhooks = await channel.webhooks()
    for webhook in webhooks:
        if webhook.name == MONOBOT_WEBHOOK_NAME:
            webhook_cache[channel.id] = webhook
            return webhook

    webhook = await channel.create_webhook(name=MONOBOT_WEBHOOK_NAME)
    webhook_cache[channel.id] = webhook
    return webhook


async def __get_member_and_role(guild_id: int, member_id: int, role_id: int):
    guild = bot.get_guild(guild_id)
    if not guild:
        guild = await bot.fetch_guild(guild_id)

    member = guild.get_member(member_id)
    if not member:
        member = await guild.fetch_member(member_id)

    role = guild.get_role(role_id)
    if not role:
        role = await guild.fetch_role(role_id)

    return member, role


def __create_rr_msg(role_dict: dict):
    rr_msg = f'## React to this message for roles\n'
    if len(role_dict) == 0:
        rr_msg += (f'-# this server currently has no react roles, use `{COMMAND_PREFIX}react_role` to create roles, '
                   f'or `{COMMAND_PREFIX}help react_role` for help!')
    else:
        for emote_id, val in role_dict.items():
            role_emote = f'<:{val["emote name"]}:{emote_id}>' if val["emote name"] else f'{emote_id}'
            caption_txt = f'- {val["caption"]}' if val["caption"] else ''
            rr_msg += f'{role_emote} - <@&{val["role id"]}> {caption_txt}\n'

    return rr_msg


@bot.command(aliases=['rr'],
             usage=['react_role NAME # EMOTE', 'react_role NAME # EMOTE # CAPTION'],
             help='create a new react role that all members can add to themselves (requires manage roles permission)')
async def react_role(ctx: commands.Context, *, msg=''):
    if not ctx.author.guild_permissions.manage_roles and not f'{ctx.author.id}' == OWNER_ID:
        await ctx.reply(f"making new react roles can only be done by role managers & mono", mention_author=False)
        return

    guild_id = str(ctx.guild.id)
    data_rr = data['react roles']
    if guild_id in data_rr and 'message' in data_rr[guild_id]:
        try:
            guild_rr = data_rr[guild_id]
            channel = ctx.guild.get_channel(int(guild_rr['message']['channel']))
            if not channel:
                channel = await ctx.guild.fetch_channel(int(guild_rr['message']['channel']))
            rr_msg = await channel.fetch_message(int(guild_rr['message']['id']))
        except discord.NotFound:
            await ctx.reply(f'react role message not sent, use `{COMMAND_PREFIX}react_role_message here` in a '
                            f'channel to send', mention_author=False)
            return
    else:
        await ctx.reply(f'react role message not sent, use `{COMMAND_PREFIX}react_role_message here` in a '
                        f'channel to send',
                        mention_author=False)
        return

    split = msg.split('#')
    if len(split) < 2 or len(split) > 3 and re.match(r'.+#.+[#.+]?', msg):
        await ctx.reply('syntax: role name #role emote #optional caption', mention_author=False)
        return

    role_emote = split[1].strip()
    if ':' in role_emote:
        emote = role_emote.split(':')
        emote_name = emote[1]
        emote_id = emote[2][:-1]
        reaction_emote = ctx.guild.get_emoji(int(emote_id))
    else:
        emote_id = role_emote
        reaction_emote = role_emote
        emote_name = ''

    role_name = split[0].strip()
    role_caption = split[2].strip() if len(split) > 2 else ''

    if len(role_caption) > 200:
        await ctx.reply('caption too long, must be less than 200 characters', mention_author=False)
        return

    role_dict = data_rr[guild_id]['roles']
    if emote_id in role_dict:
        await ctx.reply('this emote is already being used by another react role!', mention_author=False)
        return

    try:
        role = await ctx.guild.create_role(reason='react role creation', name=role_name, mentionable=True)
    except discord.Forbidden:
        log.error('missing permission to create react role')
        await ctx.send(f"bot doesn't have permission to create roles!")
        return

    role_dict[emote_id] = {
        'role id': role.id,
        'emote name': emote_name,
        'caption': role_caption
    }
    with open('data.json', 'w') as file:
        json.dump(data, file)

    await rr_msg.edit(content=__create_rr_msg(role_dict))
    await rr_msg.add_reaction(reaction_emote)
    await ctx.reply(f'role <@&{role.id}> created', mention_author=False)
    log.info(f'role created - emote_id: {emote_id}, role_id: {role.id}, role_name: {role_name}')


@bot.command(aliases=['rrmsg'],
             usage=['react_role_message', 'react_role_message here'],
             help='links to the message where you can get your roles via reacting, or sends a new react role message '
                  '(sending requires manage roles permission)')
async def react_role_message(ctx: commands.Context, *, msg=''):
    guild_id = str(ctx.guild.id)

    data_rr = data['react roles']

    if guild_id in data_rr and 'message' in data_rr[guild_id]:
        try:
            guild_rr = data_rr[guild_id]
            channel = ctx.guild.get_channel(int(guild_rr['message']['channel']))
            if not channel:
                channel = await ctx.guild.fetch_channel(int(guild_rr['message']['channel']))
            await channel.fetch_message(int(guild_rr['message']['id']))
            rr_msg_exists = True
        except discord.NotFound:
            rr_msg_exists = False
    else:
        rr_msg_exists = False

    if not msg:
        if rr_msg_exists:
            await ctx.reply(data_rr[guild_id]['message']['link'], mention_author=False)
        else:
            await ctx.reply('no react roles are set up in this server!', mention_author=False)
        return
    elif msg != 'here':
        return

    if not ctx.author.guild_permissions.manage_roles and not f'{ctx.author.id}' == OWNER_ID:
        await ctx.reply(f"managing react role messages can only be done by role managers & mono", mention_author=False)
        return

    if rr_msg_exists and msg == 'here':
        await ctx.reply(f'this server already has a react role message, delete it to send another one: '
                        f'{data_rr[guild_id]["message"]["link"]}', mention_author=False)
        return

    if guild_id not in data['react roles']:
        data['react roles'][guild_id] = {
            'message': {},
            'roles': {}
        }
    data_rr_guild = data['react roles'][guild_id]

    msg = await ctx.send(__create_rr_msg(data_rr_guild['roles']))
    log.info(f'new rr message created: {msg.jump_url} in {msg.channel.name} ({msg.channel.id})')

    data_rr_guild['message'] = {
        'id': msg.id,
        'channel': msg.channel.id,
        'link': msg.jump_url
    }

    with open('data.json', 'w') as file:
        json.dump(data, file)


def __get_user_curr_time(user_id: int) -> datetime:
    return datetime.now(pytz.timezone(data['timezones'][str(user_id)]))


def __del_reminder(reminder_id: uuid.UUID):
    del alarms[str(reminder_id)]
    del data['reminders'][str(reminder_id)]
    with open('data.json', 'w') as file:
        json.dump(data, file)


async def __reminder_task(reminder_id: uuid.UUID,
                          msg: discord.Message,
                          timer: datetime,
                          author: discord.Member,
                          message: str):
    try:
        log.info(f'{reminder_id} - {timer} from {author.id}: {message}')

        time_left = (timer - __get_user_curr_time(author.id))
        if time_left.total_seconds() > 15:
            await asyncio.sleep(time_left.total_seconds())

            log.debug(f'{reminder_id} executing')
            if message:
                await msg.reply(f'{author.mention} - {message}')
            else:
                await msg.reply(f'{author.mention}')

        __del_reminder(reminder_id)
    except asyncio.CancelledError:
        # FIXME: This currently deletes tasks on bot shutdown as well
        log.debug(f'reminder {reminder_id} already cancelled')
        __del_reminder(reminder_id)
    except discord.errors.HTTPException:
        log.debug(f'reminder {reminder_id} already cancelled via deletion')
        __del_reminder(reminder_id)
    except Exception as e:
        __del_reminder(reminder_id)
        raise e


def __parse_timestamp(msg: str, user_id: int) -> datetime:
    if str(user_id) not in data['timezones']:
        data['timezones'][str(user_id)] = 'UTC'
        with open('data.json', 'w') as file:
            json.dump(data, file)

    parsed = dateparser.parse(msg)
    if not parsed.tzinfo:
        parsed = dateparser.parse(msg, settings={
            'TIMEZONE': data['timezones'][str(user_id)],
            'RETURN_AS_TIMEZONE_AWARE': True
        })
    return parsed


def __to_discord_timestamps(ts: datetime):
    return f'<t:{int(ts.timestamp())}> (<t:{int(ts.timestamp())}:R>)'


@bot.command(aliases=['reminder', 'remindme', 'alarm', 're'],
             help='set a reminder',
             usage=['remind TIME', 'remind TIME #MESSAGE'])
async def remind(ctx: commands.Context, *, msg=''):
    split_msg = re.split('#', msg)
    alarm_timestamp = __parse_timestamp(split_msg[0], ctx.author.id)

    if alarm_timestamp - __get_user_curr_time(ctx.author.id) > timedelta(days=90):
        await ctx.reply('cannot set reminders more than 90 days in the future!', mention_author=False)
        return

    reminder_id = uuid.uuid4()

    reminder_data = {
        'channel id': ctx.channel.id,
        'message id': ctx.message.id,
        'timestamp': alarm_timestamp.timestamp(),
        'author id': ctx.author.id,
        'alarm message': ''
    }

    alarm_message = ''
    if len(split_msg) >= 2:
        alarm_message = '#'.join(split_msg[1:])
        reminder_data['alarm message'] = alarm_message

    alarms[str(reminder_id)] = asyncio.create_task(__reminder_task(reminder_id,
                                                                   ctx.message,
                                                                   alarm_timestamp,
                                                                   ctx.author,
                                                                   alarm_message))
    data['reminders'][str(reminder_id)] = reminder_data

    await ctx.reply(f'added reminder for {__to_discord_timestamps(alarm_timestamp)}\nto cancel reminder, delete this message',
                    mention_author=False)
    with open('data.json', 'w') as file:
        json.dump(data, file)


@bot.command(aliases=['ts'],
             help='translate a time into a discord timestamp, '
                  'can also use relative timestamps like "in 2 days" or "tomorrow at 3pm"',
             usage=['timestamp TIME'])
async def timestamp(ctx: commands.Context, *, msg=''):
    parsed = __parse_timestamp(msg, ctx.author.id)
    if parsed:
        await ctx.reply(__to_discord_timestamps(parsed), mention_author=False)
    else:
        await ctx.reply('no timestamp in message!', mention_author=False)


@bot.command(aliases=['tz'],
             help="see your timezone in the bot's database or see a list of available timezones",
             usage=['timezone', 'timezone list', 'timezone TIMEZONE'])
async def timezone(ctx: commands.Context, *, msg=''):
    msg = msg.strip()
    user_id = str(ctx.author.id)

    if not msg:
        if user_id in data['timezones']:
            await ctx.reply(f'your timezone is: {data["timezones"][user_id]}', mention_author=False)
        else:
            await ctx.reply('no timezone found', mention_author=False)
        return

    if msg == 'list':
        await ctx.reply(', '.join(TIMEZONES), mention_author=False)
        return

    try:
        offset = int(msg)
    except ValueError:
        if msg in TIMEZONES:
            offset = msg
        else:
            await ctx.reply('invalid timezone, please give a timezone on the list')
            return

    data['timezones'][user_id] = offset
    with open('data.json', 'w') as file:
        json.dump(data, file)

    await ctx.reply('timezone changed!', mention_author=False)


def __maint_update(curr_news):
    date_str = curr_news.title.replace('Scheduled Update Notice', '')
    image_url = curr_news.summary.split('<img src="')[1].split('"')[0]
    detection = ocr_reader.readtext(image_url)

    detect_str = ''
    for txt in detection:
        detect_str += txt[1].strip() + ' '
    detect_str = detect_str.strip()

    time_strs = [w for w in detect_str.split('from') if '[AM]' in w][0]
    time_strs = time_strs.split('on')[0].split('through')

    from_time_str = time_strs[0].replace('[', '').replace(']', '')
    to_time_str = time_strs[1].replace('[', '').replace(']', '')

    data['maint']['curr maint'] = curr_news.title.strip()
    data['maint']['from time'] = from_time_str.strip()
    data['maint']['to time'] = to_time_str.strip()
    data['maint']['date'] = date_str.strip()
    with open('data.json', 'w') as file:
        json.dump(data, file)

    log.info('updating maint to: ' + str(data['maint']))


def __get_scheduled_update_news(entries):
    return [news for news in entries if
            'Scheduled Update Notice' in news.title and 'Error' not in news.title and 'Correction' not in news.title]


async def __headless_maint_update():
    await bot.wait_until_ready()

    log.debug(f'headless maint update loop start')

    while not bot.is_closed():
        feed = feedparser.parse(rss_url)
        if feed.bozo:
            log.error('failed to fetch steam news stream')
        else:
            update_news = __get_scheduled_update_news(feed.entries)

            curr_news = update_news[0]
            if 'curr maint' not in data['maint'] or data['maint']['curr maint'] != curr_news.title:
                log.info('cached maint news out of date, fetching and parsing online news headlessly...')
                __maint_update(curr_news)
                log.info('headlessly updated maint news')
            else:
                log.debug('cached maint up to date')

        await asyncio.sleep(MAINT_UPDATE_LOOP_TIMER)

    log.info(f'headless maint update loop close')


@bot.command(help='get time of Limbus maintenance')
async def maint(ctx: Context):
    if random.random() < 0.02:
        await ctx.reply('wouldnt you like to know, pisserboy?', mention_author=False)
        return

    feed = feedparser.parse(rss_url)
    if feed.bozo:
        await ctx.reply('failed to fetch steam news stream', mention_author=False)
        return

    update_news = __get_scheduled_update_news(feed.entries)
    if len(update_news) == 0:
        await ctx.reply('no recent scheduled updates found', mention_author=False)
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
        __maint_update(curr_news)
        date_str = data['maint']['date']
        from_time_str = data['maint']['from time']
        to_time_str = data['maint']['to time']

    from_time = parser.parse(date_str + ' ' + from_time_str).replace(tzinfo=tz.gettz('Asia/Seoul'))
    to_time = parser.parse(date_str + ' ' + to_time_str).replace(tzinfo=tz.gettz('Asia/Seoul'))

    now = int(datetime.now().timestamp())
    from_timestamp = int(from_time.timestamp())
    to_timestamp = int(to_time.timestamp())
    if now < from_timestamp:
        await ctx.reply(f'the next maintenance begins <t:{from_timestamp}:R> at <t:{from_timestamp}> and ends at '
                        f'<t:{to_timestamp}>', mention_author=False)
    elif from_timestamp <= now < to_timestamp:
        await ctx.reply(f'the current maintenance ends <t:{to_timestamp}:R> at <t:{to_timestamp}>',
                        mention_author=False)
    else:
        await ctx.reply(f'the last maintenance ended <t:{to_timestamp}:R> at <t:{to_timestamp}>', mention_author=False)


@bot.command(help='chooses from list of comma-separated choices', usage=['choose CHOICE, CHOICE, CHOICE, ...'])
async def choose(ctx: Context, *, msg=''):
    split = [x.strip() for x in ctx.message.content[7:].split(',')]
    if len(split) == 0:
        await ctx.reply("you'll need to give me a list of comma-separated choices for me to choose from",
                        mention_author=False)
    else:
        await ctx.reply(f'{ctx.message.author.mention}, i choose `{random.choice(split)}` for you',
                        mention_author=False)


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


async def __remove_local_roll_mode(ctx: Context):
    try:
        del data['roll mode'][f'{ctx.guild.id}']['category'][f'{ctx.channel.category.id}']
        await ctx.send('removing local rolling mode...')
    except KeyError:
        await ctx.reply("local rolling mode doesn't exist!", mention_author=False)


@bot.command(help='set rolling mode of the server/category (requires channel manager permission)',
             usage=['mode MODE', 'mode local MODE'])
async def mode(ctx: Context, *, msg=''):
    split = ctx.message.content.split(' ')
    if len(split) == 1:
        if f'{ctx.guild.id}' in data['roll mode']:
            send_str = f'current server rolling mode: "{data["roll mode"][str(ctx.guild.id)]["server"]}"'
            if f'{ctx.channel.category.id}' in data['roll mode'][str(ctx.guild.id)]['category']:
                send_str += f'\ncurrent category rolling mode: "{data["roll mode"][str(ctx.guild.id)]["category"][str(ctx.channel.category.id)]}"'
            await ctx.reply(send_str, mention_author=False)
        else:
            await __default_mode(ctx.message)
        return

    if not ctx.author.guild_permissions.manage_channels and not f'{ctx.author.id}' == OWNER_ID:
        await ctx.reply(f'setting the rolling mode of this server can only be done by channel managers & mono',
                        mention_author=False)
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
        await ctx.reply(f'mode does not exist!\nallowed rolling modes: *{", ".join(sorted(modes))}*',
                        mention_author=False)
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
            await ctx.reply(f'successfully set rolling mode of this server to "{mode}"', mention_author=False)
        else:
            await ctx.reply(f'successfully set rolling mode of this category to "{mode}"', mention_author=False)


@bot.command(help='good advice')
async def touchgrass(ctx: Context, *, msg=''):
    await ctx.reply('https://hard-drive.net/hd/video-games/top-10-grasses-to-go-touch/', mention_author=False)


@bot.command(help='uwu someone by replying to them or uwu your own message', usage=['uwu', 'uwu MSG'])
async def uwu(ctx: Context, *, msg=''):
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
    await message.reply(f'{message.author.mention} {random.choice(choice)}', mention_author=False)


@bot.command(aliases=['p'],
             help='sets up a poll, add options by passing a list of comma-separated choices (limit of 9)',
             usage=['poll CHOICE, CHOICE, CHOICE, ...'])
async def poll(ctx: Context, *, msg=''):
    options = [s.strip() for s in msg.strip().split(',') if len(s) > 0]
    if len(options) > 9:
        await ctx.reply('do you really need that many options in a poll?', mention_author=False)
        return
    if len(options) < 1:
        await ctx.reply('you gonna put any options in that poll? (ps. you can add them through a comma-separated list)',
                        mention_author=False)
        return
    if len(options) == 1:
        await ctx.reply(
            'a poll with only one option is kinda boring isn\'t it? (ps. you can add more through a comma-separated list)'
        )
        return

    message = ''
    for i in range(len(options)):
        message += f'{NUM_TO_EMOTE[i + 1]}: {options[i]}\n'
    sent_msg = await ctx.reply(message, mention_author=False)

    for i in range(len(options)):
        await sent_msg.add_reaction(f'{NUM_TO_EMOTE[i + 1]}')


@bot.command(aliases=['qp'], help='sets up a yes/no poll')
async def quickpoll(ctx: Context, *, msg=''):
    await ctx.message.add_reaction("✅")
    await ctx.message.add_reaction("❌")


@bot.command(help='reply/mention someone to make them a wee bit yellow', usage=['pee', 'pee @USER'])
async def pee(ctx: Context, *, msg=''):
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
        await ctx.reply(file=discord.File(make_pee(), filename='pee.png'), mention_author=False)
    elif ctx.message.reference:
        ref = await ctx.fetch_message(ctx.message.reference.message_id)
        author_pfp = await ref.author.display_avatar.with_static_format('png').read()
        pfp = Image.open(io.BytesIO(author_pfp)).resize(PFP_SIZE)
        await ctx.reply(file=discord.File(make_pee(), filename='pee.png'), mention_author=False)
    else:
        author_pfp = await ctx.author.display_avatar.with_static_format('png').read()
        pfp = Image.open(io.BytesIO(author_pfp)).resize(PFP_SIZE)
        await ctx.reply(file=discord.File(make_pee(), filename='pee.png'), mention_author=False)


@bot.command(help='mention mono')
@commands.cooldown(5, 300)
async def a(ctx: Context, *, msg=''):
    await ctx.reply(f'<@{OWNER_ID}>', mention_author=False)


@bot.command(help='give yourself a gun, as a treat')
async def gun(ctx: Context, *, msg=''):
    author_pfp = await ctx.author.display_avatar.with_static_format('png').read()
    gun_image = Image.open('./img/gun.png').resize((150, 150))
    pfp = Image.open(io.BytesIO(author_pfp)).resize(PFP_SIZE)
    pfp.paste(gun_image, (90, 50), gun_image)

    pfp_bytes = io.BytesIO()
    pfp.save(pfp_bytes, format="PNG")
    pfp_bytes.seek(0)
    await ctx.reply(file=discord.File(pfp_bytes, filename='gun.png'), mention_author=False)


@bot.command(help='show the bot a bit of love (some exceptions apply)')
async def love(ctx: Context, *, msg=''):
    if ctx.message.author.id == int(EXPLODE_ID):
        if random.random() < 0.05:
            love_list = ['💕', '💝', '💖']
            await ctx.message.add_reaction(random.choice(love_list))
        else:
            await ctx.message.add_reaction('%s' % EXPLODE_EMOTE)

    elif ctx.message.author.id == int(MEAT_SHIELD_ID):
        if random.random() < 0.5:
            await ctx.message.add_reaction(EXPLODE_EMOTE)
        else:
            love_list = ['⭐', '✨', '💕', '💝', '💖']
            for lv in love_list:
                await ctx.message.add_reaction(random.choice(lv))

    else:
        if random.random() < 0.05:
            await ctx.message.add_reaction(EXPLODE_EMOTE)
        else:
            love_list = ['💕', '💝', '💖']
            await ctx.message.add_reaction(random.choice(love_list))


@bot.command(help='reply/mention someone to blow them up, or send some nyukes',
             usage=['explode', 'explode @USER', 'explode NUM'])
async def explode(ctx: Context, *, msg=""):
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
                    await bot.fetch_user(int(MEAT_SHIELD_ID))).display_avatar.with_static_format('png').read()
                message = 'MEAT SHIELD GO'
            else:
                author_pfp = await ctx.message.mentions[0].display_avatar.with_static_format('png').read()
        else:
            ref = await ctx.fetch_message(ctx.message.reference.message_id)
            if ref.author.id == int(OWNER_ID):
                author_pfp = await (
                    await bot.fetch_user(int(MEAT_SHIELD_ID))).display_avatar.with_static_format('png').read()
                message = 'MEAT SHIELD GO'
            else:
                author_pfp = await ref.author.display_avatar.with_static_format('png').read()
        pfp = Image.open(io.BytesIO(author_pfp)).resize(PFP_SIZE)
        await ctx.reply(message, file=discord.File(make_explode(pfp), filename='boom.gif'), mention_author=False)
    else:
        count = 1
        if len(msg) >= 1:
            count = int(msg)

        if count > 30:
            await ctx.reply('i do not permit you to blow up the server', mention_author=False)
            count = 30
        message = ''
        limit = 0
        for _ in range(count):
            message += f'{EXPLODE_EMOTE} '
            limit += 1
            if limit >= 30:
                await ctx.reply(message, mention_author=False)
                message = ''
                limit = 0

        if len(message) > 0:
            await ctx.reply(message, mention_author=False)


def __has_duplicates(lst):
    counts = {}
    for num in lst:
        if num in counts:
            return True
        counts[num] = 1
    return False


def __roll_hate(fstr, fval, pool, roll_mode):
    fstr += f' [`10d`: **{fval}**; '
    for x in pool:
        fstr += f'`{x}`, '
    fstr = fstr[:-2] + "]"
    if fval <= 3:
        c = random.choice(HATE_LIST)
        fstr += c
    elif roll_mode != RollModeEnum.CAIN.value:
        if fval == 6:
            fstr += '\ndamn...'
    else:
        if fval > 3:
            fstr += '\ndamn...'
    return fstr


def __hate_wildseas(ctx: Context, pool, fval):
    twist = __has_duplicates(pool)
    if not twist:
        fstr = f'{ctx.message.author.mention}, you rolled 10d for a **{WILDSEA_DICT[fval]}**.'
    else:
        fstr = f'{ctx.message.author.mention}, you rolled 10d for a **Twist** and a **{WILDSEA_DICT[fval]}**.'
    return __roll_hate(fstr, fval, pool, RollModeEnum.WILDSEAS.value)


def __hate_fitd(ctx: Context, pool, fval):
    crit = pool.count(6) >= 2
    if not crit:
        fstr = f'{ctx.message.author.mention}, you rolled 10d for a **{FITD_DICT[fval]}**.'
    else:
        fstr = f'{ctx.message.author.mention}, you rolled 10d for a **Critical Success**.'
    return __roll_hate(fstr, fval, pool, RollModeEnum.FITD.value)


def __hate_cain(ctx: Context, pool, fval):
    num_success = len([x for x in pool if x > 3])
    if num_success <= 1:
        fstr = f'{ctx.message.author.mention}, you rolled 10d for a **{CAIN_DICT[fval]}**.'
    else:
        fstr = f'{ctx.message.author.mention}, you rolled 10d for {num_success} **Successes**.'
    return __roll_hate(fstr, fval, pool, RollModeEnum.CAIN.value)


@bot.command(help='let the bot vent some rage, may or may not improve your rolls')
async def hate(ctx: Context, *, msg=""):
    pool = [random.choices(range(1, 7), weights=HATE_WEIGHTS)[0] for _ in range(10)]
    pool = sorted(pool, reverse=True)
    fval = max(pool)

    roll_mode = __get_curr_roll_mode(ctx.message)
    if roll_mode == RollModeEnum.WILDSEAS.value:
        await ctx.reply(__hate_wildseas(ctx, pool, fval), mention_author=False)
    elif roll_mode == RollModeEnum.FITD.value:
        await ctx.reply(__hate_fitd(ctx, pool, fval), mention_author=False)
    elif roll_mode == RollModeEnum.CAIN.value:
        await ctx.reply(__hate_cain(ctx, pool, fval), mention_author=False)
    else:
        await ctx.reply("invalid roll mode: " + roll_mode, mention_author=False)


def __roll_risk_msg():
    roll = random.randint(1, 6)
    return """
```ansi
[1mRisk[0m: You rolled {roll} for {risk}
```""".format(roll=roll, risk=RISK_DICT[roll])


@bot.command(aliases=['r'], help='roll risk (only usable with Cain)')
async def risk(ctx: Context, *, msg=""):
    if __get_curr_roll_mode(ctx.message) == RollModeEnum.CAIN.value:
        await ctx.reply(__roll_risk_msg(), mention_author=False)
    else:
        await ctx.reply('only available for "cain" roll mode', mention_author=False)


def __roll_cain(original_msg: discord.Message, message: str, dice: int, is_risky: bool, is_hard: bool, sort_dice: bool,
                sides: int = 6, mods: str = ''):
    if sides != 6:
        return __roll_custom(original_msg, message, dice, sort_dice, sides=sides, is_risky=is_risky, mods=mods)

    if dice > 0:
        pool = [random.randint(1, 6) for _ in range(dice)]
        fval = max(pool)

        if is_hard:
            num_success = pool.count(6)
        else:
            num_success = sum(pool.count(i) for i in range(4, 7))

        fstr = f'{original_msg.author.mention}, you rolled {dice}d'
        if is_hard:
            fstr += ' with *hard*'
        if num_success <= 1:
            fstr += f' for a **{CAIN_DICT_HARD[fval] if is_hard else CAIN_DICT[fval]}**'
        else:
            fstr += f' for {num_success} **Successes**'
        fstr += f'{f"; roll for `{message}`" if message else ""}.'

        fstr += f' [`{dice}d`: **{fval}**; '
        for x in (sorted(pool, reverse=True) if sort_dice else pool):
            fstr += f'`{x}`, '
    else:
        pool = [random.randint(1, sides) for _ in range(2 - dice)]
        fval = min(pool)
        fstr = f'{original_msg.author.mention}, you rolled {dice}d'
        if is_hard:
            fstr += ' with *hard*'
        fstr += f' for a **{CAIN_DICT_HARD[fval] if is_hard else CAIN_DICT[fval]}**'
        fstr += f'{f"; roll for `{message}`" if message else ""}.'
        fstr += f' [`{dice}d`: **{fval}**; `{sorted(pool)[0]}`, '
        for x in sorted(pool)[1:]:
            fstr += f'~~`{x}`~~, '

    fstr = fstr[:-2] + "]"
    if is_risky:
        fstr += __roll_risk_msg()
    return fstr


def __roll_wildsea(original_msg: discord.Message,
                   message: str,
                   cut: int,
                   dice: int,
                   sort_dice: bool,
                   sides: int = 6,
                   mods: str = ''):
    if sides != 6:
        return __roll_custom(original_msg, message, dice, sort_dice, sides=sides, mods=mods)

    if dice - cut <= 0:
        pool = [random.randint(1, 6)]
        fval = max(pool)
        fstr = (f'{original_msg.author.mention}, you rolled {dice}d'
                f' for a **{WILDSEA_DICT[fval] if fval < 6 else WILDSEA_DICT[fval - 1]}**'
                f'{f"; roll for `{message}`" if message else ""}.')
        fstr += f' [`{dice}d`: **{fval}**; '
        for x in (sorted(pool, reverse=True) if sort_dice else pool):
            fstr += f'`{x}`, '
        fstr = fstr[:-2] + "]"
        fstr += """```ansi
[1mThis roll will have greater consequences and/or worse positioning[0m```"""
        return fstr

    if dice > 0:
        pool = [random.randint(1, 6) for _ in range(dice)]

        if cut > 0:
            pool = sorted(pool, reverse=True)
            fval = pool[cut]
            twist = __has_duplicates(pool[cut:])

            if not twist:
                fstr = (f'{original_msg.author.mention}, you rolled {dice}d'
                        f' with cut of {cut} for a **{WILDSEA_DICT[fval]}**'
                        f'{f"; roll for `{message}`" if message else ""}.')
            else:
                fstr = (f'{original_msg.author.mention}, you rolled {dice}d'
                        f'{f" with cut of {cut} for a **Twist** and a **{WILDSEA_DICT[fval]}**"}'
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
                        f' for a **{WILDSEA_DICT[fval]}**'
                        f'{f"; roll for `{message}`" if message else ""}.')
            else:
                fstr = (f'{original_msg.author.mention}, you rolled {dice}d'
                        f' for a **Twist** and a **{WILDSEA_DICT[fval]}**'
                        f'{f"; roll for `{message}`" if message else ""}.')

            fstr += f' [`{dice}d`: **{fval}**; '
            for x in (sorted(pool, reverse=True) if sort_dice else pool):
                fstr += f'`{x}`, '
            return fstr[:-2] + "]"
    else:
        pool = [random.randint(1, 6) for _ in range(2 - dice)]
        fval = min(pool)
        fstr = (f'{original_msg.author.mention}, you rolled {dice}d'
                f' for a **{WILDSEA_DICT[fval]}**'
                f'{f"; roll for `{message}`" if message else ""}.')

        fstr += f' [`{dice}d`: **{fval}**; `{sorted(pool)[0]}`, '
        for x in sorted(pool)[1:]:
            fstr += f'~~`{x}`~~, '
        return fstr[:-2] + "]"


def __roll_fitd(original_msg: discord.Message,
                message: str,
                dice: int,
                sort_dice: bool,
                sides: int = 6,
                mods: str = ''):
    if sides != 6:
        return __roll_custom(original_msg, message, dice, sort_dice, sides=sides, mods=mods)

    if dice > 0:
        pool = [random.randint(1, 6) for _ in range(dice)]
        fval = max(pool)

        crit = pool.count(6) >= 2
        if not crit:
            fstr = (f'{original_msg.author.mention}, you rolled {dice}d'
                    f' for a **{FITD_DICT[fval]}**'
                    f'{f"; roll for `{message}`" if message else ""}.')
        else:
            fstr = (f'{original_msg.author.mention}, you rolled {dice}d'
                    f' for a **Critical Success**'
                    f'{f"; roll for `{message}`" if message else ""}.')

        fstr += f' [`{dice}d`: **{fval}**; '
        for x in (sorted(pool, reverse=True) if sort_dice else pool):
            fstr += f'`{x}`, '
        return fstr[:-2] + "]"
    else:
        pool = [random.randint(1, 6) for _ in range(2 - dice)]
        fval = min(pool)
        fstr = (f'{original_msg.author.mention}, you rolled {dice}d'
                f' for a **{FITD_DICT[fval]}**'
                f'{f"; roll for `{message}`" if message else ""}.')

        fstr += f' [`{dice}d`: **{fval}**; `{sorted(pool)[0]}`, '
        for x in sorted(pool)[1:]:
            fstr += f'~~`{x}`~~, '
        return fstr[:-2] + "]"


def __roll_hunter(original_msg: discord.Message, message: str, dice: int, desp_dice: int, sort_dice: bool,
                  sides: int = 10, mods: str = ''):
    if sides != 10:
        return __roll_custom(original_msg, message, dice, sort_dice, sides=sides, mods=mods)

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


def __roll_persona(original_msg: discord.Message,
                   message: str,
                   dice: int,
                   sort_dice: bool,
                   sides: int = 10,
                   mods: str = ''):
    if sides != 10:
        return __roll_custom(original_msg, message, dice, sort_dice, sides=sides, mods=mods)

    pool = [random.randint(1, 10) for _ in range(dice)]
    counts = [0] * sides
    for i in range(sides):
        counts[i] = pool.count(i + 1)

    fstr = f'{original_msg.author.mention}, you rolled {dice}d'
    fstr += f'{f"; roll for `{message}`" if message else ""}.'

    fstr += f' [`{dice}d`: '
    for x in (sorted(pool, reverse=True) if sort_dice else pool):
        fstr += f'`{x}`, '

    fstr = fstr[:-2] + f']\nSets: ['
    has_set = False
    for i, n in enumerate(counts):
        if n > 1:
            has_set = True
            fstr += f'**{n}** x`{i + 1}`, '
    fstr = (fstr[:-2] if has_set else f'{fstr} ¯\\\\\_(ツ)_/¯ ') + f']\nLoose dice: ['

    for i, n in enumerate(counts):
        if n == 1:
            fstr += f'`{i + 1}`, '
    return fstr[:-2] + "]"


def __roll_custom(original_msg: discord.Message,
                  message: str,
                  dice: int,
                  sort_dice: bool,
                  sides: int,
                  is_risky=None,
                  mods: str = ''):
    try:
        modifier = simple_eval(mods)
    except InvalidExpression:
        modifier = 0

    fstr = (f'{original_msg.author.mention}, you rolled {dice}d{sides}'
            f'{f"; roll for `{message}`" if message else ""}.')
    if dice > 0:
        pool = [random.randint(1, sides) for _ in range(dice)]
        fval = max(pool)
        fsum = sum(pool)
        equation = f'{fsum}{mods} = ' if modifier else ''
        fstr += f' [`{dice}d{sides}`: **{fval}** | {equation}**{fsum + modifier}**; '
        for x in (sorted(pool, reverse=True) if sort_dice else pool):
            fstr += f'`{x}`, '
    else:
        pool = [random.randint(1, sides) for _ in range(2 - dice)]
        fval = min(pool)
        fsum = min(pool)
        equation = f'{fsum}{mods} = ' if modifier else ''
        fstr += f' [`{dice}d{sides}`: **{fval}** | {equation}**{fsum + modifier}**; `{sorted(pool)[0]}`, '
        for x in sorted(pool)[1:]:
            fstr += f'~~`{x}`~~, '

    fstr = fstr[:-2] + "]"
    if is_risky:
        fstr += __roll_risk_msg()
    return fstr


@bot.command(usage=['lethal TARGET', 'lethal TARGET MODIFYING_EQUATION'],
             help="roll to see if an action is lethal, or how much damage it'll do (only usable with Delta Green)")
async def lethal(ctx: Context, *, msg=''):
    if __get_curr_roll_mode(ctx.message) != RollModeEnum.DG.value:
        await ctx.reply('only available for "deltagreen" roll mode', mention_author=False)
        return

    split = msg.strip().split('#')
    message = ''.join(split[1:]) if len(split) > 1 else ''

    try:
        target = simple_eval(split[0])
    except Exception:
        await ctx.reply('incorrect syntax!', mention_author=False)
        return

    fval = random.randint(1, 100)
    if fval == 100:
        d1, d2 = 10, 10
    else:
        d1 = fval // 10
        d2 = fval % 10
    dmg = d1 + d2

    fstr = f'{ctx.author.mention}, your target was `{target}` and you rolled **{fval}** for '
    if fval <= target:
        fstr += f'__**DEATH**__'
    else:
        fstr += f'**{dmg}** damage'
    fstr += f'{f"; roll for `{message}`" if message else ""}.'
    await ctx.reply(fstr, mention_author=False)


@bot.command(aliases=['sk'],
             usage=[
                 'skill TARGET',
                 'skill TARGET MODIFYING_EQUATION',
                 'skill NUM_DICE**d**NUM_SIDES',
                 'skill NUM_DICE**d**NUM_SIDES MODIFYING_EQUATION',
             ],
             help='roll a skill check, can append #MSG at the very end to attach a message to the roll (only usable with Delta Green)')
async def skill(ctx: Context, *, msg=''):
    if __get_curr_roll_mode(ctx.message) != RollModeEnum.DG.value:
        await ctx.reply('only available for "deltagreen" roll mode', mention_author=False)
        return

    split = msg.strip().split('#')
    message = ''.join(split[1:]) if len(split) > 1 else ''

    try:
        target = simple_eval(split[0])
    except Exception:
        await ctx.reply('incorrect syntax!', mention_author=False)
        return

    fval = random.randint(1, 100)
    d1 = fval // 10
    d2 = fval % 10
    crit = d1 == d2 or fval == 1 or fval == 100

    fstr = f'{ctx.author.mention}, your target was `{target}` and you rolled **{fval}** for '
    if fval > target:
        fstr += f'a **{"Failure" if not crit else "Fumble"}**'
    else:
        fstr += f'a **{"Success" if not crit else "Critical Success"}**'

    fstr += f'{f"; roll for `{message}`" if message else ""}.'
    await ctx.reply(fstr, mention_author=False)


async def roll_dice(message: discord.Message) -> bool:
    """Return true if roll pattern matched/do not continue"""
    try:
        roll_mode = __get_curr_roll_mode(message)
        if (roll_mode == RollModeEnum.CAIN.value and (
                match := re.match(fr'{COMMAND_PREFIX}(\d+)[dD](\d*)([\s\d|\+\-\*\/]*?)(!?)( ?-\d*)?( h| r| hr| rh)?($| ?#.*)',
                                  message.content)
        )):
            dice = int(match.group(1).strip())
            sides = int(match.group(2).strip()) if len(match.group(2)) > 0 else 6
            mods = match.group(3).strip()
            sort_dice = '!' not in match.group(4)
            difficulty = match.group(6).strip() if match.group(6) else ""
            msg = match.group(7).strip().replace('#', '')
            if dice and dice > 100:
                await message.reply('in what world do you need to roll that many dice?', mention_author=False)
                return True
            await message.reply(__roll_cain(message, msg, dice, 'r' in difficulty, 'h' in difficulty,
                                            sort_dice, sides, mods), mention_author=False)
            return True
        elif (roll_mode == RollModeEnum.HUNTER.value and (
                match := re.match(fr'{COMMAND_PREFIX}(\d+)[dD](\d*)([\s\d|\+\-\*\/]*?)(!?)(\s?[dD]([0-9]))?($| ?#.*)',
                                  message.content)
        )):
            dice = int(match.group(1).strip())
            sides = int(match.group(2).strip()) if len(match.group(2)) > 0 else 10
            mods = match.group(3).strip()
            sort_dice = '!' not in match.group(4)
            desp_dice = int(match.group(6).strip()) if match.group(6) else 0
            msg = match.group(7).strip().replace('#', '')
            if dice and dice > 100:
                await message.reply('in what world do you need to roll that many dice?', mention_author=False)
                return True
            await message.reply(__roll_hunter(message, msg, dice, desp_dice, sort_dice, sides, mods),
                                mention_author=False)
            return True
        elif (roll_mode == RollModeEnum.DG.value and (
                match := re.match(fr'{COMMAND_PREFIX}(\d+)[dD](\d*)([\s\d|\+\-\*\/]*?)(!?)($| ?#.*)',
                                  message.content)
        )):
            if not match.group(2):
                await message.reply('you must define number of sides for Delta Green!', mention_author=False)
                return True

            dice = int(match.group(1).strip())
            sides = int(match.group(2).strip())
            mods = match.group(3).strip()
            sort_dice = '!' not in match.group(4)
            msg = match.group(5).strip().replace('#', '')
            if dice and dice > 100:
                await message.reply('in what world do you need to roll that many dice?', mention_author=False)
                return True
            await message.reply(__roll_custom(message, msg, dice, sort_dice, sides=sides, mods=mods),
                                mention_author=False)
        elif ((roll_mode == RollModeEnum.WILDSEAS.value or
               roll_mode == RollModeEnum.FITD.value or
               roll_mode == RollModeEnum.PERSONA.value) and (
                      match := re.match(fr'{COMMAND_PREFIX}(-?)(\d+)[dD](\d*)([\s\d|\+\-\*\/]*?)(!?)( ?-\d*)?($| ?#.*)',
                                        message.content)
              )):
            dice = int(f'{match.group(1)}{match.group(2).strip()}')

            sides = int(match.group(3).strip()) if len(match.group(3)) > 0 else \
                (10 if roll_mode == RollModeEnum.PERSONA.value else 6)
            mods = match.group(4).strip()

            sort_dice = '!' not in match.group(5)
            cut = int(match.group(6).strip().replace('-', '')) if match.group(6) else 0
            msg = match.group(7).strip().replace('#', '')
            if dice and dice > 100:
                await message.reply('in what world do you need to roll that many dice?', mention_author=False)
                return True
            if roll_mode == RollModeEnum.FITD.value:
                await message.reply(__roll_fitd(message, msg, dice, sort_dice, sides=sides, mods=mods),
                                    mention_author=False)
            elif roll_mode == RollModeEnum.WILDSEAS.value:
                await message.reply(__roll_wildsea(message, msg, cut, dice, sort_dice, sides=sides, mods=mods),
                                    mention_author=False)
            else:
                await message.reply(__roll_persona(message, msg, dice, sort_dice, sides=sides, mods=mods),
                                    mention_author=False)
            return True

        # continue executing other possible commands
        return False
    except ValueError as e:
        log.warning(f'ValueError when rolling: {e}')
        await message.reply("that doesnt look like a valid integer", mention_author=False)
        return True


@bot.command(help="sends monobot's invite link (mono only)")
async def invite(ctx: Context, *, msg=""):
    if ctx.message.author.id == int(OWNER_ID):
        await ctx.reply(f'use this [invite](https://discord.com/oauth2/authorize?client_id=1208179071624941578'
                        f'&permissions=8&scope=bot) to add monobot to your server')
    else:
        await ctx.reply('this method is only usable by mono', mention_author=False)


bot.run(env.get("CLIENT_TOKEN"))
