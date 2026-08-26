"""AutoMod cog: banned words, link blocking, anti-spam (repeated messages / flood).

Commands (require manage_guild):
- !automod          -> mostra stato
- !automod on|off   -> abilita/disabilita l'automod
- !automod links on|off
- !automod spam on|off
- !addbadword <parola>
- !removebadword <parola>
- !listbadwords
"""
import time
import re
from collections import defaultdict, deque
import discord
from discord.ext import commands
import db


LINK_RE = re.compile(r"https?://\S+|discord\.gg/\S+", re.IGNORECASE)

# In-memory sliding window for spam detection
# key = (guild_id, user_id) -> deque of (timestamp, content)
_msg_history: dict[tuple, deque] = defaultdict(lambda: deque(maxlen=8))

SPAM_WINDOW = 6      # seconds
SPAM_LIMIT = 5       # messages in window -> spam
REPEAT_LIMIT = 3     # same content N times -> spam
MUTE_SECONDS = 300   # 5-minute timeout on spam


async def _get_automod(guild_id: int) -> dict:
    cfg = await db.get_guild_config(guild_id)
    return cfg.get("automod", {
        "enabled": False,
        "block_links": False,
        "block_spam": True,
        "bad_words": [],
    })


async def _save_automod(guild_id: int, am: dict):
    await db.guild_config.update_one(
        {"guild_id": guild_id},
        {"$set": {"automod": am}},
        upsert=True,
    )


async def _log_action(bot, guild: discord.Guild, *, action: str, user: discord.Member,
                      channel: discord.TextChannel, reason: str, content: str = "",
                      color: int = 0xe74c3c):
    """Send an automod action to the configured log channel (if any)."""
    am = await _get_automod(guild.id)
    log_id = am.get("log_channel")
    if not log_id:
        return
    log_ch = guild.get_channel(log_id)
    if not log_ch:
        return
    e = discord.Embed(title=f"🛡️ AutoMod — {action}", color=color, timestamp=discord.utils.utcnow())
    e.add_field(name="Utente", value=f"{user.mention} (`{user.id}`)", inline=True)
    e.add_field(name="Canale", value=channel.mention, inline=True)
    e.add_field(name="Motivo", value=reason, inline=False)
    if content:
        snippet = content if len(content) <= 500 else content[:500] + "..."
        e.add_field(name="Messaggio", value=f"```{snippet}```", inline=False)
    e.set_thumbnail(url=user.display_avatar.url)
    try:
        await log_ch.send(embed=e)
    except Exception:
        pass


