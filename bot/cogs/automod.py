1|"""AutoMod cog: banned words, link blocking, anti-spam (repeated messages / flood).
2|
3|Commands (require manage_guild):
4|- !automod          -> mostra stato
5|- !automod on|off   -> abilita/disabilita l'automod
6|- !automod links on|off
7|- !automod spam on|off
8|- !addbadword <parola>
9|- !removebadword <parola>
10|- !listbadwords
11|"""
12|import time
13|import re
14|from collections import defaultdict, deque
15|import discord
16|from discord.ext import commands
17|import db
18|
19|
20|LINK_RE = re.compile(r"https?://\S+|discord\.gg/\S+", re.IGNORECASE)
21|
22|# In-memory sliding window for spam detection
23|# key = (guild_id, user_id) -> deque of (timestamp, content)
24|_msg_history: dict[tuple, deque] = defaultdict(lambda: deque(maxlen=8))
25|
26|SPAM_WINDOW = 6      # seconds
27|SPAM_LIMIT = 5       # messages in window -> spam
28|REPEAT_LIMIT = 3     # same content N times -> spam
29|MUTE_SECONDS = 300   # 5-minute timeout on spam
30|
31|
32|async def _get_automod(guild_id: int) -> dict:
33|    cfg = await db.get_guild_config(guild_id)
34|    return cfg.get("automod", {
35|        "enabled": False,
36|        "block_links": False,
37|        "block_spam": True,
38|        "bad_words": [],
39|    })
40|
41|
42|async def _save_automod(guild_id: int, am: dict):
43|    await db.guild_config.update_one(
44|        {"guild_id": guild_id},
45|        {"$set": {"automod": am}},
46|        upsert=True,
47|    )
48|
49|
50|async def _log_action(bot, guild: discord.Guild, *, action: str, user: discord.Member,
51|                      channel: discord.TextChannel, reason: str, content: str = "",
52|                      color: int = 0xe74c3c):
53|    """Send an automod action to the configured log channel (if any)."""
54|    am = await _get_automod(guild.id)
55|    log_id = am.get("log_channel")
56|    if not log_id:
57|        return
58|    log_ch = guild.get_channel(log_id)
59|    if not log_ch:
60|        return
61|    e = discord.Embed(title=f"🛡️ AutoMod — {action}", color=color, timestamp=discord.utils.utcnow())
62|    e.add_field(name="Utente", value=f"{user.mention} (`{user.id}`)", inline=True)
63|    e.add_field(name="Canale", value=channel.mention, inline=True)
64|    e.add_field(name="Motivo", value=reason, inline=False)
65|    if content:
66|        snippet = content if len(content) <= 500 else content[:500] + "..."
67|        e.add_field(name="Messaggio", value=f"```{snippet}```", inline=False)
68|    e.set_thumbnail(url=user.display_avatar.url)
69|    try:
70|        await log_ch.send(embed=e)
71|    except Exception:
72|        pass
73|
74|
75|class AutoMod(commands.Cog):
76|    def __init__(self, bot):
77|        self.bot = bot
78|
79|    # ---------------- Listener ----------------
80|    @commands.Cog.listener()
81|    async def on_message(self, message: discord.Message):
82|        if message.author.bot or not message.guild:
83|            return
84|        # Skip staff (manage_messages)
85|        if message.author.guild_permissions.manage_messages:
86|            return
87|
88|        am = await _get_automod(message.guild.id)
89|        if not am.get("enabled"):
90|            return
91|
92|        content = message.content or ""
93|        lc = content.lower()
94|
95|        # --- Bad words ---
96|        for w in am.get("bad_words", []):
97|            if w and w.lower() in lc:
98|                try:
99|                    await message.delete()
100|                except Exception:
101|                    pass
102|                try:
103|                    await message.channel.send(
104|                        f"{message.author.mention} parola vietata rilevata. Messaggio rimosso.",
105|                        delete_after=6,
106|                    )
107|                except Exception:
108|                    pass
109|                await db.warns.insert_one({
110|                    "guild_id": message.guild.id, "user_id": message.author.id,
111|                    "mod_id": self.bot.user.id, "reason": f"AutoMod: parola vietata ({w})",
112|                    "ts": time.time(),
113|                })
114|                await _log_action(self.bot, message.guild,
115|                    action="Parola vietata", user=message.author, channel=message.channel,
116|                    reason=f"Parola bloccata: `{w}`", content=content, color=0xe74c3c)
117|                return
118|
119|        # --- Links ---
120|        if am.get("block_links") and LINK_RE.search(content):
121|            try:
122|                await message.delete()
123|            except Exception:
124|                pass
125|            try:
126|                await message.channel.send(
127|                    f"{message.author.mention} i link non sono permessi qui.",
128|                    delete_after=6,
129|                )
130|            except Exception:
131|                pass
132|            await _log_action(self.bot, message.guild,
133|                action="Link bloccato", user=message.author, channel=message.channel,
134|                reason="Link non permesso", content=content, color=0xf39c12)
135|            return
136|
137|        # --- Spam / flood ---
138|        if am.get("block_spam", True):
139|            key = (message.guild.id, message.author.id)
140|            hist = _msg_history[key]
141|            now = time.time()
142|            hist.append((now, lc.strip()))
143|            # remove old
144|            while hist and now - hist[0][0] > SPAM_WINDOW:
145|                hist.popleft()
146|            same = sum(1 for _, c in hist if c == lc.strip() and c)
147|            flood = len(hist) >= SPAM_LIMIT
148|            if flood or same >= REPEAT_LIMIT:
149|                hist.clear()
150|                try:
151|                    await message.delete()
152|                except Exception:
153|                    pass
154|                try:
155|                    until = discord.utils.utcnow() + discord.utils.time_snowflake and None
156|                    from datetime import timedelta
157|                    await message.author.timeout(
158|                        discord.utils.utcnow() + timedelta(seconds=MUTE_SECONDS),
159|                        reason="AutoMod: spam",
160|                    )
161|                    await message.channel.send(
162|                        f"{message.author.mention} sei stato messo in timeout per **spam** ({MUTE_SECONDS//60} min).",
163|                        delete_after=8,
164|                    )
165|                except Exception:
166|                    pass
167|                await _log_action(self.bot, message.guild,
168|                    action="Spam rilevato", user=message.author, channel=message.channel,
169|                    reason=("Messaggio ripetuto" if same >= REPEAT_LIMIT else "Flood") +
170|                           f" → timeout {MUTE_SECONDS//60} min",
171|                    content=content, color=0x8e44ad)
172|                return
173|
174|    # ---------------- Commands ----------------
175|    @commands.group(name="automod", invoke_without_command=True)
176|    @commands.has_permissions(manage_guild=True)
177|    async def automod(self, ctx):
178|        am = await _get_automod(ctx.guild.id)
179|        e = discord.Embed(title="🛡️ AutoMod — Stato", color=0xe74c3c)
180|        e.add_field(name="Abilitato", value="✅" if am.get("enabled") else "❌")
181|        e.add_field(name="Blocca link", value="✅" if am.get("block_links") else "❌")
182|        e.add_field(name="Anti-spam", value="✅" if am.get("block_spam", True) else "❌")
183|        log_id = am.get("log_channel")
184|        log_val = f"<#{log_id}>" if log_id else "Non impostato"
185|        e.add_field(name="Canale log", value=log_val, inline=True)
186|        bw = am.get("bad_words", [])
187|        e.add_field(name=f"Parole vietate ({len(bw)})",
188|                    value=", ".join(bw[:20]) if bw else "Nessuna", inline=False)
189|        e.set_footer(text=f"{ctx.prefix}automod on|off · links · spam · log #canale · logoff")
190|        await ctx.send(embed=e)
191|
192|    @automod.command(name="on")
193|    @commands.has_permissions(manage_guild=True)
194|    async def automod_on(self, ctx):
195|        am = await _get_automod(ctx.guild.id)
196|        am["enabled"] = True
197|        await _save_automod(ctx.guild.id, am)
198|        await ctx.send("🛡️ AutoMod **abilitato**.")
199|
200|    @automod.command(name="off")
201|    @commands.has_permissions(manage_guild=True)
202|    async def automod_off(self, ctx):
203|        am = await _get_automod(ctx.guild.id)
204|        am["enabled"] = False
205|        await _save_automod(ctx.guild.id, am)
206|        await ctx.send("🛡️ AutoMod **disabilitato**.")
207|
208|    @automod.command(name="links")
209|    @commands.has_permissions(manage_guild=True)
210|    async def automod_links(self, ctx, mode: str):
211|        am = await _get_automod(ctx.guild.id)
212|        am["block_links"] = mode.lower() in ("on", "true", "1", "si", "sì")
213|        await _save_automod(ctx.guild.id, am)
214|        await ctx.send(f"Blocco link: {'✅ ON' if am['block_links'] else '❌ OFF'}")
215|
216|    @automod.command(name="spam")
217|    @commands.has_permissions(manage_guild=True)
218|    async def automod_spam(self, ctx, mode: str):
219|        am = await _get_automod(ctx.guild.id)
220|        am["block_spam"] = mode.lower() in ("on", "true", "1", "si", "sì")
221|        await _save_automod(ctx.guild.id, am)
222|        await ctx.send(f"Anti-spam: {'✅ ON' if am['block_spam'] else '❌ OFF'}")
223|
224|    @automod.command(name="log")
225|    @commands.has_permissions(manage_guild=True)
226|    async def automod_log(self, ctx, channel: discord.TextChannel):
227|        """Imposta il canale di log per le azioni AutoMod."""
228|        am = await _get_automod(ctx.guild.id)
229|        am["log_channel"] = channel.id
230|        await _save_automod(ctx.guild.id, am)
231|        await ctx.send(f"📋 Canale log AutoMod impostato su {channel.mention}.")
232|        try:
233|            await channel.send("✅ Questo canale riceverà d'ora in poi i log AutoMod.")
234|        except Exception:
235|            await ctx.send("⚠️ Non riesco a scrivere in quel canale. Controlla i permessi del bot.")
236|
237|    @automod.command(name="logoff")
238|    @commands.has_permissions(manage_guild=True)
239|    async def automod_logoff(self, ctx):
240|        am = await _get_automod(ctx.guild.id)
241|        am["log_channel"] = None
242|        await _save_automod(ctx.guild.id, am)
243|        await ctx.send("Canale log AutoMod rimosso.")
244|
245|    @commands.command(name="addbadword")
246|    @commands.has_permissions(manage_guild=True)
247|    async def add_badword(self, ctx, *, word: str):
248|        am = await _get_automod(ctx.guild.id)
249|        bw = am.get("bad_words", [])
250|        if word.lower() in [w.lower() for w in bw]:
251|            return await ctx.send("Parola già presente.")
252|        bw.append(word.lower())
253|        am["bad_words"] = bw
254|        await _save_automod(ctx.guild.id, am)
255|        try:
256|            await ctx.message.delete()
257|        except Exception:
258|            pass
259|        await ctx.send(f"Aggiunta parola vietata (nascosta). Totale: {len(bw)}.")
260|
261|    @commands.command(name="removebadword", aliases=["delbadword"])
262|    @commands.has_permissions(manage_guild=True)
263|    async def remove_badword(self, ctx, *, word: str):
264|        am = await _get_automod(ctx.guild.id)
265|        bw = am.get("bad_words", [])
266|        low = word.lower()
267|        if low not in bw:
268|            return await ctx.send("Parola non presente.")
269|        bw.remove(low)
270|        am["bad_words"] = bw
271|        await _save_automod(ctx.guild.id, am)
272|        await ctx.send("Parola rimossa.")
273|
274|    @commands.command(name="listbadwords")
275|    @commands.has_permissions(manage_guild=True)
276|    async def list_badwords(self, ctx):
277|        am = await _get_automod(ctx.guild.id)
278|        bw = am.get("bad_words", [])
279|        if not bw:
280|            return await ctx.send("Nessuna parola vietata.")
281|        try:
282|            await ctx.author.send("Parole vietate:\n" + ", ".join(bw))
283|            await ctx.send("Lista inviata in DM.")
284|        except Exception:
285|            await ctx.send("Non riesco a inviarti DM. Abilitali.")
286|
287|
288|async def setup(bot):
289|    await bot.add_cog(AutoMod(bot))
290|
