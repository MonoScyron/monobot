import random
import re

import discord
import dotenv
from discord.ext import commands

env = dotenv.dotenv_values()
command_prefix = env.get('PREFIX')

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
        print(f'{ctx.content}')
        if re.match(r'~-?\d+[dD]( ?c\d*)?($| ?#.*)', ctx.content):
            newcontent = "rollwildsea " + ctx.content[1:].lower().split("d")[0]
            if "c" in ctx.content:
                newcontent += " c" + ctx.content.split('c')[1].split(" ")[0]
            if "#" in ctx.content:
                newcontent += " #" + ctx.content.split('#')[1]
            ctx.content = newcontent
        await bot.process_commands(ctx)


def has_duplicates(lst):
    counts = {}
    for num in lst:
        if num in counts:
            return True
        counts[num] = 1
    return False


@bot.command(aliases=["rollwildsea"])
async def botroll(ctx: discord.ext.commands.Context, *, msg=""):
    try:
        print(msg)
        split = msg.split(" ")
        dice = int(split[0])
        cut = 0
        if len(split) > 2:
            cut = int(split[1].split("c")[1])
    except ValueError:
        await ctx.send("That doesn't look like a valid pool to me.")
        return

    message = msg.split("#")
    if len(message) > 1:
        message = message[1]
        if message and message[0] == " ":
            message = message[1:]
        message = f"; roll for `{message}`"
    else:
        message = ""

    if dice and dice > 100:
        await ctx.send('Due to statutory limitations on bot labour, I can only roll 100 dice at a time.')
        return

    roll = dice - cut

    if roll > 0:
        pool = [random.randint(1, 6) for _ in range(roll)]

        fval = max(pool)
        twist = has_duplicates(pool)

        if cut > 0:
            if not twist:
                fstr = f'{ctx.message.author.mention}, you rolled {dice}d with cut of {cut} for a **{wildsea_dict[fval]}**{message}.'
            else:
                fstr = f'{ctx.message.author.mention}, you rolled {roll}d for a **Twist** and a **{wildsea_dict[fval]}**{message}.'
        else:
            if not twist:
                fstr = f'{ctx.message.author.mention}, you rolled {dice}d for a **{wildsea_dict[fval]}**{message}.'
            else:
                fstr = f'{ctx.message.author.mention}, you rolled {dice}d for a **Twist** and a **{wildsea_dict[fval]}**{message}.'

        fstr += f' [`{roll}d`: {fval}; '
        for x in sorted(pool, reverse=True):
            fstr += f'`{x}`, '
        fstr = fstr[:-2] + "]"
    else:
        pool = [random.randint(1, 6) for _ in range(2 - roll)]
        fval = min(pool)
        fstr = f'{ctx.message.author.mention}, you rolled {roll}d for a **{wildsea_dict[fval]}**{message}.'
        fstr += f' [`{roll}d`: {fval}; `{sorted(pool)[0]}`, '
        for x in sorted(pool)[1:]:
            fstr += f'~~`{x}`~~, '
        fstr = fstr[:-2] + "]"

    if roll > 7:
        if fval == 6:
            fstr += "\nDid you really expect anything different?"
        elif fval < 4:
            fstr += "\n...That's kind of impressive, really."
    await ctx.send(fstr)


bot.run(env.get("CLIENT_TOKEN"))