class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------------- Listener ----------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        # Skip staff (manage_messages)
        if message.author.guild_permissions.manage_messages:
            return

        am = await _get_automod(message.guild.id)
        if not am.get("enabled"):
            return

        content = message.content or ""
        lc = content.lower()

        # --- Bad words ---
        for w in am.get("bad_words", []):
            if w and w.lower() in lc:
                try:
                    await message.delete()
                except Exception:
                    pass
                try:
                    await message.channel.send(
                        f"{message.author.mention} parola vietata rilevata. Messaggio rimosso.",
                        delete_after=6,
                    )
                except Exception:
                    pass
                await db.warns.insert_one({
                    "guild_id": message.guild.id, "user_id": message.author.id,
                    "mod_id": self.bot.user.id, "reason": f"AutoMod: parola vietata ({w})",
                    "ts": time.time(),
                })
                await _log_action(self.bot, message.guild,
                    action="Parola vietata", user=message.author, channel=message.channel,
                    reason=f"Parola bloccata: `{w}`", content=content, color=0xe74c3c)
                return

        # --- Links ---
        if am.get("block_links") and LINK_RE.search(content):
            try:
                await message.delete()
            except Exception:
                pass
            try:
                await message.channel.send(
                    f"{message.author.mention} i link non sono permessi qui.",
                    delete_after=6,
                )
            except Exception:
                pass
            await _log_action(self.bot, message.guild,
                action="Link bloccato", user=message.author, channel=message.channel,
                reason="Link non permesso", content=content, color=0xf39c12)
            return

        # --- Spam / flood ---
        if am.get("block_spam", True):
            key = (message.guild.id, message.author.id)
            hist = _msg_history[key]
            now = time.time()
            hist.append((now, lc.strip()))
            # remove old
            while hist and now - hist[0][0] > SPAM_WINDOW:
                hist.popleft()
            same = sum(1 for _, c in hist if c == lc.strip() and c)
            flood = len(hist) >= SPAM_LIMIT
            if flood or same >= REPEAT_LIMIT:
                hist.clear()
                try:
                    await message.delete()
                except Exception:
                    pass
                try:
                    until = discord.utils.utcnow() + discord.utils.time_snowflake and None
                    from datetime import timedelta
                    await message.author.timeout(
                        discord.utils.utcnow() + timedelta(seconds=MUTE_SECONDS),
                        reason="AutoMod: spam",
                    )
                    await message.channel.send(
                        f"{message.author.mention} sei stato messo in timeout per **spam** ({MUTE_SECONDS//60} min).",
                        delete_after=8,
                    )
                except Exception:
                    pass
                await _log_action(self.bot, message.guild,
                    action="Spam rilevato", user=message.author, channel=message.channel,
                    reason=("Messaggio ripetuto" if same >= REPEAT_LIMIT else "Flood") +
                           f" → timeout {MUTE_SECONDS//60} min",
                    content=content, color=0x8e44ad)
                return

    # ---------------- Commands ----------------
    @commands.group(name="automod", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def automod(self, ctx):
        am = await _get_automod(ctx.guild.id)
        e = discord.Embed(title="🛡️ AutoMod — Stato", color=0xe74c3c)
        e.add_field(name="Abilitato", value="✅" if am.get("enabled") else "❌")
        e.add_field(name="Blocca link", value="✅" if am.get("block_links") else "❌")
        e.add_field(name="Anti-spam", value="✅" if am.get("block_spam", True) else "❌")
        log_id = am.get("log_channel")
        log_val = f"<#{log_id}>" if log_id else "Non impostato"
        e.add_field(name="Canale log", value=log_val, inline=True)
        bw = am.get("bad_words", [])
        e.add_field(name=f"Parole vietate ({len(bw)})",
                    value=", ".join(bw[:20]) if bw else "Nessuna", inline=False)
        e.set_footer(text=f"{ctx.prefix}automod on|off · links · spam · log #canale · logoff")
        await ctx.send(embed=e)

    @automod.command(name="on")
    @commands.has_permissions(manage_guild=True)
    async def automod_on(self, ctx):
        am = await _get_automod(ctx.guild.id)
        am["enabled"] = True
        await _save_automod(ctx.guild.id, am)
        await ctx.send("🛡️ AutoMod **abilitato**.")

    @automod.command(name="off")
    @commands.has_permissions(manage_guild=True)
    async def automod_off(self, ctx):
        am = await _get_automod(ctx.guild.id)
        am["enabled"] = False
        await _save_automod(ctx.guild.id, am)
        await ctx.send("🛡️ AutoMod **disabilitato**.")

    @automod.command(name="links")
    @commands.has_permissions(manage_guild=True)
    async def automod_links(self, ctx, mode: str):
        am = await _get_automod(ctx.guild.id)
        am["block_links"] = mode.lower() in ("on", "true", "1", "si", "sì")
        await _save_automod(ctx.guild.id, am)
        await ctx.send(f"Blocco link: {'✅ ON' if am['block_links'] else '❌ OFF'}")

    @automod.command(name="spam")
    @commands.has_permissions(manage_guild=True)
    async def automod_spam(self, ctx, mode: str):
        am = await _get_automod(ctx.guild.id)
        am["block_spam"] = mode.lower() in ("on", "true", "1", "si", "sì")
        await _save_automod(ctx.guild.id, am)
        await ctx.send(f"Anti-spam: {'✅ ON' if am['block_spam'] else '❌ OFF'}")

    @automod.command(name="log")
    @commands.has_permissions(manage_guild=True)
    async def automod_log(self, ctx, channel: discord.TextChannel):
        """Imposta il canale di log per le azioni AutoMod."""
        am = await _get_automod(ctx.guild.id)
        am["log_channel"] = channel.id
        await _save_automod(ctx.guild.id, am)
        await ctx.send(f"📋 Canale log AutoMod impostato su {channel.mention}.")
        try:
            await channel.send("✅ Questo canale riceverà d'ora in poi i log AutoMod.")
        except Exception:
            await ctx.send("⚠️ Non riesco a scrivere in quel canale. Controlla i permessi del bot.")

    @automod.command(name="logoff")
    @commands.has_permissions(manage_guild=True)
    async def automod_logoff(self, ctx):
        am = await _get_automod(ctx.guild.id)
        am["log_channel"] = None
        await _save_automod(ctx.guild.id, am)
        await ctx.send("Canale log AutoMod rimosso.")

    @commands.command(name="addbadword")
    @commands.has_permissions(manage_guild=True)
    async def add_badword(self, ctx, *, word: str):
        am = await _get_automod(ctx.guild.id)
        bw = am.get("bad_words", [])
        if word.lower() in [w.lower() for w in bw]:
            return await ctx.send("Parola già presente.")
        bw.append(word.lower())
        am["bad_words"] = bw
        await _save_automod(ctx.guild.id, am)
        try:
            await ctx.message.delete()
        except Exception:
            pass
        await ctx.send(f"Aggiunta parola vietata (nascosta). Totale: {len(bw)}.")

    @commands.command(name="removebadword", aliases=["delbadword"])
    @commands.has_permissions(manage_guild=True)
    async def remove_badword(self, ctx, *, word: str):
        am = await _get_automod(ctx.guild.id)
        bw = am.get("bad_words", [])
        low = word.lower()
        if low not in bw:
            return await ctx.send("Parola non presente.")
        bw.remove(low)
        am["bad_words"] = bw
        await _save_automod(ctx.guild.id, am)
        await ctx.send("Parola rimossa.")

    @commands.command(name="listbadwords")
    @commands.has_permissions(manage_guild=True)
    async def list_badwords(self, ctx):
        am = await _get_automod(ctx.guild.id)
        bw = am.get("bad_words", [])
        if not bw:
            return await ctx.send("Nessuna parola vietata.")
        try:
            await ctx.author.send("Parole vietate:\n" + ", ".join(bw))
            await ctx.send("Lista inviata in DM.")
        except Exception:
            await ctx.send("Non riesco a inviarti DM. Abilitali.")


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
