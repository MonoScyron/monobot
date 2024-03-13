import io
import random
import re
import dotenv
import discord

from PIL import Image
from discord.ext import commands
from discord.ext.commands import CommandOnCooldown

PFP_SIZE = (200, 200)

env = dotenv.dotenv_values()
command_prefix = env.get('PREFIX')
owner_id = env.get('OWNER_ID')
explode = int(env.get('EXPLODE'))
explode_more = int(env.get('EXPLODE_MORE'))

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


@bot.command(aliases=['~'])
async def botnodice(ctx: discord.ext.commands.Context, *, msg=''):
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
async def botpoll(ctx: discord.ext.commands.Context, *, msg=''):
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
async def botqp(ctx: discord.ext.commands.Context, *, msg=''):
    await ctx.message.add_reaction("✅")
    await ctx.message.add_reaction("❌")


@bot.command(aliases=['~pee'])
async def botpee(ctx: discord.ext.commands.Context, *, msg=''):
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
async def bota(ctx: discord.ext.commands.Context, *, msg=''):
    await ctx.send(f'<@{owner_id}>')


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, CommandOnCooldown):
        await ctx.send(f'<:Explode:1207534077838626836>')


@bot.command(aliases=['~gun'])
async def botgun(ctx: discord.ext.commands.Context, *, msg=''):
    author_pfp = await ctx.author.display_avatar.with_static_format('png').read()
    gun = Image.open('./img/gun.png').resize((150, 150))
    pfp = Image.open(io.BytesIO(author_pfp)).resize(PFP_SIZE)
    pfp.paste(gun, (90, 50), gun)

    pfp_bytes = io.BytesIO()
    pfp.save(pfp_bytes, format="PNG")
    pfp_bytes.seek(0)
    await ctx.send(file=discord.File(pfp_bytes, filename='gun.png'))


@bot.command(aliases=["~love"])
async def botlove(ctx: discord.ext.commands.Context, *, msg=''):
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
async def botexplode(ctx: discord.ext.commands.Context, *, msg=""):
    if ctx.message.mentions:
        author_pfp = await ctx.message.mentions[0].display_avatar.with_static_format('png').read()
        pfp = Image.open(io.BytesIO(author_pfp)).resize(PFP_SIZE)

        frames = []
        for frame_name in range(17):
            frame = Image.open(f'./img/explosion/{frame_name + 1}.png')
            static_copy = pfp.copy()
            static_copy.paste(frame, (0, 0), frame.convert("RGBA"))
            frames.append(static_copy)

        pfp_boom_buffer = io.BytesIO()
        frames[0].save(pfp_boom_buffer, format="GIF", save_all=True, append_images=frames[1:], loop=0, duration=10)
        pfp_boom_buffer.seek(0)

        await ctx.send(file=discord.File(pfp_boom_buffer, filename='boom.gif'))
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


weights = [1, .5, .25, .05, .025, .005]
hate = [
    '\neat shit!!!!!',
    '\nexplode???',
    '\n>:3',
    '\nLOL',
    '\nlmao'
]


@bot.command(aliases=["~hate"])
async def bothate(ctx: discord.ext.commands.Context, *, msg=""):
    pool = [random.choices(range(1, 7), weights=weights)[0] for _ in range(10)]
    pool = sorted(pool, reverse=True)
    fval = max(pool)
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

    await ctx.send(fstr)


@bot.command(aliases=["~rollwildsea"])
async def botroll(ctx: discord.ext.commands.Context, *, msg=""):
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
    await ctx.send(fstr)


bot.run(env.get("CLIENT_TOKEN"))
