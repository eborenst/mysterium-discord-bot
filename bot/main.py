import os
import discord
from discord.ext import commands

_default_user_role = "Guildsman"
_status_messages_channel = "moderator-only"

bot = commands.Bot(command_prefix="!")
TOKEN = os.getenv("DISCORD_TOKEN")

@bot.event
async def on_ready():
	print(f"Logged in as {bot.user.name}({bot.user.id})")

@bot.event
async def on_member_join(member):
	print(f"User {member.display_name} ({member.id}) joined server {guild.name}.")

	guild = member.guild
	statusChannel = discord.utils.get(guild.text_channels, name=_status_messages_channel)
	await statusChannel.send("Hey! {member.display_name} ({member.id}) just joined the server!")


@bot.event
async def on_member_update(before, after):
	if before.pending == True and after.pending == False:
		print(f"User {after.display_name} ({after.id}) in server {guild.name} went through screening. Applying {_default_user_role} role.")

		guild = after.guild
		statusChannel = discord.utils.get(guild.text_channels, name=_status_messages_channel)
		await statusChannel.send("We would have given {member.display_name} a permission right now if we were active.")

		#role = discord.utils.get(after.guild.roles, name=_default_user_role)
		#await after.add_roles(role, reason = "Completed member screening.")



@bot.command()
async def ping(ctx):
	await ctx.send("pong")

if __name__ == "__main__":
	bot.run(TOKEN)
