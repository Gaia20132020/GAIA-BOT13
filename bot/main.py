"""Main entry point for the Discord bot."""
import os
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import discord
from discord.ext import commands

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("bot")

PREFIX = os.environ.get("PREFIX", "!")
TOKEN = os.environ.get("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.invites = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None, case_insensitive=True)


@bot.event
async def on_ready():
    log.info(f"Bot online come {bot.user} (id={bot.user.id})")
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}help | {len(bot.guilds)} server"))


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(f"Ti mancano i permessi: `{', '.join(error.missing_permissions)}`")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Argomento mancante: `{error.param.name}`. Usa `{PREFIX}help {ctx.command}`.")
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send(f"Argomento non valido: {error}")
        return
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"In cooldown. Riprova tra {error.retry_after:.0f}s.")
        return
    log.exception("Errore comando", exc_info=error)
    try:
        await ctx.send(f"Errore: `{type(error).__name__}: {error}`")
    except Exception:
        pass


COGS = [
    "cogs.moderation",
    "cogs.economy",
    "cogs.games",
    "cogs.music",
    "cogs.support",
    "cogs.general",
    "cogs.events",
    "cogs.automod",
]


async def main():
    async with bot:
        for c in COGS:
            try:
                await bot.load_extension(c)
                log.info(f"Cog caricata: {c}")
            except Exception as e:
                log.exception(f"Fallito caricamento {c}: {e}")
        if not TOKEN:
            log.error("DISCORD_TOKEN mancante!")
            return
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
