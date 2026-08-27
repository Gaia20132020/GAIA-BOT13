"""Support cog: ticket panel (3 types), giveaway, welcome/goodbye, invites, provino staff."""
import asyncio
import random
import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta
import db


TICKET_TYPES = {
    "collab":  {"label": "Collaborazione",   "emoji": "🤝", "color": 0x3498db, "style": discord.ButtonStyle.primary},
    "help":    {"label": "Aiuto Generale",   "emoji": "❓", "color": 0x2ecc71, "style": discord.ButtonStyle.success},
    "report":  {"label": "Segnala Cittadino","emoji": "🚨", "color": 0xe74c3c, "style": discord.ButtonStyle.danger},
    "provino": {"label": "Provino Staff",    "emoji": "🎓", "color": 0x9b59b6, "style": discord.ButtonStyle.secondary},
}


def parse_duration(s: str) -> int:
    s = s.strip().lower()
    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    if s[-1] in mult and s[:-1].isdigit():
        return int(s[:-1]) * mult[s[-1]]
    return int(s)


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", emoji="✅", style=discord.ButtonStyle.success, custom_id="tk_claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        t = await db.tickets.find_one({"channel_id": interaction.channel.id})
        if not t:
            return await interaction.response.send_message("Non è un ticket.", ephemeral=True)
        if t.get("claimed_by"):
            return await interaction.response.send_message(f"Già reclamato da <@{t['claimed_by']}>.", ephemeral=True)
        await db.tickets.update_one({"channel_id": interaction.channel.id}, {"$set": {"claimed_by": interaction.user.id}})
        await interaction.response.send_message(f"✅ Ticket reclamato da {interaction.user.mention}.")

    @discord.ui.button(label="Unclaim", emoji="↩️", style=discord.ButtonStyle.secondary, custom_id="tk_unclaim")
    async def unclaim(self, interaction: discord.Interaction, button: discord.ui.Button):
        t = await db.tickets.find_one({"channel_id": interaction.channel.id})
        if not t:
            return await interaction.response.send_message("Non è un ticket.", ephemeral=True)
        await db.tickets.update_one({"channel_id": interaction.channel.id}, {"$set": {"claimed_by": None}})
        await interaction.response.send_message("Ticket non più reclamato.")

    @discord.ui.button(label="Close", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="tk_close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        t = await db.tickets.find_one({"channel_id": interaction.channel.id})
        if not t:
            return await interaction.response.send_message("Non è un ticket.", ephemeral=True)
        await interaction.response.send_message("🔒 Chiusura in 5 secondi...")
        await asyncio.sleep(5)
        await db.tickets.delete_one({"channel_id": interaction.channel.id})
        try:
            await interaction.channel.delete(reason=f"Ticket chiuso da {interaction.user}")
        except Exception:
            pass

    @discord.ui.button(label="Close with reason", emoji="📝", style=discord.ButtonStyle.danger, custom_id="tk_close_reason")
    async def close_reason(self, interaction: discord.Interaction, button: discord.ui.Button):
        t = await db.tickets.find_one({"channel_id": interaction.channel.id})
        if not t:
            return await interaction.response.send_message("Non è un ticket.", ephemeral=True)
        await interaction.response.send_modal(CloseReasonModal())


class CloseReasonModal(discord.ui.Modal, title="Chiudi ticket con motivo"):
    reason = discord.ui.TextInput(label="Motivo di chiusura", style=discord.TextStyle.paragraph, required=True, max_length=500)

    async def on_submit(self, interaction: discord.Interaction):
        t = await db.tickets.find_one({"channel_id": interaction.channel.id})
        if not t:
            return
        opener = interaction.guild.get_member(t["opener_id"])
        if opener:
            try:
                e = discord.Embed(title="Il tuo ticket è stato chiuso", color=0xe74c3c,
                                  description=f"**Server:** {interaction.guild.name}\n**Chiuso da:** {interaction.user}\n**Motivo:** {self.reason.value}")
                await opener.send(embed=e)
            except Exception:
                pass
        await interaction.response.send_message(f"🔒 Ticket chiuso da {interaction.user.mention}\n**Motivo:** {self.reason.value}\nChiusura in 5s...")
        await asyncio.sleep(5)
        await db.tickets.delete_one({"channel_id": interaction.channel.id})
        try:
            await interaction.channel.delete(reason=f"Ticket chiuso: {self.reason.value}")
        except Exception:
            pass


class TicketPanelView(discord.ui.View):
    def __init__(self, with_provino: bool = False):
        super().__init__(timeout=None)
        for key in ("collab", "help", "report"):
            info = TICKET_TYPES[key]
            btn = discord.ui.Button(label=info["label"], emoji=info["emoji"], style=info["style"], custom_id=f"open_{key}")
            btn.callback = self._make_callback(key)
            self.add_item(btn)
        if with_provino:
            info = TICKET_TYPES["provino"]
            btn = discord.ui.Button(label=info["label"], emoji=info["emoji"], style=info["style"], custom_id="open_provino")
            btn.callback = self._make_callback("provino")
            self.add_item(btn)

    def _make_callback(self, kind: str):
        async def cb(interaction: discord.Interaction):
            await open_ticket(interaction, kind)
        return cb


async def open_ticket(interaction: discord.Interaction, kind: str):
    guild = interaction.guild
    info = TICKET_TYPES[kind]
    ch_name = f"{kind}-{interaction.user.name}".lower().replace(" ", "-")[:90]
    existing = discord.utils.get(guild.text_channels, name=ch_name)
    if existing:
        return await interaction.response.send_message(f"Hai già un ticket: {existing.mention}", ephemeral=True)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, embed_links=True),
    }

    cfg = await db.get_guild_config(guild.id)
    staff_role_id = cfg.get("staff_role")
    staff_role = guild.get_role(staff_role_id) if staff_role_id else None
    if staff_role:
        overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True)

    cat_name = "Tickets" if kind != "provino" else "Provini"
    category = discord.utils.get(guild.categories, name=cat_name)
    if not category:
        category = await guild.create_category(cat_name)

    ch = await guild.create_text_channel(name=ch_name, category=category, overwrites=overwrites)
    await db.tickets.insert_one({
        "channel_id": ch.id, "guild_id": guild.id, "opener_id": interaction.user.id,
        "kind": kind, "claimed_by": None, "extra_users": [],
    })

    e = discord.Embed(title=f"{info['emoji']} Ticket: {info['label']}",
                      description=f"Ciao {interaction.user.mention}! Uno staff ti risponderà appena possibile.\nNel frattempo descrivi bene la tua richiesta.",
                      color=info["color"])
    e.set_footer(text=f"Aperto da {interaction.user}", icon_url=interaction.user.display_avatar.url)

    ping = staff_role.mention if staff_role else "@Staff"
    await ch.send(content=f"{interaction.user.mention} · {ping}", embed=e, view=TicketControlView(),
                  allowed_mentions=discord.AllowedMentions(users=True, roles=True))
    await interaction.response.send_message(f"✅ Ticket aperto: {ch.mention}", ephemeral=True)


