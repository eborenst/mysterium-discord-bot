import os
import sys
import discord
from discord.ext import commands
from urllib.request import urlopen

# ------- CONSTANTS -------
_default_user_role = "Guildsman" # The role to grant after Member Screening.
_status_messages_channel = "bot-messages" # Where to send status messages.

# We need to declare this intent or Discord won't let us change member permissions or access
# member data.
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Create the bot and grab our private key/token from the Heroku environment variables.
bot = commands.Bot(command_prefix = "!", intents = intents)
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

# Pull CSV of discord usernames from mysterium.net and try to apply a specific role to them. 
@bot.command()
async def bulkadd(ctx, url):
	guild = ctx.guild
	users = guild.members
	attendeeRole = discord.utils.get(guild.roles, name="Mysterium Onsite")
	statusChannel = discord.utils.get(guild.text_channels, name=_status_messages_channel)
	usersNotFound = []
	

	# If user is Mysterium Staff then,
	if discord.utils.get(guild.roles, name="Mysterium Staff") in ctx.author.roles:
		# Announce it
		message = f"User '{ctx.author}' just started the bulk add mysterium attendee role command."
		log(message)
		await statusChannel.send(message)

		try:
			# Pull in the CSV from the user-provided URL
			with urlopen(url) as response:
				# Unicode unfuckery
				lines = (line.decode('utf-8') for line in response)
				# Iterate over each line in the CSV and process
				for row in csv.reader(lines):
					# Split  Username#0000 into two in order to pass them to the Discord disambiguator
					csvUser=row[0].split("#")
					# Pass name and, if present, the discriminator (thanks for the "improvement", Discord...)
					with discord.utils.get(users, name = csvUser[0], discriminator = (csvUser[1] if len(csvUser) == 2 else None)) as u:
						if u is None:
							# User as-presented isn't in Members list so 'get' call returned None. Add them to a list to report back later.
							# TODO: Maybe if name & discriminator fail, try the call again with just name before failing?
							usersNotFound.append(row[0])
						else:
							# User was found in member list so do the needful.
							#TODO: I think this doesn't fail if the user already has the role? Discord and discord.py docs both don't address this.
							await u.add_roles(attendeeRole)
		except urllib.error.URLError as e:
			# Oops, did you get the URL right??
			message = f"Failed retrieving '{url}' with server response '{e.code}'."
			log(message)
			await statusChannel.send(message)

		# Build a message to report back on failed users and send it:
		if len(usersNotFound) > 0:
			uNFMessage = "The following users were not found in the server:"
			for userNotFound in usersNotFound:
				uNFMessage = uNFMessage + "\n    " + userNotFound
			log(uNFMessage)
			await statusChannel.send(uNFMessage)

		message = "The bulk add mysterium attendee role command has finished."
		log(message)
		await statusChannel.send(message)

	else:
		message = f"User '{ctx.author}' just tried to run the bulk add mysterium attendee role command, but doesn't have the right permissions."
		log(message)
		await statusChannel.send(message)

log("Bot starting...")

if __name__ == "__main__":
	bot.run(TOKEN)
