import asyncio
import io
import json
import random
import re
from enum import Enum
from typing import Union

import dotenv
import discord

from uwuipy import uwuipy
from PIL import Image
from discord.ext import commands
from discord.ext.commands import CommandOnCooldown

stupid_fucking_pillar = False

PFP_SIZE = (200, 200)

env = dotenv.dotenv_values()
command_prefix = env.get('PREFIX')
owner_id = env.get('OWNER_ID')
bot_id = env.get('BOT_ID')
explode = int(env.get('EXPLODE'))
explode_more = int(env.get('EXPLODE_MORE'))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.AutoShardedBot(command_prefix='', intents=intents)

data = {}
with open('data.json', 'r') as file:
    data = json.load(file)

uwu = uwuipy(face_chance=.075)

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


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    activity = discord.Activity(type=discord.ActivityType.playing, name="actual suffering")
    await bot.change_presence(activity=activity)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, CommandOnCooldown):
        await ctx.send(f'<:Explode:1207534077838626836>')


@bot.event
async def on_message(ctx: discord.Message):
    if ctx.author.id == int(bot_id):
        return

    if ctx.content and ctx.content[0] == command_prefix:
        split_content = ctx.content[1:].lower().split("d")
        if data['roll mode'][f'{ctx.guild.id}'] == RollModeEnum.CAIN.value and re.match(
                r'~-?\d+[dD]!?( ?-\d*)?( h| r| hr| rh)?($| ?#.*)',
                ctx.content):
            newcontent = "~roll " + split_content[0]
            msg = ''
            if "#" in ctx.content:
                msg = "#" + ctx.content.split('#')[1].strip()
                difficulty = f' {ctx.content.split("d")[1].split("#")[0].strip()} '
            else:
                difficulty = ctx.content.split("d")[1]
                difficulty = difficulty.replace('!', ' !')
            ctx.content = newcontent + difficulty + msg
        elif re.match(r'~-?\d+[dD]!?( ?-\d*)?($| ?#.*)', ctx.content):
            newcontent = "~roll " + split_content[0]
            cut = ''
            msg = ''
            if "#" in ctx.content:
                msg = "#" + ctx.content.split('#')[1].strip()
                ctx.content = ctx.content.split('#')[0].strip()
            if "-" in ctx.content:
                cut = " -" + ctx.content.split('-')[1].strip()
            if len(split_content[1]) > 0 and split_content[1][0] == "!":
                newcontent = newcontent + " !"
            ctx.content = newcontent + cut + msg
        await bot.process_commands(ctx)
    elif stupid_fucking_pillar and ctx.content and (ctx.content[0] != 'f' and ctx.content[0] != 'F'):
        try:
            await ctx.delete()
        except Exception as e:
            print(e)


@bot.command(aliases=['~touchsonar'])
async def bot_touchsonar(ctx: discord.ext.commands.Context, *, msg=''):
    if not ctx.author.guild_permissions.administrator and not f'{ctx.author.id}' == owner_id:
        await ctx.send(f'turning on touch sonar can only be done by admins & mono')
        return

    global stupid_fucking_pillar
    stupid_fucking_pillar = not stupid_fucking_pillar
    await ctx.send('touch based sonar now enforced' if stupid_fucking_pillar else 'touch based sonar now optional')


@bot.command(aliases=['~choose'])
async def bot_choose(ctx: discord.ext.commands.Context, *, msg=''):
    split = [x.strip() for x in ctx.message.content[7:].split(',')]
    if len(split) == 0:
        await ctx.send("you'll need to give me a list of comma-separated choices for me to choose from")
    else:
        await ctx.send(f'{ctx.message.author.mention}, i choose `{random.choice(split)}` for you')


class RollModeEnum(Enum):
    WILDSEAS = "wildseas"
    FITD = "fitd"
    CAIN = "cain"


