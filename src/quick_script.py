import dotenv
import discord

intents = discord.Intents.all()
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print('finished')


env = dotenv.dotenv_values()
client.run(env.get("CLIENT_TOKEN"))
