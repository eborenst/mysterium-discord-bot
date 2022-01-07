import os
import discord
from discord.ext import commands

_default_user_role = "Guildsman"
_status_messages_channel = "bot-messages"

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix = "!", intents = intents)
TOKEN = os.getenv("DISCORD_TOKEN")

@bot.event
async def on_ready():
	print(f"Logged in as {bot.user.name}({bot.user.id})")

@bot.event
async def on_member_join(member):
	guild = member.guild
	print(f"User '{member.display_name}' joined server '{guild.name}'.")

	statusChannel = discord.utils.get(guild.text_channels, name=_status_messages_channel)
	await statusChannel.send(f"Hey! {member.mention} just joined the server!")

@bot.event
async def on_member_update(before, after):
	if before.pending == True and after.pending == False:
		guild = after.guild
		print(f"User '{after.display_name}' ({after.name}) in server '{guild.name}' went through screening. Applying '{_default_user_role}' role.")

		try:
			role = discord.utils.get(after.guild.roles, name=_default_user_role)
			await after.add_roles(role, reason = "Completed member screening.")
		except discord.errors.Forbidden as e:
			# Send a message to the server about it, and then re-raise it so it gets logged
			# on the server.
			statusChannel = discord.utils.get(guild.text_channels, name=_status_messages_channel)
			await statusChannel.send(f"ERROR! Bot got a 'FORBIDDEN' error after trying to grant the '{_default_user_role}' role to '{after.mention}'!")
			raise e


		statusChannel = discord.utils.get(guild.text_channels, name=_status_messages_channel)
		await statusChannel.send(f"{after.mention} completed screening and was given the '{_default_user_role}' role!")
		print(f"Gave role '{_default_user_role}' to user '{after.display_name}'.")

@bot.command()
async def ping(ctx):
	await ctx.send("pong")	

if __name__ == "__main__":
	bot.run(TOKEN)
