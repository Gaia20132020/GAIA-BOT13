"""Economy cog."""
import random
import time
import asyncio
import discord
from discord.ext import commands
import db

CURRENCY = "🪙"
DAILY_COOLDOWN = 60 * 60 * 24
WORK_COOLDOWN = 60 * 30
MINE_COOLDOWN = 60 * 10


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["bal", "money"])
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        u = await db.get_user(ctx.guild.id, member.id)
        e = discord.Embed(title=f"Portafoglio di {member.display_name}", color=0xf1c40f)
        e.add_field(name="Contanti", value=f"{u.get('balance', 0)} {CURRENCY}")
        e.add_field(name="Banca", value=f"{u.get('bank', 0)} {CURRENCY}")
        e.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=e)

    @commands.command()
    async def daily(self, ctx):
        u = await db.get_user(ctx.guild.id, ctx.author.id)
        now = int(time.time())
        if now - u.get("last_daily", 0) < DAILY_COOLDOWN:
            remain = DAILY_COOLDOWN - (now - u.get("last_daily", 0))
            return await ctx.send(f"Torna tra {remain // 3600}h {(remain % 3600) // 60}m.")
        reward = random.randint(200, 500)
        await db.inc_user(ctx.guild.id, ctx.author.id, {"balance": reward})
        await db.update_user(ctx.guild.id, ctx.author.id, {"last_daily": now})
        await ctx.send(f"{ctx.author.mention} ha ricevuto {reward} {CURRENCY} come daily!")

    @commands.command()
    async def work(self, ctx):
        u = await db.get_user(ctx.guild.id, ctx.author.id)
        now = int(time.time())
        if now - u.get("last_work", 0) < WORK_COOLDOWN:
            remain = WORK_COOLDOWN - (now - u.get("last_work", 0))
            return await ctx.send(f"Sei stanco. Riposa {remain // 60}m.")
        jobs = ["programmatore", "medico", "cuoco", "youtuber", "streamer", "pilota"]
        earn = random.randint(50, 250)
        await db.inc_user(ctx.guild.id, ctx.author.id, {"balance": earn})
        await db.update_user(ctx.guild.id, ctx.author.id, {"last_work": now})
        await ctx.send(f"Hai lavorato come {random.choice(jobs)} e guadagnato {earn} {CURRENCY}!")

    @commands.command()
    async def mine(self, ctx):
        u = await db.get_user(ctx.guild.id, ctx.author.id)
        now = int(time.time())
        if now - u.get("last_mine", 0) < MINE_COOLDOWN:
            remain = MINE_COOLDOWN - (now - u.get("last_mine", 0))
            return await ctx.send(f"Aspetta {remain // 60}m {remain % 60}s prima di riminare.")
        gems = [("carbone", 10, 40), ("ferro", 40, 100), ("oro", 100, 250), ("diamante", 250, 600)]
        bonus = 2 if "pickaxe" in [i.get("id") for i in u.get("inventory", [])] else 1
        gem = random.choices(gems, weights=[50, 30, 15, 5])[0]
        earn = random.randint(gem[1], gem[2]) * bonus
        await db.inc_user(ctx.guild.id, ctx.author.id, {"balance": earn})
        await db.update_user(ctx.guild.id, ctx.author.id, {"last_mine": now})
        await ctx.send(f"{ctx.author.mention} ha estratto **{gem[0]}** e guadagnato {earn} {CURRENCY}!")

    @commands.command()
    async def pay(self, ctx, member: discord.Member, amount: int):
        if member == ctx.author or member.bot:
            return await ctx.send("Non puoi pagare te stesso o un bot.")
        if amount <= 0:
            return await ctx.send("Importo non valido.")
        u = await db.get_user(ctx.guild.id, ctx.author.id)
        if u.get("balance", 0) < amount:
            return await ctx.send("Fondi insufficienti.")
        await db.inc_user(ctx.guild.id, ctx.author.id, {"balance": -amount})
        await db.inc_user(ctx.guild.id, member.id, {"balance": amount})
        await ctx.send(f"{ctx.author.mention} ha pagato {amount} {CURRENCY} a {member.mention}.")

    @commands.command(name="add")
    @commands.has_permissions(administrator=True)
    async def add_money(self, ctx, member: discord.Member, amount: int):
        await db.inc_user(ctx.guild.id, member.id, {"balance": amount})
        await ctx.send(f"Aggiunti {amount} {CURRENCY} a {member.mention}.")

    @commands.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def remove_money(self, ctx, member: discord.Member, amount: int):
        await db.inc_user(ctx.guild.id, member.id, {"balance": -amount})
        await ctx.send(f"Rimossi {amount} {CURRENCY} a {member.mention}.")

    @commands.command()
    async def coinflip(self, ctx, choice: str, bet: int):
        choice = choice.lower()
        if choice not in ("testa", "croce"):
            return await ctx.send("Scegli `testa` o `croce`.")
        if bet <= 0:
            return await ctx.send("Puntata non valida.")
        u = await db.get_user(ctx.guild.id, ctx.author.id)
        if u.get("balance", 0) < bet:
            return await ctx.send("Fondi insufficienti.")
        result = random.choice(["testa", "croce"])
        if result == choice:
            await db.inc_user(ctx.guild.id, ctx.author.id, {"balance": bet})
            await ctx.send(f"È uscito **{result}**! Vinci {bet} {CURRENCY}.")
        else:
            await db.inc_user(ctx.guild.id, ctx.author.id, {"balance": -bet})
            await ctx.send(f"È uscito **{result}**. Hai perso {bet} {CURRENCY}.")

    @commands.command()
    async def roulette(self, ctx, color: str, bet: int):
        color = color.lower()
        if color not in ("rosso", "nero", "verde"):
            return await ctx.send("Colori: `rosso`, `nero`, `verde`.")
        u = await db.get_user(ctx.guild.id, ctx.author.id)
        if u.get("balance", 0) < bet or bet <= 0:
            return await ctx.send("Puntata non valida o fondi insufficienti.")
        result = random.choices(["rosso", "nero", "verde"], weights=[18, 18, 2])[0]
        mult = 14 if color == "verde" else 2
        if result == color:
            win = bet * (mult - 1)
            await db.inc_user(ctx.guild.id, ctx.author.id, {"balance": win})
            await ctx.send(f"Pallina su **{result}**! Vinci {win} {CURRENCY}.")
        else:
            await db.inc_user(ctx.guild.id, ctx.author.id, {"balance": -bet})
            await ctx.send(f"Pallina su **{result}**. Hai perso {bet} {CURRENCY}.")

    @commands.command()
    async def tris(self, ctx, bet: int = 100):
        u = await db.get_user(ctx.guild.id, ctx.author.id)
        if u.get("balance", 0) < bet or bet <= 0:
            return await ctx.send("Puntata non valida o fondi insufficienti.")
        board = [" "] * 9
        def render():
            rows = []
            for i in range(0, 9, 3):
                rows.append(" | ".join(c if c != " " else str(i + j + 1) for j, c in enumerate(board[i:i+3])))
            return "\n---------\n".join(rows)
        def winner(p):
            wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
            return any(all(board[i]==p for i in w) for w in wins)
        await ctx.send(f"Tris! Tu sei X. Scrivi la casella (1-9). Puntata: {bet} {CURRENCY}\n```\n{render()}\n```")
        for _ in range(9):
            if all(c != " " for c in board):
                break
            try:
                msg = await self.bot.wait_for("message", timeout=60,
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content.strip().isdigit())
            except asyncio.TimeoutError:
                return await ctx.send("Tempo scaduto.")
            pos = int(msg.content) - 1
            if not (0 <= pos < 9) or board[pos] != " ":
                await ctx.send("Casella non valida.")
                continue
            board[pos] = "X"
            if winner("X"):
                await db.inc_user(ctx.guild.id, ctx.author.id, {"balance": bet})
                return await ctx.send(f"```\n{render()}\n```\nHai vinto! +{bet} {CURRENCY}")
            empty = [i for i, c in enumerate(board) if c == " "]
            if not empty:
                break
            board[random.choice(empty)] = "O"
            if winner("O"):
                await db.inc_user(ctx.guild.id, ctx.author.id, {"balance": -bet})
                return await ctx.send(f"```\n{render()}\n```\nHai perso. -{bet} {CURRENCY}")
            await ctx.send(f"```\n{render()}\n```")
        await ctx.send(f"```\n{render()}\n```\nPareggio.")

    @commands.command()
    async def blackjack(self, ctx, bet: int = 100):
        u = await db.get_user(ctx.guild.id, ctx.author.id)
        if u.get("balance", 0) < bet or bet <= 0:
            return await ctx.send("Puntata non valida o fondi insufficienti.")
        deck = [v for v in [2,3,4,5,6,7,8,9,10,10,10,10,11] for _ in range(4)]
        random.shuffle(deck)
        player = [deck.pop(), deck.pop()]
        dealer = [deck.pop(), deck.pop()]
        def score(h):
            s = sum(h); aces = h.count(11)
            while s > 21 and aces:
                s -= 10; aces -= 1
            return s
        await ctx.send(f"Le tue carte: {player} = {score(player)} | Dealer mostra: {dealer[0]}\nRispondi `hit` o `stand`.")
        while score(player) < 21:
            try:
                msg = await self.bot.wait_for("message", timeout=45,
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ("hit", "stand"))
            except asyncio.TimeoutError:
                return await ctx.send("Tempo scaduto.")
            if msg.content.lower() == "stand":
                break
            player.append(deck.pop())
            await ctx.send(f"Le tue carte: {player} = {score(player)}")
        if score(player) > 21:
            await db.inc_user(ctx.guild.id, ctx.author.id, {"balance": -bet})
            return await ctx.send(f"Bust! Perdi {bet} {CURRENCY}.")
        while score(dealer) < 17:
            dealer.append(deck.pop())
        ps, ds = score(player), score(dealer)
        if ds > 21 or ps > ds:
            await db.inc_user(ctx.guild.id, ctx.author.id, {"balance": bet})
            await ctx.send(f"Dealer: {dealer} = {ds}. Vinci {bet} {CURRENCY}!")
        elif ps == ds:
            await ctx.send(f"Dealer: {dealer} = {ds}. Pareggio.")
        else:
            await db.inc_user(ctx.guild.id, ctx.author.id, {"balance": -bet})
            await ctx.send(f"Dealer: {dealer} = {ds}. Perdi {bet} {CURRENCY}.")

    @commands.command(aliases=["lb", "top"])
    async def leaderboard(self, ctx):
        docs = await db.users.find({"guild_id": ctx.guild.id}).sort("balance", -1).to_list(length=10)
        e = discord.Embed(title=f"Top 10 Ricchi - {ctx.guild.name}", color=0xf1c40f)
        lines = []
        for i, u in enumerate(docs, 1):
            m = ctx.guild.get_member(u["user_id"])
            name = m.display_name if m else f"User {u['user_id']}"
            lines.append(f"**{i}.** {name} — {u.get('balance', 0)} {CURRENCY}")
        e.description = "\n".join(lines) or "Nessuno."
        await ctx.send(embed=e)

    @commands.command()
    async def shop(self, ctx):
        e = discord.Embed(title="Negozio", color=0x2ecc71)
        for item in db.shop_items_default:
            e.add_field(name=f"{item['name']} — {item['price']} {CURRENCY}",
                        value=f"`{item['id']}` — {item['desc']}", inline=False)
        e.set_footer(text=f"Compra con {ctx.prefix}buy <id>")
        await ctx.send(embed=e)

    @commands.command(name="buy")
    async def buy(self, ctx, item_id: str):
        item = next((i for i in db.shop_items_default if i["id"] == item_id.lower()), None)
        if not item:
            return await ctx.send("Oggetto non trovato.")
        u = await db.get_user(ctx.guild.id, ctx.author.id)
        if u.get("balance", 0) < item["price"]:
            return await ctx.send("Fondi insufficienti.")
        inv = u.get("inventory", [])
        inv.append({"id": item["id"], "name": item["name"]})
        await db.update_user(ctx.guild.id, ctx.author.id, {"inventory": inv})
        await db.inc_user(ctx.guild.id, ctx.author.id, {"balance": -item["price"]})
        await ctx.send(f"Hai comprato {item['name']}!")

    @commands.command()
    async def inventory(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        u = await db.get_user(ctx.guild.id, member.id)
        inv = u.get("inventory", [])
        e = discord.Embed(title=f"Inventario di {member.display_name}", color=0x3498db)
        if not inv:
            e.description = "Vuoto."
        else:
            from collections import Counter
            counts = Counter(i["id"] for i in inv)
            e.description = "\n".join(f"**{cid}** x{c}" for cid, c in counts.items())
        await ctx.send(embed=e)

    @commands.command(name="luckybox", aliases=["lucky", "dailybox"])
    async def luckybox(self, ctx):
        u = await db.get_user(ctx.guild.id, ctx.author.id)
        now = int(time.time())
        last = u.get("last_luckybox", 0)
        streak = u.get("luckybox_streak", 0)
        best = u.get("luckybox_best_streak", 0)
        if now - last < DAILY_COOLDOWN:
            remain = DAILY_COOLDOWN - (now - last)
            return await ctx.send(f"🎁 Cassa già aperta oggi (streak: **{streak}** 🔥). Torna tra {remain // 3600}h {(remain % 3600) // 60}m.")
        if last and now - last <= DAILY_COOLDOWN * 2:
            streak += 1
        else:
            streak = 1
        best = max(best, streak)
        mult_table = [1.0, 1.1, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]
        mult = mult_table[min(streak - 1, len(mult_table) - 1)]
        rarities = [
            ("Comune", "⚪", 55, 100, 400, None),
            ("Non Comune", "🟢", 25, 400, 900, None),
            ("Raro", "🔵", 12, 900, 2000, None),
            ("Epico", "🟣", 6, 2000, 4500, "box"),
            ("Leggendario", "🟡", 2, 4500, 10000, "crown"),
        ]
        weights = [r[2] for r in rarities]
        pick = random.choices(rarities, weights=weights, k=1)[0]
        label, icon, _, cmin, cmax, bonus = pick
        base = random.randint(cmin, cmax)
        coins = int(base * mult)
        milestone_bonus = None
        if streak > 0 and streak % 7 == 0:
            milestone_bonus = "crown"
        elif streak > 0 and streak % 3 == 0:
            milestone_bonus = "box"
        await db.inc_user(ctx.guild.id, ctx.author.id, {"balance": coins})
        await db.update_user(ctx.guild.id, ctx.author.id, {
            "last_luckybox": now, "luckybox_streak": streak, "luckybox_best_streak": best,
        })
        extra_lines = []
        u2 = await db.get_user(ctx.guild.id, ctx.author.id)
        inv = u2.get("inventory", [])
        if bonus:
            item = next((i for i in db.shop_items_default if i["id"] == bonus), None)
            if item:
                inv.append({"id": item["id"], "name": item["name"]})
                extra_lines.append(f"🎁 Bonus rarità: **{item['name']}**")
        if milestone_bonus:
            item = next((i for i in db.shop_items_default if i["id"] == milestone_bonus), None)
            if item:
                inv.append({"id": item["id"], "name": item["name"]})
                extra_lines.append(f"🏆 Bonus streak {streak}: **{item['name']}**")
        if bonus or milestone_bonus:
            await db.update_user(ctx.guild.id, ctx.author.id, {"inventory": inv})
        e = discord.Embed(
            title=f"{icon} Cassa Fortunata — {label}",
            description=f"{ctx.author.mention} ha trovato **{coins} {CURRENCY}**" +
                        (f" (base {base} × {mult:g})" if mult != 1.0 else "") + "!" +
                        ("\n" + "\n".join(extra_lines) if extra_lines else ""),
            color=0xf1c40f if label != "Leggendario" else 0xffd700,
        )
        e.add_field(name="🔥 Streak", value=f"**{streak}** giorni", inline=True)
        e.add_field(name="🏅 Record", value=f"**{best}** giorni", inline=True)
        e.add_field(name="✖️ Molt.", value=f"×{mult:g}", inline=True)
        if streak < len(mult_table):
            e.set_footer(text=f"Domani: ×{mult_table[streak]:g}!")
        else:
            e.set_footer(text=f"Sei al moltiplicatore massimo (×{mult_table[-1]:g})!")
        await ctx.send(embed=e)

    @commands.command(name="luckystreak", aliases=["streak"])
    async def lucky_streak(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        u = await db.get_user(ctx.guild.id, member.id)
        streak = u.get("luckybox_streak", 0)
        best = u.get("luckybox_best_streak", 0)
        last = u.get("last_luckybox", 0)
        now = int(time.time())
        status = "Attiva 🔥" if last and (now - last) <= DAILY_COOLDOWN * 2 else "Spezzata ❌"
        e = discord.Embed(title=f"🔥 Streak di {member.display_name}", color=0xff6b35)
        e.add_field(name="Streak attuale", value=str(streak))
        e.add_field(name="Record personale", value=str(best))
        e.add_field(name="Stato", value=status, inline=False)
        await ctx.send(embed=e)

    @commands.command(name="openbox", aliases=["open_box", "open"])
    async def openbox(self, ctx):
        u = await db.get_user(ctx.guild.id, ctx.author.id)
        inv = u.get("inventory", [])
        box_index = next((i for i, it in enumerate(inv) if it["id"] == "box"), None)
        if box_index is None:
            return await ctx.send("Non hai nessuna Cassa Misteriosa nell'inventario.")
        inv.pop(box_index)
        reward = random.randint(500, 3000)
        await db.update_user(ctx.guild.id, ctx.author.id, {"inventory": inv})
        await db.inc_user(ctx.guild.id, ctx.author.id, {"balance": reward})
        await ctx.send(f"Hai aperto la cassa e trovato {reward} {CURRENCY}!")


async def setup(bot):
    await bot.add_cog(Economy(bot))
