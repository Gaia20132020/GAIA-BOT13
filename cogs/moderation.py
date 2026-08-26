"""Moderation cog."""
import discord
from discord.ext import commands
from datetime import timedelta, datetime, timezone
import db


def _level_from_xp(xp: int) -> int:
    lvl = 0
    need = 100
    while xp >= need:
        xp -= need
        lvl += 1
        need = 100 + lvl * 50
    return lvl


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="pex")
    @commands.has_permissions(administrator=True)
    async def pex(self, ctx, member: discord.Member, *, role: discord.Role):
        await member.add_roles(role, reason=f"pex da {ctx.author}")
        await ctx.send(f"Aggiunto ruolo {role.mention} a {member.mention}")

    @commands.command(name="depex")
    @commands.has_permissions(administrator=True)
    async def depex(self, ctx, member: discord.Member, *, role: discord.Role):
        await member.remove_roles(role, reason=f"depex da {ctx.author}")
        await ctx.send(f"Rimosso ruolo {role.mention} da {member.mention}")

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = "Nessun motivo"):
        await member.kick(reason=f"{ctx.author}: {reason}")
        await ctx.send(f"{member} è stato kickato. Motivo: {reason}")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str = "Nessun motivo"):
        await member.ban(reason=f"{ctx.author}: {reason}")
        await ctx.send(f"{member} è stato bannato. Motivo: {reason}")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, user_id: int, *, reason: str = "Unban"):
        user = await self.bot.fetch_user(user_id)
        await ctx.guild.unban(user, reason=reason)
        await ctx.send(f"{user} è stato sbannato.")

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, minutes: int, *, reason: str = "Timeout"):
        until = discord.utils.utcnow() + timedelta(minutes=minutes)
        await member.timeout(until, reason=reason)
        await ctx.send(f"{member.mention} in timeout per {minutes} minuti.")

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def untimeout(self, ctx, member: discord.Member):
        await member.timeout(None, reason=f"untimeout da {ctx.author}")
        await ctx.send(f"Timeout rimosso a {member.mention}.")

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str = "Nessun motivo"):
        await db.warns.insert_one({
            "guild_id": ctx.guild.id, "user_id": member.id,
            "mod_id": ctx.author.id, "reason": reason,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        count = await db.warns.count_documents({"guild_id": ctx.guild.id, "user_id": member.id})
        await ctx.send(f"{member.mention} avvisato (#{count}). Motivo: {reason}")

    @commands.command(name="warncount", aliases=["warn_count"])
    async def warn_count(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        count = await db.warns.count_documents({"guild_id": ctx.guild.id, "user_id": member.id})
        await ctx.send(f"{member.mention} ha {count} warn.")

    @commands.command(name="resetwarn", aliases=["reset_warn"])
    @commands.has_permissions(kick_members=True)
    async def reset_warn(self, ctx, member: discord.Member):
        r = await db.warns.delete_many({"guild_id": ctx.guild.id, "user_id": member.id})
        await ctx.send(f"Rimossi {r.deleted_count} warn a {member.mention}.")

    @commands.command(name="leavewarn", aliases=["leave_warn"])
    @commands.has_permissions(kick_members=True)
    async def leave_warn(self, ctx, member: discord.Member, warn_index: int):
        cursor = db.warns.find({"guild_id": ctx.guild.id, "user_id": member.id}).sort("ts", -1)
        docs = await cursor.to_list(length=100)
        if warn_index < 1 or warn_index > len(docs):
            return await ctx.send("Indice warn non valido.")
        await db.warns.delete_one({"_id": docs[warn_index - 1]["_id"]})
        await ctx.send(f"Warn #{warn_index} rimosso a {member.mention}.")

    @commands.command(aliases=["level", "lvl"])
    async def livelli(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        u = await db.get_user(ctx.guild.id, member.id)
        e = discord.Embed(title=f"Livello di {member.display_name}", color=0x9b59b6)
        e.add_field(name="Livello", value=str(u.get("level", 0)))
        e.add_field(name="XP", value=str(u.get("xp", 0)))
        e.add_field(name="Messaggi", value=str(u.get("messages", 0)))
        e.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=e)

    @commands.command(name="xpadd", aliases=["xp_add"])
    @commands.has_permissions(administrator=True)
    async def xp_add(self, ctx, member: discord.Member, amount: int):
        u = await db.get_user(ctx.guild.id, member.id)
        new_xp = u.get("xp", 0) + amount
        await db.update_user(ctx.guild.id, member.id, {"xp": new_xp, "level": _level_from_xp(new_xp)})
        await ctx.send(f"Aggiunti {amount} XP a {member.mention}.")

    @commands.command(name="messageadd", aliases=["message_add"])
    @commands.has_permissions(administrator=True)
    async def message_add(self, ctx, member: discord.Member, amount: int):
        await db.inc_user(ctx.guild.id, member.id, {"messages": amount})
        await ctx.send(f"Aggiunti {amount} messaggi a {member.mention}.")

    @commands.command(name="messagecount", aliases=["message_count"])
    async def message_count(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        u = await db.get_user(ctx.guild.id, member.id)
        await ctx.send(f"{member.mention} ha {u.get('messages', 0)} messaggi.")

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int):
        if amount < 1 or amount > 100:
            return await ctx.send("Numero tra 1 e 100.")
        deleted = await ctx.channel.purge(limit=amount + 1)
        m = await ctx.send(f"Eliminati {len(deleted) - 1} messaggi.")
        await m.delete(delay=3)

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"{channel.mention} bloccato.")

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"{channel.mention} sbloccato.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        u = await db.get_user(message.guild.id, message.author.id)
        new_xp = u.get("xp", 0) + 5
        new_lvl = _level_from_xp(new_xp)
        old_lvl = u.get("level", 0)
        await db.update_user(message.guild.id, message.author.id, {"xp": new_xp, "level": new_lvl})
        await db.inc_user(message.guild.id, message.author.id, {"messages": 1})
        if new_lvl > old_lvl:
            try:
                await message.channel.send(f"{message.author.mention} è salito al livello {new_lvl}!")
            except Exception:
                pass


async def setup(bot):
    await bot.add_cog(Moderation(bot))
