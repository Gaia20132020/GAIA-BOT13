"""General cog: help, userinfo, serverinfo."""
2|import discord
3|from discord.ext import commands
4|from datetime import datetime
5|
6|
7|class General(commands.Cog):
8|    def __init__(self, bot):
9|        self.bot = bot
10|
11|    @commands.command(name="help", aliases=["comandi", "aiuto"])
12|    async def help_cmd(self, ctx, *, section: str = None):
13|        p = ctx.prefix
14|        sections = {
15|            "moderazione": [
16|                f"`{p}pex @user @ruolo` - assegna ruolo",
17|                f"`{p}depex @user @ruolo` - rimuovi ruolo",
18|                f"`{p}kick @user [motivo]`",
19|                f"`{p}ban @user [motivo]`",
20|                f"`{p}unban <id>`",
21|                f"`{p}timeout @user <minuti>`",
22|                f"`{p}untimeout @user`",
23|                f"`{p}warn @user [motivo]`",
24|                f"`{p}warncount @user`",
25|                f"`{p}resetwarn @user`",
26|                f"`{p}leavewarn @user <n>`",
27|                f"`{p}livelli [@user]`",
28|                f"`{p}xpadd @user <xp>`",
29|                f"`{p}messageadd @user <n>`",
30|                f"`{p}messagecount [@user]`",
31|                f"`{p}purge <n>`",
32|                f"`{p}lock` / `{p}unlock`",
33|            ],
34|            "automod": [
35|                f"`{p}automod` - mostra stato",
36|                f"`{p}automod on|off` - abilita/disabilita",
37|                f"`{p}automod links on|off` - blocca link",
38|                f"`{p}automod spam on|off` - anti-spam/flood",
39|                f"`{p}automod log #canale` - canale log azioni",
40|                f"`{p}automod logoff` - rimuovi canale log",
41|                f"`{p}addbadword <parola>` (msg auto-eliminato)",
42|                f"`{p}removebadword <parola>`",
43|                f"`{p}listbadwords` - inviata in DM",
44|            ],
45|            "economia": [
46|                f"`{p}balance [@user]`",
47|                f"`{p}daily`, `{p}work`, `{p}mine`",
48|                f"`{p}pay @user <n>`",
49|                f"`{p}add @user <n>` / `{p}remove @user <n>`",
50|                f"`{p}coinflip testa|croce <bet>`",
51|                f"`{p}roulette rosso|nero|verde <bet>`",
52|                f"`{p}tris [bet]`, `{p}blackjack [bet]`",
53|                f"`{p}leaderboard`",
54|                f"`{p}shop`, `{p}buy <id>`, `{p}inventory`, `{p}openbox`",
55|                f"`{p}luckybox` - cassa fortunata gratis (1/giorno, con streak)",
56|                f"`{p}luckystreak [@user]` - vedi la tua streak",
57|            ],
58|            "giochi": [
59|                f"`{p}8ball <domanda>`",
60|                f"`{p}say <testo>`",
61|                f"`{p}ship @a @b`",
62|                f"`{p}rendigay [@user]`",
63|                f"`{p}chat <messaggio>` (AI)",
64|                f"`{p}kiss @user`, `{p}hug @user`, `{p}clap [@user]`",
65|            ],
66|            "musica": [
67|                f"`{p}play <query>` - riproduci brano",
68|                f"`{p}stop` - ferma e disconnetti",
69|                f"`{p}playlist` - lista",
70|                f"`{p}playlist create <nome> <url1> <url2>...`",
71|                f"`{p}playlist play <nome>`",
72|                f"`{p}playlist delete <nome>`",
73|            ],
74|            "supporto": [
75|                f"`{p}pannelloticket`",
76|                f"`{p}close`, `{p}reclama`, `{p}unclaima`, `{p}aggiungi @user`",
77|                f"`{p}provinostaffcreate`, `{p}provinostaffshow`",
78|                f"`{p}creategiveaway <durata> <win> <premio>`",
79|                f"`{p}endgiveaway <id>`, `{p}giveawayreroll <id>`",
80|                f"`{p}showgiveawaylist`, `{p}showgiveawayid <id>`",
81|                f"`{p}setwelcome #canale [msg]`",
82|                f"`{p}setgoodbye #canale [msg]`",
83|                f"`{p}showinvites [@user]`, `{p}setinviteschannel #canale`",
84|                f"`{p}resetinvites [@user]`, `{p}addinvites @user <n>`",
85|                f"`{p}invitebot`, `{p}userinfo`, `{p}serverinfo`",
86|            ],
87|        }
88|        if section and section.lower() in sections:
89|            k = section.lower()
90|            e = discord.Embed(title=f"Help — {k.capitalize()}", color=0x5865f2,
91|                              description="\n".join(sections[k]))
92|            return await ctx.send(embed=e)
93|        e = discord.Embed(title=f"📚 Menu Comandi — prefisso `{p}`", color=0x5865f2,
94|                          description=f"Usa `{p}help <sezione>` per i dettagli.")
95|        e.add_field(name="🛡️ Moderazione", value=f"`{p}help moderazione`", inline=True)
96|        e.add_field(name="🚨 AutoMod", value=f"`{p}help automod`", inline=True)
97|        e.add_field(name="💰 Economia", value=f"`{p}help economia`", inline=True)
98|        e.add_field(name="🎮 Giochi", value=f"`{p}help giochi`", inline=True)
99|        e.add_field(name="🎵 Musica", value=f"`{p}help musica`", inline=True)
100|        e.add_field(name="🎫 Supporto", value=f"`{p}help supporto`", inline=True)
101|        e.set_footer(text=f"Bot creato con ❤️ | {len(self.bot.guilds)} server")
102|        await ctx.send(embed=e)
103|
104|    @commands.command(name="userinfo", aliases=["ui"])
105|    async def userinfo(self, ctx, member: discord.Member = None):
106|        member = member or ctx.author
107|        e = discord.Embed(title=f"Info su {member}", color=member.color)
108|        e.set_thumbnail(url=member.display_avatar.url)
109|        e.add_field(name="ID", value=member.id)
110|        e.add_field(name="Nickname", value=member.display_name)
111|        e.add_field(name="Bot", value="Sì" if member.bot else "No")
112|        e.add_field(name="Account creato", value=f"<t:{int(member.created_at.timestamp())}:R>")
113|        if member.joined_at:
114|            e.add_field(name="Entrato", value=f"<t:{int(member.joined_at.timestamp())}:R>")
115|        roles = [r.mention for r in member.roles if r != ctx.guild.default_role]
116|        e.add_field(name=f"Ruoli ({len(roles)})", value=" ".join(roles[:15]) or "Nessuno", inline=False)
117|        await ctx.send(embed=e)
118|
119|    @commands.command(name="serverinfo", aliases=["si"])
120|    async def serverinfo(self, ctx):
121|        g = ctx.guild
122|        e = discord.Embed(title=f"Info su {g.name}", color=0x2ecc71)
123|        if g.icon:
124|            e.set_thumbnail(url=g.icon.url)
125|        e.add_field(name="ID", value=g.id)
126|        e.add_field(name="Owner", value=str(g.owner))
127|        e.add_field(name="Membri", value=str(g.member_count))
128|        e.add_field(name="Canali testo", value=str(len(g.text_channels)))
129|        e.add_field(name="Canali vocali", value=str(len(g.voice_channels)))
130|        e.add_field(name="Ruoli", value=str(len(g.roles)))
131|        e.add_field(name="Creato", value=f"<t:{int(g.created_at.timestamp())}:R>")
132|        e.add_field(name="Boost", value=f"Livello {g.premium_tier} ({g.premium_subscription_count})")
133|        await ctx.send(embed=e)
134|
135|
136|async def setup(bot):
137|    await bot.add_cog(General(bot))
