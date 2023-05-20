import os
import sys
import discord
from discord.ext import commands

# ------- CONSTANTS -------
_default_user_role = "Guildsman" # The role to grant after Member Screening.
_status_messages_channel = "bot-messages" # Where to send status messages.

# We need to declare this intent or Discord won't let us change member permissions or access
# member data.
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Create the bot and grab our private key/token from the Heroku environment variables.
bot = commands.Bot(command_prefix = "$", intents = intents)
TOKEN = os.getenv("DISCORD_TOKEN")

# For some reason, logs to stdout will not show up in the fly.io console on their v2 platform,
# but logs to stderr will just show normally. So we'll do that.
def log(x):
	print(f"BOT LOG: {x}", file=sys.stderr)

# Event run when the bot starts up.
@bot.event
async def on_ready():
	log(f"Logged in as {bot.user.name}({bot.user.id})")

# Event run whenever a new member joins one of our servers.
@bot.event
async def on_member_join(member):
	# Log it on the backend, and then announce it in the server chat.
	guild = member.guild
	log(f"User '{member.display_name}' joined server '{guild.name}'.")

	statusChannel = discord.utils.get(guild.text_channels, name=_status_messages_channel)
	await statusChannel.send(f"Hey! {member.mention} just joined the server!")

# Event run whenever a new member's status is updated.
# We only use this to catch when they complete Member Screening and grant them a role.
@bot.event
async def on_member_update(before, after):
	# Check that the 'pending' attribute went from True to False (indicating they finished Screening).
	if before.pending == True and after.pending == False:

		# Log it.
		guild = after.guild
		log(f"User '{after.display_name}' ({after.name}) in server '{guild.name}' went through screening. Applying '{_default_user_role}' role.")

		# Try to grant them the role. If that fails for permissions reasons, log it and announce
		# it on the server.
		try:
			role = discord.utils.get(after.guild.roles, name=_default_user_role)
			await after.add_roles(role, reason = "Completed member screening.")
		except discord.errors.Forbidden as e:
			# Send a message to the server about it, and then re-raise it so it gets logged
			# on the server.
			log(f"ERROR! Bot got a 'FORBIDDEN' error after trying to grant the '{_default_user_role}' role to '{after.display_name}' ({after.name})! Stack trace to follow:")
			statusChannel = discord.utils.get(guild.text_channels, name=_status_messages_channel)
			await statusChannel.send(f"ERROR! Bot got a 'FORBIDDEN' error after trying to grant the '{_default_user_role}' role to '{after.mention}'!")
			raise e

		# Log and announce on the server that we added the role to the user.
		statusChannel = discord.utils.get(guild.text_channels, name=_status_messages_channel)
		await statusChannel.send(f"{after.mention} completed screening and was given the '{_default_user_role}' role!")
		log(f"Gave role '{_default_user_role}' to user '{after.display_name}'.")

# This is just an example command that came with the template. I figured I'd leave it in for fun :)
@bot.command()
async def ping(ctx):
	await ctx.send("pong")
	log(f"Sent a pong for a ping!")

log("Bot starting...")

if __name__ == "__main__":
	bot.run(TOKEN)