class Support(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.giveaway_task.start()

    async def cog_load(self):
        self.bot.add_view(TicketPanelView(with_provino=False))
        self.bot.add_view(TicketPanelView(with_provino=True))
        self.bot.add_view(TicketControlView())

    def cog_unload(self):
        self.giveaway_task.cancel()

    @commands.command(name="setstaffrole", aliases=["staffrole"])
    @commands.has_permissions(administrator=True)
    async def set_staff_role(self, ctx, role: discord.Role):
        await db.guild_config.update_one({"guild_id": ctx.guild.id}, {"$set": {"staff_role": role.id}}, upsert=True)
        await ctx.send(f"✅ Ruolo staff impostato: {role.mention}")

    @commands.command(name="pannelloticket", aliases=["pannello_ticket", "ticketpanel"])
    @commands.has_permissions(manage_guild=True)
    async def pannello_ticket(self, ctx):
        e = discord.Embed(title="🎫 Pannello Ticket",
                          description="Scegli il tipo di richiesta cliccando uno dei pulsanti qui sotto:\n\n"
                                      "🤝 **Collaborazione** — proposte, partnership, collab\n"
                                      "❓ **Aiuto Generale** — domande e assistenza\n"
                                      "🚨 **Segnala Cittadino** — segnalazioni utenti / regole",
                          color=0x5865f2)
        e.set_footer(text="Apri solo un ticket alla volta.")
        await ctx.send(embed=e, view=TicketPanelView(with_provino=False))

    @commands.command(name="close", aliases=["closeticket", "close_ticket"])
    async def close_ticket(self, ctx):
        t = await db.tickets.find_one({"channel_id": ctx.channel.id})
        if not t:
            return await ctx.send("Questo non è un ticket.")
        await ctx.send("Chiusura in 5 secondi...")
        await asyncio.sleep(5)
        await db.tickets.delete_one({"channel_id": ctx.channel.id})
        await ctx.channel.delete(reason=f"Ticket chiuso da {ctx.author}")

    @commands.command(name="reclama", aliases=["claim", "claimticket"])
    async def reclama_ticket(self, ctx):
        t = await db.tickets.find_one({"channel_id": ctx.channel.id})
        if not t:
            return await ctx.send("Questo non è un ticket.")
        if t.get("claimed_by"):
            return await ctx.send(f"Già reclamato da <@{t['claimed_by']}>.")
        await db.tickets.update_one({"channel_id": ctx.channel.id}, {"$set": {"claimed_by": ctx.author.id}})
        await ctx.send(f"✅ Ticket reclamato da {ctx.author.mention}.")

    @commands.command(name="unclaima", aliases=["unclaim"])
    async def unclaima_ticket(self, ctx):
        t = await db.tickets.find_one({"channel_id": ctx.channel.id})
        if not t:
            return await ctx.send("Questo non è un ticket.")
        await db.tickets.update_one({"channel_id": ctx.channel.id}, {"$set": {"claimed_by": None}})
        await ctx.send("Ticket non più reclamato.")

    @commands.command(name="aggiungi", aliases=["adduser", "aggiungialticket"])
    async def aggiungi_al_ticket(self, ctx, member: discord.Member):
        t = await db.tickets.find_one({"channel_id": ctx.channel.id})
        if not t:
            return await ctx.send("Questo non è un ticket.")
        await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
        await ctx.send(f"Aggiunto {member.mention} al ticket.")

    @commands.command(name="provinostaffcreate", aliases=["provino_staff_create"])
    @commands.has_permissions(manage_guild=True)
    async def provino_staff_create(self, ctx):
        e = discord.Embed(title="🎓 Provino Staff",
                          description="Vuoi entrare nello staff? Clicca il bottone qui sotto per aprire un provino.",
                          color=0x9b59b6)
        await ctx.send(embed=e, view=TicketPanelView(with_provino=True))

    @commands.command(name="provinostaffshow", aliases=["provino_staff_show"])
    async def provino_staff_show(self, ctx):
        docs = await db.tickets.find({"guild_id": ctx.guild.id, "kind": "provino"}).to_list(length=50)
        e = discord.Embed(title="Provini attivi", color=0x9b59b6)
        e.description = "\n".join(f"<#{d['channel_id']}> — <@{d['opener_id']}>" for d in docs) if docs else "Nessun provino attivo."
        await ctx.send(embed=e)

    @commands.command(name="creategiveaway", aliases=["create_giveaway", "gwcreate"])
    @commands.has_permissions(manage_guild=True)
    async def create_giveaway(self, ctx, duration: str, winners: int, *, prize: str):
        try:
            secs = parse_duration(duration)
        except Exception:
            return await ctx.send("Durata non valida. Esempi: 10m, 2h, 1d")
        ends_at = datetime.now(timezone.utc) + timedelta(seconds=secs)
        e = discord.Embed(title="🎉 GIVEAWAY 🎉", color=0xf39c12,
                          description=f"**Premio:** {prize}\n**Vincitori:** {winners}\n**Finisce:** <t:{int(ends_at.timestamp())}:R>\n\nReagisci con 🎉!")
        e.set_footer(text=f"Host: {ctx.author.display_name}")
        msg = await ctx.send(embed=e)
        await msg.add_reaction("🎉")
        gw_id = f"{ctx.guild.id}-{msg.id}"
        await db.giveaways.insert_one({
            "gw_id": gw_id, "guild_id": ctx.guild.id, "channel_id": ctx.channel.id,
            "message_id": msg.id, "prize": prize, "ends_at": ends_at.isoformat(),
            "winners": winners, "host_id": ctx.author.id, "ended": False,
        })
        await ctx.send(f"Giveaway creato. ID: `{gw_id}`", delete_after=10)

    async def _finish_giveaway(self, gw: dict):
        ch = self.bot.get_channel(gw["channel_id"])
        if not ch:
            return []
        try:
            msg = await ch.fetch_message(gw["message_id"])
        except Exception:
            return []
        users = []
        for r in msg.reactions:
            if str(r.emoji) == "🎉":
                async for u in r.users():
                    if not u.bot:
                        users.append(u.id)
        if not users:
            await ch.send(f"Giveaway **{gw['prize']}** terminato — nessun partecipante.")
            await db.giveaways.update_one({"gw_id": gw["gw_id"]}, {"$set": {"ended": True, "winner_ids": []}})
            return []
        winners = random.sample(users, min(gw["winners"], len(users)))
        await ch.send(f"🎉 Vincitori di **{gw['prize']}**: {', '.join(f'<@{w}>' for w in winners)}!")
        await db.giveaways.update_one({"gw_id": gw["gw_id"]}, {"$set": {"ended": True, "winner_ids": winners}})
        return winners

    @commands.command(name="endgiveaway", aliases=["end_giveaway", "gwend"])
    @commands.has_permissions(manage_guild=True)
    async def end_giveaway(self, ctx, gw_id: str):
        gw = await db.giveaways.find_one({"gw_id": gw_id})
        if not gw:
            return await ctx.send("Giveaway non trovato.")
        if gw.get("ended"):
            return await ctx.send("Già terminato.")
        await self._finish_giveaway(gw)

    @commands.command(name="giveawayreroll", aliases=["gwreroll", "giveaway_reroll"])
    @commands.has_permissions(manage_guild=True)
    async def giveaway_reroll(self, ctx, gw_id: str):
        gw = await db.giveaways.find_one({"gw_id": gw_id})
        if not gw:
            return await ctx.send("Giveaway non trovato.")
        await self._finish_giveaway(gw)

    @commands.command(name="showgiveawaylist", aliases=["giveawaylist", "gwlist"])
    async def show_giveaway_list(self, ctx):
        docs = await db.giveaways.find({"guild_id": ctx.guild.id, "ended": False}).to_list(length=25)
        e = discord.Embed(title="Giveaway attivi", color=0xf39c12)
        e.description = "\n".join(f"`{d['gw_id']}` — {d['prize']}" for d in docs) if docs else "Nessun giveaway attivo."
        await ctx.send(embed=e)

    @commands.command(name="showgiveawayid", aliases=["giveawayinfo", "gwshow"])
    async def show_giveaway_id(self, ctx, gw_id: str):
        gw = await db.giveaways.find_one({"gw_id": gw_id})
        if not gw:
            return await ctx.send("Non trovato.")
        e = discord.Embed(title=f"Giveaway {gw_id}", color=0xf39c12)
        e.add_field(name="Premio", value=gw["prize"])
        e.add_field(name="Vincitori", value=str(gw["winners"]))
        e.add_field(name="Finisce", value=gw["ends_at"], inline=False)
        e.add_field(name="Stato", value="Terminato" if gw.get("ended") else "Attivo")
        await ctx.send(embed=e)

    @tasks.loop(seconds=30)
    async def giveaway_task(self):
        now = datetime.now(timezone.utc)
        docs = await db.giveaways.find({"ended": False}).to_list(length=100)
        for gw in docs:
            try:
                ends = datetime.fromisoformat(gw["ends_at"])
                if ends <= now:
                    await self._finish_giveaway(gw)
            except Exception:
                pass

    @giveaway_task.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()

    @commands.command(name="setwelcome")
    @commands.has_permissions(manage_guild=True)
    async def setwelcome(self, ctx, channel: discord.TextChannel, *, message: str = "Benvenuto/a {user} in {server}!"):
        await db.guild_config.update_one({"guild_id": ctx.guild.id}, {"$set": {"welcome_channel": channel.id, "welcome_msg": message}}, upsert=True)
        await ctx.send(f"Canale benvenuto: {channel.mention}\nMessaggio: {message}")

    @commands.command(name="setgoodbye")
    @commands.has_permissions(manage_guild=True)
    async def setgoodbye(self, ctx, channel: discord.TextChannel, *, message: str = "{user} ha lasciato {server}."):
        await db.guild_config.update_one({"guild_id": ctx.guild.id}, {"$set": {"goodbye_channel": channel.id, "goodbye_msg": message}}, upsert=True)
        await ctx.send(f"Canale addio: {channel.mention}\nMessaggio: {message}")

    @commands.command(name="showinvites", aliases=["invites"])
    async def show_invites(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        doc = await db.invites.find_one({"guild_id": ctx.guild.id, "user_id": member.id})
        count = doc.get("count", 0) if doc else 0
        await ctx.send(f"{member.mention} ha invitato {count} membri.")

    @commands.command(name="setinviteschannel", aliases=["setinvites_channel"])
    @commands.has_permissions(manage_guild=True)
    async def set_invites_channel(self, ctx, channel: discord.TextChannel):
        await db.guild_config.update_one({"guild_id": ctx.guild.id}, {"$set": {"invites_channel": channel.id}}, upsert=True)
        await ctx.send(f"Canale invites: {channel.mention}")

    @commands.command(name="resetinvites")
    @commands.has_permissions(manage_guild=True)
    async def reset_invites(self, ctx, member: discord.Member = None):
        if member:
            await db.invites.update_one({"guild_id": ctx.guild.id, "user_id": member.id}, {"$set": {"count": 0}}, upsert=True)
            await ctx.send(f"Invites di {member.mention} azzerati.")
        else:
            await db.invites.delete_many({"guild_id": ctx.guild.id})
            await ctx.send("Tutti gli invites del server azzerati.")

    @commands.command(name="addinvites")
    @commands.has_permissions(manage_guild=True)
    async def add_invites(self, ctx, member: discord.Member, amount: int):
        await db.invites.update_one({"guild_id": ctx.guild.id, "user_id": member.id}, {"$inc": {"count": amount}}, upsert=True)
        await ctx.send(f"Aggiunti {amount} invites a {member.mention}.")

    @commands.command(name="invitebot", aliases=["invite_bot", "invite"])
    async def invite_bot(self, ctx):
        url = discord.utils.oauth_url(self.bot.user.id, permissions=discord.Permissions(administrator=True),
                                      scopes=["bot", "applications.commands"])
        await ctx.send(f"🔗 Invita il bot: {url}")


async def setup(bot):
    await bot.add_cog(Support(bot))
