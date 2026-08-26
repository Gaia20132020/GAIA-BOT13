"""General cog: help, userinfo, serverinfo."""
from discord.ext import commands
from datetime import datetime


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help", aliases=["comandi", "aiuto"])
    async def help_cmd(self, ctx, *, section: str = None):
        p = ctx.prefix
        sections = {
            "moderazione": [
                f"`{p}pex @user @ruolo` - assegna ruolo",
                f"`{p}depex @user @ruolo` - rimuovi ruolo",
                f"`{p}kick @user [motivo]`",
                f"`{p}ban @user [motivo]`",
                f"`{p}unban <id>`",
                f"`{p}timeout @user <minuti>`",
                f"`{p}untimeout @user`",
                f"`{p}warn @user [motivo]`",
                f"`{p}warncount @user`",
                f"`{p}resetwarn @user`",
                f"`{p}leavewarn @user <n>`",
                f"`{p}livelli [@user]`",
                f"`{p}xpadd @user <xp>`",
                f"`{p}messageadd @user <n>`",
                f"`{p}messagecount [@user]`",
                f"`{p}purge <n>`",
                f"`{p}lock` / `{p}unlock`",
            ],
            "automod": [
                f"`{p}automod` - mostra stato",
                f"`{p}automod on|off` - abilita/disabilita",
                f"`{p}automod links on|off` - blocca link",
                f"`{p}automod spam on|off` - anti-spam/flood",
                f"`{p}automod log #canale` - canale log azioni",
                f"`{p}automod logoff` - rimuovi canale log",
                f"`{p}addbadword <parola>` (msg auto-eliminato)",
                f"`{p}removebadword <parola>`",
                f"`{p}listbadwords` - inviata in DM",
            ],
            "economia": [
                f"`{p}balance [@user]`",
                f"`{p}daily`, `{p}work`, `{p}mine`",
                f"`{p}pay @user <n>`",
                f"`{p}add @user <n>` / `{p}remove @user <n>`",
                f"`{p}coinflip testa|croce <bet>`",
                f"`{p}roulette rosso|nero|verde <bet>`",
                f"`{p}tris [bet]`, `{p}blackjack [bet]`",
                f"`{p}leaderboard`",
                f"`{p}shop`, `{p}buy <id>`, `{p}inventory`, `{p}openbox`",
                f"`{p}luckybox` - cassa fortunata gratis (1/giorno, con streak)",
                f"`{p}luckystreak [@user]` - vedi la tua streak",
            ],
            "giochi": [
                f"`{p}8ball <domanda>`",
                f"`{p}say <testo>`",
                f"`{p}ship @a @b`",
                f"`{p}rendigay [@user]`",
                f"`{p}chat <messaggio>` (AI)",
                f"`{p}kiss @user`, `{p}hug @user`, `{p}clap [@user]`",
            ],
            "musica": [
                f"`{p}play <query>` - riproduci brano",
                f"`{p}stop` - ferma e disconnetti",
                f"`{p}playlist` - lista",
                f"`{p}playlist create <nome> <url1> <url2>...`",
                f"`{p}playlist play <nome>`",
                f"`{p}playlist delete <nome>`",
            ],
            "supporto": [
                f"`{p}pannelloticket`",
                f"`{p}close`, `{p}reclama`, `{p}unclaima`, `{p}aggiungi @user`",
                f"`{p}provinostaffcreate`, `{p}provinostaffshow`",
                f"`{p}creategiveaway <durata> <win> <premio>`",
                f"`{p}endgiveaway <id>`, `{p}giveawayreroll <id>`",
                f"`{p}showgiveawaylist`, `{p}showgiveawayid <id>`",
                f"`{p}setwelcome #canale [msg]`",
                f"`{p}setgoodbye #canale [msg]`",
                f"`{p}showinvites [@user]`, `{p}setinviteschannel #canale`",
                f"`{p}resetinvites [@user]`, `{p}addinvites @user <n>`",
                f"`{p}invitebot`, `{p}userinfo`, `{p}serverinfo`",
            ],
        }
        if section and section.lower() in sections:
            k = section.lower()
            e = discord.Embed(title=f"Help — {k.capitalize()}", color=0x5865f2,
                              description="\n".join(sections[k]))
            return await ctx.send(embed=e)
        e = discord.Embed(title=f"📚 Menu Comandi — prefisso `{p}`", color=0x5865f2,
                          description=f"Usa `{p}help <sezione>` per i dettagli.")
        e.add_field(name="🛡️ Moderazione", value=f"`{p}help moderazione`", inline=True)
        e.add_field(name="🚨 AutoMod", value=f"`{p}help automod`", inline=True)
        e.add_field(name="💰 Economia", value=f"`{p}help economia`", inline=True)
        e.add_field(name="🎮 Giochi", value=f"`{p}help giochi`", inline=True)
        e.add_field(name="🎵 Musica", value=f"`{p}help musica`", inline=True)
        e.add_field(name="🎫 Supporto", value=f"`{p}help supporto`", inline=True)
        e.set_footer(text=f"Bot creato con ❤️ | {len(self.bot.guilds)} server")
        await ctx.send(embed=e)

    @commands.command(name="userinfo", aliases=["ui"])
    async def userinfo(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        e = discord.Embed(title=f"Info su {member}", color=member.color)
        e.set_thumbnail(url=member.display_avatar.url)
        e.add_field(name="ID", value=member.id)
        e.add_field(name="Nickname", value=member.display_name)
        e.add_field(name="Bot", value="Sì" if member.bot else "No")
        e.add_field(name="Account creato", value=f"<t:{int(member.created_at.timestamp())}:R>")
        if member.joined_at:
            e.add_field(name="Entrato", value=f"<t:{int(member.joined_at.timestamp())}:R>")
        roles = [r.mention for r in member.roles if r != ctx.guild.default_role]
        e.add_field(name=f"Ruoli ({len(roles)})", value=" ".join(roles[:15]) or "Nessuno", inline=False)
        await ctx.send(embed=e)

    @commands.command(name="serverinfo", aliases=["si"])
    async def serverinfo(self, ctx):
        g = ctx.guild
        e = discord.Embed(title=f"Info su {g.name}", color=0x2ecc71)
        if g.icon:
            e.set_thumbnail(url=g.icon.url)
        e.add_field(name="ID", value=g.id)
        e.add_field(name="Owner", value=str(g.owner))
        e.add_field(name="Membri", value=str(g.member_count))
        e.add_field(name="Canali testo", value=str(len(g.text_channels)))
        e.add_field(name="Canali vocali", value=str(len(g.voice_channels)))
        e.add_field(name="Ruoli", value=str(len(g.roles)))
        e.add_field(name="Creato", value=f"<t:{int(g.created_at.timestamp())}:R>")
        e.add_field(name="Boost", value=f"Livello {g.premium_tier} ({g.premium_subscription_count})")
        await ctx.send(embed=e)


async def setup(bot):
    await bot.add_cog(General(bot))