@bot.command(aliases=['~mode'])
async def bot_mode(ctx: discord.ext.commands.Context, *, msg=''):
    split = ctx.message.content.split(' ')
    if len(split) == 1:
        if f'{ctx.guild.id}' in data['roll mode']:
            await ctx.send(f'current server rolling mode: "{data["roll mode"][str(ctx.guild.id)]}"')
        else:
            data['roll mode'][f'{ctx.guild.id}'] = RollModeEnum.FITD.value
            with open('data.json', 'w') as file:
                json.dump(data, file)
            await ctx.send(f'server currently has no rolling mode, setting to "fitd" by default')
        return

    if not ctx.author.guild_permissions.administrator and not f'{ctx.author.id}' == owner_id:
        await ctx.send(f'setting the rolling mode of this server can only be done by admins & mono')
        return

    mode = split[1]
    modes = {e.value for e in RollModeEnum}
    if mode not in modes:
        await ctx.send(f'mode does not exist!\nallowed rolling modes: *{", ".join(sorted(modes))}*')
    else:
        data['roll mode'][f'{ctx.guild.id}'] = mode
        with open('data.json', 'w') as file:
            json.dump(data, file)
        await ctx.send(f'successfully set rolling mode of this server to "{mode}"')


@bot.command(aliases=['~touchgrass'])
async def bot_touchgrass(ctx: discord.ext.commands.Context, *, msg=''):
    await ctx.send('https://hard-drive.net/hd/video-games/top-10-grasses-to-go-touch/')


@bot.command(aliases=['~uwu'])
async def bot_uwu(ctx: discord.ext.commands.Context, *, msg=''):
    if ctx.message.reference:
        raw_msg = await ctx.fetch_message(ctx.message.reference.message_id)
        uwu_msg = uwu.uwuify(raw_msg.content)
    else:
        uwu_msg = uwu.uwuify(ctx.message.content[5:])
    await ctx.send(uwu_msg)


@bot.command(aliases=['~'])
async def bot_nodice(ctx: discord.ext.commands.Context, *, msg=''):
    choice = [
        'got dice?',
        'gonna roll anything there buddy?',
        'you think i can roll null dice?',
        'did you forget to write something there'
    ]
    await ctx.send(f'{ctx.message.author.mention} {random.choice(choice)}')


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


@bot.command(aliases=['~p', '~poll'])
async def bot_poll(ctx: discord.ext.commands.Context, *, msg=''):
    options = [s.strip() for s in msg.strip().split('-') if len(s) > 0]
    if len(options) > 9:
        await ctx.send('do you really need that many options in a poll?')
        return
    if len(options) < 1:
        await ctx.send('you gonna put any options in that poll? (ps. you can add them with a "-")')
        return
    if len(options) == 1:
        await ctx.send('a poll with only one option is kinda boring isn\'t it? (ps. you can add more with a "-")')
        return

    message = ''
    for i in range(len(options)):
        message += f'{num_to_word[i + 1]}: {options[i]}\n'
    sent_msg = await ctx.send(message)

    for i in range(len(options)):
        await sent_msg.add_reaction(f'{num_to_word[i + 1]}')


@bot.command(aliases=['~qp', '~quickpoll'])
async def bot_qp(ctx: discord.ext.commands.Context, *, msg=''):
    await ctx.message.add_reaction("✅")
    await ctx.message.add_reaction("❌")


@bot.command(aliases=['~pee'])
async def bot_pee(ctx: discord.ext.commands.Context, *, msg=''):
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


@bot.command(aliases=['~a'])
@commands.cooldown(5, 300)
async def bot_a(ctx: discord.ext.commands.Context, *, msg=''):
    await ctx.send(f'<@{owner_id}>')


@bot.command(aliases=['~gun'])
async def bot_gun(ctx: discord.ext.commands.Context, *, msg=''):
    author_pfp = await ctx.author.display_avatar.with_static_format('png').read()
    gun = Image.open('./img/gun.png').resize((150, 150))
    pfp = Image.open(io.BytesIO(author_pfp)).resize(PFP_SIZE)
    pfp.paste(gun, (90, 50), gun)

    pfp_bytes = io.BytesIO()
    pfp.save(pfp_bytes, format="PNG")
    pfp_bytes.seek(0)
    await ctx.send(file=discord.File(pfp_bytes, filename='gun.png'))


