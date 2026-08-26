"""Music cog."""
import asyncio
import discord
from discord.ext import commands
import yt_dlp
import db

YDL_OPTS = {
    "format": "bestaudio/best", "quiet": True, "no_warnings": True,
    "default_search": "ytsearch", "source_address": "0.0.0.0", "noplaylist": True,
}
FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


async def fetch_track(query: str) -> dict:
    loop = asyncio.get_event_loop()
    def _extract():
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(query, download=False)
            if "entries" in info:
                info = info["entries"][0]
            return {"title": info.get("title", "Sconosciuto"), "url": info["url"], "webpage": info.get("webpage_url", "")}
    return await loop.run_in_executor(None, _extract)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues: dict[int, list[dict]] = {}

    async def _ensure_voice(self, ctx):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("Devi essere in un canale vocale!")
            return None
        vc = ctx.voice_client
        if vc is None:
            vc = await ctx.author.voice.channel.connect()
        elif vc.channel != ctx.author.voice.channel:
            await vc.move_to(ctx.author.voice.channel)
        return vc

    def _play_next(self, ctx, vc):
        q = self.queues.get(ctx.guild.id, [])
        if not q:
            return
        track = q.pop(0)
        source = discord.FFmpegPCMAudio(track["url"], **FFMPEG_OPTS)
        vc.play(source, after=lambda e: self._play_next(ctx, vc) if not e else None)
        asyncio.run_coroutine_threadsafe(ctx.send(f"▶️ In riproduzione: **{track['title']}**"), self.bot.loop)

    @commands.command()
    async def play(self, ctx, *, query: str):
        vc = await self._ensure_voice(ctx)
        if not vc:
            return
        async with ctx.typing():
            track = await fetch_track(query)
        self.queues.setdefault(ctx.guild.id, []).append(track)
        if not vc.is_playing():
            self._play_next(ctx, vc)
        else:
            await ctx.send(f"➕ In coda: **{track['title']}**")

    @commands.command()
    async def stop(self, ctx):
        vc = ctx.voice_client
        if not vc:
            return await ctx.send("Non sono in un canale vocale.")
        self.queues[ctx.guild.id] = []
        vc.stop()
        await vc.disconnect()
        await ctx.send("⏹️ Fermato e disconnesso.")

    @commands.group(name="playlist", invoke_without_command=True)
    async def playlist(self, ctx):
        docs = await db.playlists.find({"guild_id": ctx.guild.id, "user_id": ctx.author.id}).to_list(length=25)
        if not docs:
            return await ctx.send("Non hai playlist. Crea con `!playlist create <nome> <url1> <url2>...`")
        e = discord.Embed(title=f"Playlist di {ctx.author.display_name}", color=0x1db954)
        for p in docs:
            e.add_field(name=p["name"], value=f"{len(p.get('tracks', []))} brani", inline=False)
        await ctx.send(embed=e)

    @playlist.command(name="create")
    async def playlist_create(self, ctx, name: str, *tracks: str):
        if not tracks:
            return await ctx.send("Aggiungi almeno un brano.")
        await db.playlists.update_one(
            {"guild_id": ctx.guild.id, "user_id": ctx.author.id, "name": name},
            {"$set": {"tracks": [{"query": t} for t in tracks]}}, upsert=True,
        )
        await ctx.send(f"Playlist **{name}** creata con {len(tracks)} brani.")

    @playlist.command(name="play")
    async def playlist_play(self, ctx, *, name: str):
        pl = await db.playlists.find_one({"guild_id": ctx.guild.id, "user_id": ctx.author.id, "name": name})
        if not pl:
            return await ctx.send("Playlist non trovata.")
        vc = await self._ensure_voice(ctx)
        if not vc:
            return
        async with ctx.typing():
            for t in pl.get("tracks", []):
                try:
                    track = await fetch_track(t["query"])
                    self.queues.setdefault(ctx.guild.id, []).append(track)
                except Exception:
                    pass
        await ctx.send(f"▶️ Playlist **{name}** in coda ({len(self.queues[ctx.guild.id])} brani).")
        if not vc.is_playing():
            self._play_next(ctx, vc)

    @playlist.command(name="delete")
    async def playlist_delete(self, ctx, *, name: str):
        r = await db.playlists.delete_one({"guild_id": ctx.guild.id, "user_id": ctx.author.id, "name": name})
        if r.deleted_count:
            await ctx.send(f"Playlist **{name}** eliminata.")
        else:
            await ctx.send("Playlist non trovata.")


async def setup(bot):
    await bot.add_cog(Music(bot))
