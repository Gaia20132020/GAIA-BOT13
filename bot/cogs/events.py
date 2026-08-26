"""Events cog: welcome/goodbye + invite tracking."""
import discord
from discord.ext import commands
import db


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invite_cache: dict[int, dict[str, int]] = {}

    @commands.Cog.listener()
    async def on_ready(self):
        for g in self.bot.guilds:
            try:
                invs = await g.invites()
                self.invite_cache[g.id] = {i.code: i.uses for i in invs}
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        self.invite_cache.setdefault(invite.guild.id, {})[invite.code] = invite.uses or 0

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = await db.get_guild_config(member.guild.id)
        wc = cfg.get("welcome_channel")
        if wc:
            ch = member.guild.get_channel(wc)
            if ch:
                msg = cfg.get("welcome_msg", "Benvenuto/a {user} in {server}!")
                await ch.send(msg.replace("{user}", member.mention).replace("{server}", member.guild.name))
        try:
            new_invs = await member.guild.invites()
            old = self.invite_cache.get(member.guild.id, {})
            inviter = None
            for inv in new_invs:
                if inv.uses and inv.uses > old.get(inv.code, 0):
                    inviter = inv.inviter
                    break
            self.invite_cache[member.guild.id] = {i.code: i.uses for i in new_invs}
            if inviter:
                await db.invites.update_one(
                    {"guild_id": member.guild.id, "user_id": inviter.id},
                    {"$inc": {"count": 1}}, upsert=True,
                )
                ic = cfg.get("invites_channel")
                if ic:
                    ch = member.guild.get_channel(ic)
                    if ch:
                        c = await db.invites.find_one({"guild_id": member.guild.id, "user_id": inviter.id})
                        await ch.send(f"📩 {member.mention} è entrato con l'invito di {inviter.mention} (totale: {c.get('count', 1)}).")
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        cfg = await db.get_guild_config(member.guild.id)
        gc = cfg.get("goodbye_channel")
        if gc:
            ch = member.guild.get_channel(gc)
            if ch:
                msg = cfg.get("goodbye_msg", "{user} ha lasciato {server}.")
                await ch.send(msg.replace("{user}", str(member)).replace("{server}", member.guild.name))


async def setup(bot):
    await bot.add_cog(Events(bot))