@bot.command(aliases=["~love"])
async def bot_love(ctx: discord.ext.commands.Context, *, msg=''):
    if ctx.message.author.id == explode:
        if random.random() < 0.05:
            love = ['💕', '💝', '💖']
            await ctx.message.add_reaction(random.choice(love))
        else:
            await ctx.message.add_reaction('<:Explode:1207534077838626836>')

    elif ctx.message.author.id == explode_more:
        if random.random() < 0.5:
            await ctx.message.add_reaction('<:Explode:1207534077838626836>')
        else:
            love = ['⭐', '✨', '💕', '💝', '💖']
            for lv in love:
                await ctx.message.add_reaction(random.choice(lv))

    else:
        if random.random() < 0.05:
            await ctx.message.add_reaction('<:Explode:1207534077838626836>')
        else:
            love = ['💕', '💝', '💖']
            await ctx.message.add_reaction(random.choice(love))


@bot.command(aliases=["~explode"])
async def bot_explode(ctx: discord.ext.commands.Context, *, msg=""):
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
            if ctx.message.mentions[0].id == int(env.get('OWNER_ID')):
                author_pfp = await (
                    await bot.fetch_user(int(env.get('MEAT_SHIELD')))).display_avatar.with_static_format('png').read()
                message = 'MEAT SHIELD GO'
            else:
                author_pfp = await ctx.message.mentions[0].display_avatar.with_static_format('png').read()
        else:
            ref = await ctx.fetch_message(ctx.message.reference.message_id)
            if ref.author.id == int(env.get('OWNER_ID')):
                author_pfp = await (
                    await bot.fetch_user(int(env.get('MEAT_SHIELD')))).display_avatar.with_static_format('png').read()
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
            message += '<:Explode:1207534077838626836> '
            limit += 1
            if limit >= 30:
                await ctx.send(message)
                message = ''
                limit = 0

        if len(message) > 0:
            await ctx.send(message)


def has_duplicates(lst):
    counts = {}
    for num in lst:
        if num in counts:
            return True
        counts[num] = 1
    return False


weights = [1, .5, .25, .04, .02, .0025]
hate = [
    '\neat shit!!!!!',
    '\nexplode???',
    '\n>:3',
    '\nLOL',
    '\nlmao'
]


def hate_wildseas(ctx: discord.ext.commands.Context, pool, fval):
    twist = has_duplicates(pool)
    if not twist:
        fstr = f'{ctx.message.author.mention}, you rolled 10d for a **{wildsea_dict[fval]}**.'
    else:
        fstr = f'{ctx.message.author.mention}, you rolled 10d for a **Twist** and a **{wildsea_dict[fval]}**.'

    fstr += f' [`10d`: {fval}; '
    for x in pool:
        fstr += f'`{x}`, '
    fstr = fstr[:-2] + "]"

    if fval <= 3:
        fstr += random.choice(hate)
    elif fval == 6:
        fstr += '\ndamn...'
    return fstr


def hate_fitd(ctx: discord.ext.commands.Context, pool, fval):
    crit = pool.count(6) >= 2
    if not crit:
        fstr = f'{ctx.message.author.mention}, you rolled 10d for a **{fitd_dict[fval]}**.'
    else:
        fstr = f'{ctx.message.author.mention}, you rolled 10d for a **Critical Success**.'

    fstr += f' [`10d`: {fval}; '
    for x in pool:
        fstr += f'`{x}`, '
    fstr = fstr[:-2] + "]"

    if fval <= 3:
        fstr += random.choice(hate)
    elif fval == 6:
        fstr += '\ndamn...'
    return fstr


@bot.command(aliases=["~hate"])
async def bot_hate(ctx: discord.ext.commands.Context, *, msg=""):
    pool = [random.choices(range(1, 7), weights=weights)[0] for _ in range(10)]
    pool = sorted(pool, reverse=True)
    fval = max(pool)

    if data['roll mode'][f'{ctx.guild.id}'] == RollModeEnum.WILDSEAS.value:
        await ctx.send(hate_wildseas(ctx, pool, fval))
    elif data['roll mode'][f'{ctx.guild.id}'] == RollModeEnum.FITD.value:
        await ctx.send(hate_fitd(ctx, pool, fval))
    else:
        await ctx.send("invalid roll mode: " + data['roll mode'][f'{ctx.guild.id}'])


