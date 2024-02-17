import random
import re

import discord
import dotenv
from discord.ext import commands

env = dotenv.dotenv_values()
command_prefix = env.get('PREFIX')
owner_id = env.get('OWNER_ID')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.AutoShardedBot(command_prefix='', intents=intents)

wildsea_dict = {
    1: 'Failure',
    2: 'Failure',
    3: 'Failure',
    4: 'Conflict',
    5: 'Conflict',
    6: 'Success'
}


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    activity = discord.Activity(type=discord.ActivityType.playing, name="actual suffering")
    await bot.change_presence(activity=activity)


@bot.event
async def on_message(ctx):
    if ctx.content and ctx.content[0] == command_prefix:
        if re.match(r'~-?\d+[dD]( ?-\d*)?($| ?#.*)', ctx.content):
            newcontent = "~rollwildsea " + ctx.content[1:].lower().split("d")[0]
            cut = ''
            msg = ''
            if "#" in ctx.content:
                msg = "#" + ctx.content.split('#')[1].strip()
                ctx.content = ctx.content.split('#')[0].strip()
            if "-" in ctx.content:
                cut = " -" + ctx.content.split('-')[1].strip()
            ctx.content = newcontent + cut + msg
        await bot.process_commands(ctx)


@bot.command(aliases=["~love"])
async def botlove(ctx: discord.ext.commands.Context, *, msg=''):
    if ctx.message.author.id == 576333021641310211:
        if random.random() < 0.05:
            love = ['💕', '💝', '💖']
            await ctx.message.add_reaction(random.choice(love))
        else:
            await ctx.message.add_reaction('<:Explode:1207534077838626836>')

    elif ctx.message.author.id == 350987269433327637:
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
async def botexplode(ctx: discord.ext.commands.Context, *, msg=""):
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


@bot.command(aliases=["~rollwildsea"])
async def botroll(ctx: discord.ext.commands.Context, *, msg=""):
    try:
        message = ''
        if '#' in msg:
            message = f"; roll for `{msg.split('#')[1]}`"
            msg = msg.split('#')[0]
        print(msg, message)
        split = msg.split(" ")
        dice = int(split[0])
        cut = 0
        for i in range(1, len(split)):
            if '-' == split[i][0]:
                cut = int(split[i][1:])
    except ValueError:
        await ctx.send("that doesnt look like a valid integer")
        return

    if dice and dice > 100:
        await ctx.send('in what world do you need to roll that many dice?')
        return

    if cut > 0:
        if dice - cut <= 0:
            if random.random() < .1:
                await ctx.send(f'{ctx.message.author.mention}, you cut all your dice for a **{wildsea_dict[1]}** like the fool you are')
            else:
                await ctx.send(f'{ctx.message.author.mention}, you cut all your dice for a **{wildsea_dict[1]}**')
            return

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
            fstr = fstr[:-2] + "]"
        else:
            fval = max(pool)
            twist = has_duplicates(pool)

            if not twist:
                fstr = f'{ctx.message.author.mention}, you rolled {dice}d for a **{wildsea_dict[fval]}**{message}.'
            else:
                fstr = f'{ctx.message.author.mention}, you rolled {dice}d for a **Twist** and a **{wildsea_dict[fval]}**{message}.'

            fstr += f' [`{dice}d`: {fval}; '
            for x in sorted(pool, reverse=True):
                fstr += f'`{x}`, '
            fstr = fstr[:-2] + "]"
    else:
        pool = [random.randint(1, 6) for _ in range(2 - dice)]
        fval = min(pool)
        fstr = f'{ctx.message.author.mention}, you rolled {dice}d for a **{wildsea_dict[fval]}**{message}.'
        fstr += f' [`{dice}d`: {fval}; `{sorted(pool)[0]}`, '
        for x in sorted(pool)[1:]:
            fstr += f'~~`{x}`~~, '
        fstr = fstr[:-2] + "]"

    if dice - cut > 7:
        if fval == 6:
            fstr += "\ndid you really expect anything different?"
        elif fval < 4:
            fstr += "\n...pretty fucking impressive, actually."
    await ctx.send(fstr)


bot.run(env.get("CLIENT_TOKEN"))
