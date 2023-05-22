import os
import sys
import discord
from discord.ext import commands
from urllib.request import urlopen
import csv
import urllib.error

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

	for guild in bot.guilds:
		statusChannel = discord.utils.get(guild.text_channels, name=_status_messages_channel)
		await statusChannel.send(f"*{bot.user.name} has linked in*")

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

# Pull CSV of discord usernames from a user-supplied URL and try to apply a specific role to them.
@bot.command()
@commands.has_role("Mysterium Staff")
async def bulkadd(ctx, url):
	guild = ctx.guild
	users = guild.members
	attendeeRole = discord.utils.get(guild.roles, name="Mysterium Onsite")
	statusChannel = discord.utils.get(guild.text_channels, name=_status_messages_channel)
	usersNotFound = []	

	# Announce it
	message = f"User '{ctx.author}' just started the bulk add mysterium attendee role command."
	log(message)
	await statusChannel.send(message)

	try:
		# Pull in the CSV from the user-provided URL
		with urlopen(url) as response:
			log("Opened the URL.")

			# Unicode unfuckery
			lines = (line.decode('utf-8') for line in response)
			log("Parsed the lines.")

			# Iterate over each line in the CSV and process
			for row in csv.reader(lines):
				# Skip empty lines and the column header from Convention Manager
				if row == [] or row[0] == 'Discord Username': continue

				log(f"Working on row: '{row[0]}'")

				# Split  Username#0000 into two in order to pass them to the Discord disambiguator
				csvUser = row[0].split("#")
				# Pass name and, if present, the discriminator (thanks for the "improvement", Discord...)
				n = csvUser[0]
				d = (csvUser[1] if len(csvUser) == 2 else "0")
				u = discord.utils.get(users, name = n, discriminator = d)

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
		message = f"Failed retrieving '{url}'.  Aborting...\n Server response was: '{e.code}'."
		log(message)
		await statusChannel.send(message)
		return
	except ValueError as e:
		# User passed in something that wasn't valid URL syntax.
		message = f"Value error - '{url}' probably isn't a valid URL? Aborting...\n Error: '{e}'"
		log(message)
		await statusChannel.send(message)
		return
	except Exception as e:
		# Something else happened.
		message = f"Encountered unknown exception, aborting...\n Error was: '{e}'"
		log(message)
		await statusChannel.send(message)
		raise e
		return

	# Build a message to report back on failed users and send it:
	if len(usersNotFound) > 0:
		uNFMessage = "The following users were not found in the server:"
		for userNotFound in usersNotFound:
			uNFMessage = uNFMessage + "\n    " + userNotFound
		log(uNFMessage)
		await statusChannel.send(uNFMessage)
	else:
		message = "All users were found and were given the role."
		log(message)
		await statusChannel.send(message)

	message = "The bulk add mysterium attendee role command has finished."
	log(message)
	await statusChannel.send(message)

# Handle errors for the bulkadd command.
@bulkadd.error
async def bulkadd_error(ctx, error):
	statusChannel = discord.utils.get(ctx.guild.text_channels, name=_status_messages_channel)

	if isinstance(error, commands.MissingRequiredArgument):
		message = "Error: The `bulkadd` command requires a URL as an argument, but nothing was provided."
		log(message)
		await statusChannel.send(message)
	elif isinstance(error, commands.MissingRole):
		message = "Error: Only Mysterium Staff can use the `bulkadd` command."
		log(message)
		await statusChannel.send(message)


log("Bot starting...")

if __name__ == "__main__":
	bot.run(TOKEN)