def roll_risk_msg():
    roll = random.randint(1, 6)
    return """
```ansi
[1mrisk[0m: you rolled {roll} for {risk}
```""".format(roll=roll, risk=risk_dict[roll])


@bot.command(aliases=["~risk"])
async def roll_risk(ctx: discord.ext.commands.Context, *, msg=""):
    if data['roll mode'][f'{ctx.guild.id}'] == RollModeEnum.CAIN.value:
        await ctx.send(roll_risk_msg())
    else:
        await ctx.send('only available for "cain" roll mode')


def roll_cain(ctx: discord.ext.commands.Context,
              message: str,
              dice: int,
              is_risky: bool,
              is_hard: bool,
              sort_dice: bool):
    if dice > 0:
        pool = [random.randint(1, 6) for _ in range(dice)]
        fval = max(pool)

        if is_hard:
            num_success = pool.count(6)
            if num_success <= 1:
                fstr = f'{ctx.message.author.mention}, you rolled {dice}d with *hard* for a **{cain_dict_hard[fval]}**{message}.'
            else:
                fstr = f'{ctx.message.author.mention}, you rolled {dice}d with *hard* for {num_success} **Successes**{message}.'
        else:
            num_success = pool.count(6) + pool.count(5) + pool.count(4)
            if num_success <= 1:
                fstr = f'{ctx.message.author.mention}, you rolled {dice}d for a **{cain_dict[fval]}**{message}.'
            else:
                fstr = f'{ctx.message.author.mention}, you rolled {dice}d for {num_success} **Successes**{message}.'

        fstr += f' [`{dice}d`: {fval}; '
        for x in (sorted(pool, reverse=True) if sort_dice else pool):
            fstr += f'`{x}`, '
    else:
        pool = [random.randint(1, 6) for _ in range(2 - dice)]
        fval = min(pool)
        if is_hard:
            fstr = f'{ctx.message.author.mention}, you rolled {dice}d with *hard* for a **{cain_dict_hard[fval]}**{message}.'
        else:
            fstr = f'{ctx.message.author.mention}, you rolled {dice}d for a **{cain_dict[fval]}**{message}.'
        fstr += f' [`{dice}d`: {fval}; `{sorted(pool)[0]}`, '
        for x in sorted(pool)[1:]:
            fstr += f'~~`{x}`~~, '

    fstr = fstr[:-2] + "]"
    if is_risky:
        fstr += roll_risk_msg()

    return fstr


def roll_wildsea(ctx: discord.ext.commands.Context, message: str, cut: int, dice: int, sort_dice: bool):
    if cut > 0:
        if dice - cut <= 0:
            if random.random() < .1:
                return (f'{ctx.message.author.mention}, you cut all your dice for a **{wildsea_dict[1]}** like the '
                        f'fool you are')
            else:
                return f'{ctx.message.author.mention}, you cut all your dice for a **{wildsea_dict[1]}**'

    if dice > 0:
        pool = [random.randint(1, 6) for _ in range(dice)]

        if cut > 0:
            pool = sorted(pool, reverse=True)
            fval = pool[cut]
            twist = has_duplicates(pool[cut:])

            if not twist:
                fstr = f'{ctx.message.author.mention}, you rolled {dice}d with cut of {cut} for a **{wildsea_dict[fval]}**{message}.'
            else:
                fstr = f'{ctx.message.author.mention}, you rolled {dice}d with cut of {cut} for a **Twist** and a **{wildsea_dict[fval]}**{message}.'

            cut_count = 0
            fstr += f' [`{dice}d`: {fval}; '
            for x in pool:
                if cut_count < cut:
                    fstr += f'~~`{x}`~~, '
                    cut_count += 1
                else:
                    fstr += f'`{x}`, '
            return fstr[:-2] + "]"
        else:
            fval = max(pool)
            twist = has_duplicates(pool)

            if not twist:
                fstr = f'{ctx.message.author.mention}, you rolled {dice}d for a **{wildsea_dict[fval]}**{message}.'
            else:
                fstr = f'{ctx.message.author.mention}, you rolled {dice}d for a **Twist** and a **{wildsea_dict[fval]}**{message}.'

            fstr += f' [`{dice}d`: {fval}; '
            for x in (sorted(pool, reverse=True) if sort_dice else pool):
                fstr += f'`{x}`, '
            return fstr[:-2] + "]"
    else:
        pool = [random.randint(1, 6) for _ in range(2 - dice)]
        fval = min(pool)
        fstr = f'{ctx.message.author.mention}, you rolled {dice}d for a **{wildsea_dict[fval]}**{message}.'
        fstr += f' [`{dice}d`: {fval}; `{sorted(pool)[0]}`, '
        for x in sorted(pool)[1:]:
            fstr += f'~~`{x}`~~, '
        return fstr[:-2] + "]"


