# created for TheArxOfTheNel#4007, Minion_Kadin#2022 and Sasiko#1234 (discord)

import discord
from discord.ext import commands, tasks
from datetime import datetime
from pytz import timezone
from core import checks
from core.checks import PermissionLevel
from core.models import DMDisabled

class TicketStats(commands.Cog):
    """Shows the current status of tickets"""
    def __init__(self, bot):
        self.bot = bot
        self.db = self.bot.plugin_db.get_partition(self)
        self.tickets_backlog = int()
        self.tickets_open = int()
        self.tickets_24hrs = int()
        self.tickets_lifetime = int()
        self.daily_reset = bool()
        self.activity = bool()
        self.status_group = dict()
        self.status_msg = list()
        self.task = self.bot.loop.create_task(self.cog_load())

    async def dm_status(self):
        if self.bot.config["dm_disabled"] == DMDisabled.ALL_THREADS:
            if self.activity:
                await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=f"All DM's Disabled"))
            return "Status: __**All Tickets Disabled**__"
        elif self.bot.config["dm_disabled"] == DMDisabled.NEW_THREADS:
            if self.activity:
                await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=f"New DM's Disabled"))
            return "Status: __**New Tickets Disabled**__"
        elif self.tickets_open > self.tickets_backlog:
            if self.activity:
                await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=f"Backlogged (expect slow response)"))
            return "Status: __**Backlogged!**__ (Expect slow response)"
        else:
            if self.activity:
                await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=f"Normal (accepting new DM's)"))
            return "Status: __**Normal**__ (Accepting new tickets)"

    async def cog_load(self):
        config = await self.db.find_one({"_id": "config"})
        if config is None:
            await self.db.find_one_and_update({"_id": "config"},
                {"$set": {
                    "backlog": 5,
                    "open": int(),
                    "24hrs": int(),
                    "lifetime": int(),
                    "daily_reset": True,
                    "activity": False,
                    "msg": dict()}
                }, upsert=True)

            config = await self.db.find_one({"_id": "config"})

        self.tickets_backlog = config.get("backlog", int())
        self.tickets_open = config.get("open", int())
        self.tickets_24hrs = config.get("24hrs", int())
        self.tickets_lifetime = config.get("lifetime", int())
        self.daily_reset = config.get("daily_reset", bool())
        self.activity = config.get("activity", bool())
        self.status_group = config.get("msg", dict())

        logs = self.bot.db.logs

        if self.tickets_open == 0:
            opened = await logs.find({"open": True}).to_list(None)
            self.tickets_open == len(opened)

        if self.tickets_lifetime == 0:
            closed = await logs.find({"open": False}).to_list(None)
            self.tickets_lifetime == len(closed)

        embed = discord.Embed(title='Tickets Statistics', color=self.bot.main_color)
        embed.add_field(name='Open Tickets', value=self.tickets_open, inline=False)
        embed.add_field(name='Resolved - 24hrs', value=self.tickets_24hrs, inline=False)
        embed.add_field(name='Resolved - Lifetime', value=self.tickets_lifetime, inline=False)
        embed.description = await self.dm_status()

        if len(self.status_group) != 0:
            for k, v in self.status_group.items():
                try:
                    update_channel = self.bot.guild.get_channel(int(k)) or await self.bot.fetch_channel(int(k))
                    if update_channel:
                        if v:
                            status_msg = await update_channel.fetch_message(int(v))
                            self.status_msg.append(status_msg)
                        else:
                            status_msg = await update_channel.send(embed=embed)
                            self.status_msg.append(status_msg)
                            self.status_group[str(update_channel.id)] = status_msg.id
                            await self._update_config()
                except:
                    pass

            embed = self.status_msg[0].embeds[0]
            embed.set_field_at(index=0, name='Open Tickets', value=self.tickets_open, inline=False)
            embed.set_field_at(index=1, name='Resolved - 24hrs', value=self.tickets_24hrs, inline=False)
            embed.set_field_at(index=2, name='Resolved - Lifetime', value=self.tickets_lifetime, inline=False)
            embed.description = await self.dm_status()

            for m in self.status_msg:
                try:
                    await m.edit(embed=embed)
                except:
                    pass

        else:
            update_channel: discord.Channel = await self.bot.guild.create_text_channel('Tickets Statistics', topic='Tickets Stats', category=self.bot.main_category, overwrites={
                self.bot.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                self.bot.guild.default_role: discord.PermissionOverwrite(read_messages=True, read_message_history=True, send_messages=False)
            })

            status_msg = await update_channel.send(embed=embed)
            self.status_msg.append(status_msg)
            self.status_group = {str(update_channel.id):self.status_msg.id}
            await self._update_config()

        self.reset_daily.start()

    async def _update_config(self):
        await self.db.find_one_and_update({"_id": "config"},
            {"$set": {
                "open": self.tickets_open,
                "backlog": self.tickets_backlog,
                "24hrs": self.tickets_24hrs,
                "lifetime": self.tickets_lifetime,
                "daily_reset": self.daily_reset,
                "activity": self.activity,
                "msg": self.status_group}
            }, upsert=True)

    def cog_unload(self):
        self.task.cancel()
        self.reset_daily.cancel()

    @commands.Cog.listener()
    async def on_command(self, ctx):
        if ctx.command.qualified_name in ['close', 'disable new', 'disable all', 'enable'] and await ctx.command.can_run(ctx):
            if ctx.command.qualified_name == 'close':
                self.tickets_open = self.tickets_open-1
                self.tickets_24hrs = self.tickets_24hrs+1
                self.tickets_lifetime = self.tickets_lifetime+1
                await self._update_config()

            embed = self.status_msg[0].embeds[0]
            embed.set_field_at(index=0, name='Open Tickets', value=self.tickets_open, inline=False)
            embed.set_field_at(index=1, name='Resolved - 24hrs', value=self.tickets_24hrs, inline=False)
            embed.set_field_at(index=2, name='Resolved - Lifetime', value=self.tickets_lifetime, inline=False)
            embed.description = await self.dm_status()

            for m in self.status_msg:
                try:
                    await m.edit(embed=embed)
                except:
                    pass

    @commands.Cog.listener()
    async def on_thread_ready(self, thread, creator, category, initial_message):
        self.tickets_open = self.tickets_open+1
        await self._update_config()
        embed = self.status_msg[0].embeds[0]
        embed.set_field_at(index=0, name='Open Tickets', value=self.tickets_open, inline=False)
        embed.description = await self.dm_status()

        for m in self.status_msg:
            try:
                await m.edit(embed=embed)
            except:
                pass

    @tasks.loop(minutes=59)
    async def reset_daily(self):
        hours = int(datetime.now(timezone("Asia/Kolkata")).time().strftime("%H"))

        if hours == 0 and self.daily_reset:
            self.tickets_24hrs = 0

            embed = self.status_msg[0].embeds[0]
            embed.set_field_at(index=1, name='Resolved - 24hrs', value='0', inline=False)
            for m in self.status_msg:
                try:
                    await m.edit(embed=embed)
                except:
                    pass

            self.daily_reset = False
            await self._update_config()

        if hours != 0 and not self.daily_reset:
            self.daily_reset = True
            await self._update_config()

    @reset_daily.before_loop
    async def before_reset_daily(self):
      await self.bot.wait_until_ready()  

    @checks.has_permissions(PermissionLevel.ADMIN)
    @commands.group(name='ticketstats', invoke_without_command=True)
    async def ticketstats_(self, ctx):
        """Manually adjust the ticket status counter"""
        if not ctx.invoked_subcommand:
            await ctx.send_help(ctx.command)

    @checks.has_permissions(PermissionLevel.ADMIN)
    @ticketstats_.command(name='open')
    async def ticketstats_open(self, ctx, counter: int):
        """Manually adjust the open tickets counter"""
        self.tickets_open = counter
        await self._update_config()
        embed = self.status_msg[0].embeds[0]
        embed.set_field_at(index=0, name='Open Tickets', value=counter, inline=False)
        for m in self.status_msg:
            try:
                await m.edit(embed=embed)
            except:
                pass
        await ctx.message.add_reaction('✅')

    @checks.has_permissions(PermissionLevel.ADMIN)
    @ticketstats_.command(name='day')
    async def ticketstats_day(self, ctx, counter: int):
        """Manually adjust the day's tickets counter"""
        self.tickets_24hrs = counter
        await self._update_config()
        embed = self.status_msg[0].embeds[0]
        embed.set_field_at(index=1, name='Resolved - 24hrs', value=counter, inline=False)
        for m in self.status_msg:
            try:
                await m.edit(embed=embed)
            except:
                pass
        await ctx.message.add_reaction('✅')

    @checks.has_permissions(PermissionLevel.ADMIN)
    @ticketstats_.command(name='lifetime')
    async def ticketstats_lifetime(self, ctx, counter: int):
        """Manually adjust the lifetime tickets counter"""
        self.tickets_lifetime = counter
        await self._update_config()
        embed = self.status_msg[0].embeds[0]
        embed.set_field_at(index=2, name='Resolved - Lifetime', value=counter, inline=False)
        for m in self.status_msg:
            try:
                await m.edit(embed=embed)
            except:
                pass
        await ctx.message.add_reaction('✅')

    @checks.has_permissions(PermissionLevel.ADMIN)
    @ticketstats_.command(name='backlog')
    async def ticketstats_backlog(self, ctx, counter: int):
        """Set the backlog limit"""
        self.tickets_backlog = counter
        await self._update_config()
        embed = self.status_msg[0].embeds[0]
        embed.description = await self.dm_status()
        for m in self.status_msg:
            try:
                await m.edit(embed=embed)
            except:
                pass
        await ctx.message.add_reaction('✅')

    @checks.has_permissions(PermissionLevel.ADMIN)
    @ticketstats_.command(name='activity')
    async def ticketstats_activity(self, ctx, status: bool):
        """
        Enable/Disable bot activity based on current status
        `{prefix}ticketstats activity yes/no`
        """
        self.activity = status
        await self._update_config()
        await self.dm_status()
        await ctx.message.add_reaction('✅')

    @checks.has_permissions(PermissionLevel.ADMIN)
    @ticketstats_.command(name='channel')
    async def ticketstats_channel(self, ctx, channel: discord.TextChannel):
        """Set More stats channels"""
        if str(channel.id) in self.status_group:
            del self.status_group[str(channel.id)]
        else:
            self.status_group[str(channel.id)] = None
        await self._update_config()
        self.status_msg = list()
        self.task.cancel()
        self.task = self.bot.loop.create_task(self.cog_load())
        await ctx.message.add_reaction('✅')

    @checks.has_permissions(PermissionLevel.ADMIN)
    @ticketstats_.command(name='restorecounter')
    async def ticketstats_restorecounter(self, ctx):
        """Reads the logs database and restores the __Open__ and __Lifetime Closed__ count from it"""

        logs = self.bot.db.logs

        opened = await logs.find({"open": True}).to_list(None)
        self.tickets_open == len(opened)

        closed = await logs.find({"open": False}).to_list(None)
        self.tickets_lifetime == len(closed)

        await self._update_config()
        await ctx.message.add_reaction('✅')

def setup(bot):
    bot.add_cog(TicketStats(bot))