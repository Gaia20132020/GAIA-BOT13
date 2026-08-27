"""Games cog."""
import os
import random
import hashlib
import asyncio
import discord
from discord.ext import commands
import google.generativeai as genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="8ball")
    async def eight_ball(self, ctx, *, question: str):
        answers = [
            "Sì, decisamente.", "Certo.", "Molto probabile.", "Direi di sì.",
            "Ne dubito.", "Assolutamente no.", "Non contarci.", "Chiedi più tardi.",
            "Meglio non risponderti ora.", "Le prospettive non sono buone.",
        ]
        await ctx.send(f"🎱 **{ctx.author.display_name}**, {random.choice(answers)}")

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def say(self, ctx, *, text: str):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        await ctx.send(text)

    @commands.command()
    async def ship(self, ctx, member1: discord.Member, member2: discord.Member = None):
        member2 = member2 or ctx.author
        pair = "".join(sorted([str(member1.id), str(member2.id)]))
        pct = int(hashlib.md5(pair.encode()).hexdigest(), 16) % 101
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        name = member1.display_name[:len(member1.display_name)//2] + member2.display_name[len(member2.display_name)//2:]
        e = discord.Embed(title="💘 Ship-o-meter", color=0xe91e63,
                          description=f"**{member1.display_name}** + **{member2.display_name}**\n= **{name}**\n\n`{bar}` **{pct}%**")
        await ctx.send(embed=e)

    @commands.command(name="rendigay", aliases=["rendi_gay", "gay"])
    async def rendi_gay(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        pct = random.randint(0, 100)
        bar = "🏳️‍🌈" * (pct // 10) + "▫️" * (10 - pct // 10)
        await ctx.send(f"**{member.display_name}** è gay al **{pct}%**\n{bar}")

    @commands.command(name="chat", aliases=["ask", "ai"])
    async def chat_with_bot(self, ctx, *, prompt: str):
        if not GEMINI_API_KEY:
            return await ctx.send("Chiave LLM non configurata.")
        async with ctx.typing():
            try:
                def _generate():
                    model = genai.GenerativeModel(
                        model_name="gemini-2.5-flash",
                        system_instruction="Sei un simpatico assistente Discord. Rispondi in italiano, breve e utile."
                    )
                    result = model.generate_content(prompt)
                    return result.text

                text = await asyncio.to_thread(_generate)
                if len(text) > 1900:
                    text = text[:1900] + "..."
                await ctx.send(text)
            except Exception as e:
                await ctx.send(f"Errore AI: {e}")

    async def _action(self, ctx, member: discord.Member, emoji: str, verb: str):
        if member.id == ctx.author.id:
            return await ctx.send(f"Non puoi {verb} te stesso!")
        await ctx.send(f"{emoji} **{ctx.author.display_name}** {verb} **{member.display_name}**!")

    @commands.command()
    async def kiss(self, ctx, member: discord.Member):
        await self._action(ctx, member, "💋", "bacia")

    @commands.command()
    async def hug(self, ctx, member: discord.Member):
        await self._action(ctx, member, "🤗", "abbraccia")

    @commands.command()
    async def clap(self, ctx, member: discord.Member = None):
        if member is None:
            return await ctx.send("👏👏👏")
        await self._action(ctx, member, "👏", "applaude")


async def setup(bot):
    await bot.add_cog(Games(bot))