def roll_fitd(ctx: discord.ext.commands.Context, message: str, dice: int, sort_dice: bool):
    if dice > 0:
        pool = [random.randint(1, 6) for _ in range(dice)]
        fval = max(pool)

        crit = pool.count(6) >= 2
        if not crit:
            fstr = f'{ctx.message.author.mention}, you rolled {dice}d for a **{fitd_dict[fval]}**{message}.'
        else:
            fstr = f'{ctx.message.author.mention}, you rolled {dice}d for a **Critical Success**{message}.'

        fstr += f' [`{dice}d`: {fval}; '
        for x in (sorted(pool, reverse=True) if sort_dice else pool):
            fstr += f'`{x}`, '
        return fstr[:-2] + "]"
    else:
        pool = [random.randint(1, 6) for _ in range(2 - dice)]
        fval = min(pool)
        fstr = f'{ctx.message.author.mention}, you rolled {dice}d for a **{fitd_dict[fval]}**{message}.'
        fstr += f' [`{dice}d`: {fval}; `{sorted(pool)[0]}`, '
        for x in sorted(pool)[1:]:
            fstr += f'~~`{x}`~~, '
        return fstr[:-2] + "]"


@bot.command(aliases=["~roll"])
async def bot_roll(ctx: discord.ext.commands.Context, *, msg=""):
    if data['roll mode'][f'{ctx.guild.id}'] == RollModeEnum.CAIN.value:
        try:
            message = ''
            if '#' in msg:
                message = f"; roll for `{msg.split('#')[1]}`"
                msg = msg.split('#')[0]
            split = [x for x in msg.split(" ") if len(x) > 0]
            sorted_dice = ('!' not in split[1]) if len(split) > 1 else True
            dice = int(split[0])
            if sorted_dice:
                difficulty = split[1].strip() if len(split) > 1 else ''
            else:
                difficulty = split[2].strip() if len(split) > 2 else ''
        except ValueError:
            await ctx.send("that doesnt look like a valid integer")
            return
        if dice and dice > 100:
            await ctx.send('in what world do you need to roll that many dice?')
            return

        await ctx.send(roll_cain(ctx, message, dice, 'r' in difficulty, 'h' in difficulty, sorted_dice))
        return

    try:
        message = ''
        if '#' in msg:
            message = f"; roll for `{msg.split('#')[1]}`"
            msg = msg.split('#')[0]
        split = msg.split(" ")
        dice = int(split[0])
        cut = 0
        for i in range(1, len(split)):
            if '-' == split[i][0]:
                cut = int(split[i][1:])
    except ValueError:
        await ctx.send("that doesnt look like a valid integer")
        return

    if data['roll mode'][f'{ctx.guild.id}'] == RollModeEnum.WILDSEAS.value:
        await ctx.send(roll_wildsea(ctx, message, cut, dice, '!' not in split))
    elif data['roll mode'][f'{ctx.guild.id}'] == RollModeEnum.FITD.value:
        await ctx.send(roll_fitd(ctx, message, dice, '!' not in split))
    else:
        await ctx.send("invalid roll mode: " + data['roll mode'][f'{ctx.guild.id}'])


@bot.command(aliases=['~invite'])
async def bot_invite(ctx: discord.ext.commands.Context, *, msg=""):
    if f'{ctx.message.author.id}' == owner_id:
        await ctx.send(f'use this [invite](https://discord.com/oauth2/authorize?client_id=1208179071624941578'
                       f'&permissions=277025688640&scope=bot) to add monobot to your server')
    else:
        await ctx.send('this method is only usable by mono')


bot.run(env.get("CLIENT_TOKEN"))
