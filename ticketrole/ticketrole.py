# created for gothikit

import asyncio
import discord
from discord.ext import commands
from core import checks
from core.checks import PermissionLevel
from typing import Sequence
from babel.lists import format_list as babel_list

def humanize_list(
    items: Sequence[str], *, style: str = "standard"
) -> str:
    return babel_list(items, style=style)

class TicketRoles(commands.Cog):
    """Add custom roles to ticket author, within tickets"""
    def __init__(self, bot):
        self.bot = bot
        self.db = self.bot.plugin_db.get_partition(self)

        self.config = None
        self.guild = self.bot.modmail_guild

        self.roles = {}
        self.enabled = True

    async def cog_load(self):
        data = {
            "enabled": True,
            "roles": [],
        }

        self.config = await self.db.find_one({"_id": "config"})
        if self.config is None:
            await self.db.find_one_and_update({"_id": "config"}, {"$set": data}, upsert=True)

            self.config = await self.db.find_one({"_id": "config"})

        up = False
        for k, v in data.items():
            if k not in self.config:
                self.config[k] = v
                up = True
            
        roles = self.config.get("roles", True)
        self.roles = {k: self.guild.get_role(k) for k in roles if self.guild.get_role(k)}
        self.enabled = self.config.get("enabled", True)

        if up:
            await self._update_config()

    async def _update_config(self):
        await self.db.find_one_and_update({"_id": "config"},
            {"$set": {
                "enabled": self.enabled,
                "roles": list(self.roles.keys()),
                },
            }, upsert=True)

    #def cog_unload(self):
        #if self.reset_daily:
            #self.reset_daily.cancel()

    async def check_before_update(self, channel):
        await asyncio.sleep(0.5)
        log = await self.bot.api.get_log(channel.id)
        if channel.guild != self.guild or not log:
            return False, None

        return True, log

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if not self.enabled:
            return

        if len(self.roles) == 0:
            return

        await asyncio.sleep(2)
        ticket, log = await self.check_before_update(channel)
        if ticket:
            author = self.guild.get_member(int(log['recipient']['id']))
            buttons = []
            for r in self.roles.values():
                if r in author.roles:
                    style = discord.ButtonStyle.red
                else:
                    style = discord.ButtonStyle.green

                buttons.append(
                    discord.ui.Button(
                        style=style,
                        label=r.name,
                        custom_id=f"ticketrole_{r.id}_{channel.id}",
                    ),
                )

            async for m in channel.history(limit=5, oldest_first=True):
                if m.author == self.bot.user:
                    if m.embeds and m.embeds[0].fields and m.embeds[0].fields[0].name == "Roles":
                        await m.edit(components=buttons)
                        break

    @checks.has_permissions(PermissionLevel.ADMIN)
    @commands.group(name='ticketrole', invoke_without_command=True)
    async def ticketrole_(self, ctx):
        """Ticket Roles commands"""
        if not ctx.invoked_subcommand:
            await ctx.send_help(ctx.command)

    @checks.has_permissions(PermissionLevel.ADMIN)
    @ticketrole_.command(name='add')
    async def ticketrole_add(self, ctx, role: discord.Role):
        """Add roles to possible options"""
        if len(self.roles) > 24:
            return await ctx.send("Max roles can be 25 only")

        if role.id not in self.roles:
            self.roles[role.id] = role

        await self._update_config()
        await ctx.message.add_reaction("✅")

    @checks.has_permissions(PermissionLevel.ADMIN)
    @ticketrole_.command(name='del')
    async def ticketrole_del(self, ctx, role: discord.Role):
        """Remove roles to possible options"""
        if role.id in self.roles:
            del self.roles[role.id]
        await self._update_config()
        await ctx.message.add_reaction("✅")

    @checks.has_permissions(PermissionLevel.ADMIN)
    @ticketrole_.command(name='view')
    async def ticketrole_view(self, ctx):
        """View all added roles"""
        embed = discord.Embed(title="Ticket Roles", color=self.bot.main_color)
        roles = [r.name for r in self.roles.values()]
        embed.description = humanize_list(roles) if len(roles) > 0 else "None"
        await ctx.send(embed=embed)

    @checks.has_permissions(PermissionLevel.ADMIN)
    @ticketrole_.command(name='toggle')
    async def ticketrole_toggle(self, ctx):
        """Enable/Disable the plugin"""
        self.enabled = not self.enabled
        await self._update_config()
        embed = discord.Embed(title="Ticket Roles Status", color=self.bot.main_color)
        embed.description = f"Enabled: **{self.enabled}**"
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_button_click(self, inter: discord.MessageInteraction):
        if not inter.component.custom_id.startswith('ticketrole'):
            return

        if not self.enabled:
            return

        if len(self.roles) == 0:
            return

        message = inter.message
        customid, role_id, channel_id = inter.component.custom_id.split('_')

        role_id = int(role_id)
        channel_id = int(channel_id)

        if role_id not in self.roles:
            return inter.response.send_message("Role not found on saved database!")

        role = self.roles[role_id]
        log = await self.bot.api.get_log(channel_id)
        if log:
            author = self.guild.get_member(int(log['recipient']['id']))
            if author:
                buttons = []

                if role in author.roles:
                    await author.remove_roles(role)

                else:
                    await author.add_roles(role)

                for r in self.roles.values():
                    if r in author.roles:
                        style = discord.ButtonStyle.red
                    else:
                        style = discord.ButtonStyle.green

                    buttons.append(
                        discord.ui.Button(
                            style=style,
                            label=r.name,
                            custom_id=f"ticketrole_{r.id}_{channel_id}",
                        ),
                    )

                await inter.response.edit_message(components=buttons)

async def setup(bot):
    await bot.add_cog(TicketRoles(bot))