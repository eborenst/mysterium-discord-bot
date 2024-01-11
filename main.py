import os
import sys
import discord
from discord.ext import commands
from urllib.request import urlopen
import csv
import urllib.error

# ------- CONSTANTS -------
_default_user_role = "Guildsman" # The role to grant after Member Screening.
_onsite_user_role = "Mysterium Onsite" # The role used for onsite attendees.
_status_messages_channel = "bot-messages" # Where to send status messages.
_rules_channel = "rules" # Channel where the rules live.
_rules_url = "https://mysterium.net/discord-rules/"

# For some reason, logs to stdout will not show up in the fly.io console on their v2 platform,
# but logs to stderr will just show normally. So we'll do that.
def log(x):
	print(f"BOT LOG: {x}", file=sys.stderr)

# Class for a persistent view for manipulating the Onsite role with buttons.
# See this example for why we need this - https://github.com/Rapptz/discord.py/blob/master/examples/views/persistent.py
class PersistentOnsiteRoleView(discord.ui.View):
	def __init__(self):
		# Set the timeout to None so it is persistent.
		super().__init__(timeout=None)

	@discord.ui.button(label='Receive Notifications', style=discord.ButtonStyle.green, custom_id='PersistentOnsiteRoleView:add_onsite')
	async def green(self, interaction: discord.Interaction, button: discord.ui.Button):
		guild = interaction.guild
		user = interaction.user
		attendeeRole = discord.utils.get(guild.roles, name=_onsite_user_role)

		if attendeeRole in user.roles:
			await interaction.response.send_message('You are already receiving notifications.', ephemeral=True)
		else:
			await user.add_roles(attendeeRole, reason="User requested via button.")
			await interaction.response.send_message('You will now receive notifications!', ephemeral=True)

	@discord.ui.button(label='Stop Notifications', style=discord.ButtonStyle.red, custom_id='PersistentOnsiteRoleView:remove_onsite')
	async def red(self, interaction: discord.Interaction, button: discord.ui.Button):
		guild = interaction.guild
		user = interaction.user
		attendeeRole = discord.utils.get(guild.roles, name=_onsite_user_role)

		if attendeeRole not in user.roles:
			await interaction.response.send_message('You are not currently receiving notifications.', ephemeral=True)
		else:
			await user.remove_roles(attendeeRole, reason="User requested via button.")
			await interaction.response.send_message('You will no longer receive notifications!', ephemeral=True)

# We need to make a custom bot to override the setup_hook for persistent views.
class MysteriumBot(commands.Bot):
	def __init__(self):
		# We need to declare this intent or Discord won't let us change member permissions or access
		# member data.
		intents = discord.Intents.default()
		intents.members = True
		intents.message_content = True

		super().__init__(command_prefix=commands.when_mentioned_or('!'), intents=intents)

	async def setup_hook(self) -> None:
		# Register the persistent view for listening here.
		# Note that this does not send the view to any message.
		# In order to do this you need to first send a message with the View.
		self.add_view(PersistentOnsiteRoleView())

	# Event run when the bot starts up.
	async def on_ready(self):
		log(f"Logged in as {bot.user.name}({bot.user.id})")

		for guild in bot.guilds:
			statusChannel = discord.utils.get(guild.text_channels, name=_status_messages_channel)
			await statusChannel.send(f"*{bot.user.name} has linked in*")

# Create the bot and grab our private key/token from the Heroku environment variables.
bot = MysteriumBot()
TOKEN = os.getenv("DISCORD_TOKEN")

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
	attendeeRole = discord.utils.get(guild.roles, name=_onsite_user_role)
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

# Display a message and buttons for toggling the Onsite role.
@bot.command()
@commands.has_role("Mysterium Staff")
async def SendOnsiteMsg(ctx):
	await ctx.send("Use these buttons to start or stop receiving notifications for on-site Mysterium announcements.", view=PersistentOnsiteRoleView())

_rules_mode_push = "push"
_rules_mode_test = "test"

# A command to update the server rules from a plain text post on the blog.
@bot.command()
@commands.has_role("Mysterium Staff")
async def UpdateRules(ctx, mode):
	guild = ctx.guild
	statusChannel = discord.utils.get(guild.text_channels, name=_status_messages_channel)

	if mode != _rules_mode_test and mode != _rules_mode_push:
		message = f"The provided mode, `{mode}`, is not valid. Aborting rules update."
		log(message)
		await statusChannel.send(message)
		return

	message = f"Attempting to download rules from {_rules_url}"
	await statusChannel.send(message)
	log(message)

	try:
		# Pull in the CSV from the user-provided URL
		with urlopen(_rules_url) as response:
			log("Opened the URL.")
			rules = response.read().decode('utf-8')			
	except urllib.error.URLError as e:
		# Oops, did you get the URL right??
		message = f"Failed retrieving '{_rules_url}'.  Aborting...\n Server response was: '{e.code}'."
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

	# Search for the special string at the start of role mentions and replace with what
	# Discord wants.
	rules = rules.replace("{@&", "<@&")

	# Split the rules at break points.
	rules = rules.split("{br}")
	message = f"Got {len(rules)} chunks of rules."
	log(message)
	await statusChannel.send(message)

	# Check that none of the segments is longer than 2000 characters, which is Discords char limit.
	for i in range(len(rules)):
		if len(rules[i]) > 2000:
			message = f"Rules section {i+1} is {len(rules[i])} characters long, but the limit is 2000 characters. Aborting."
			log(message)
			await statusChannel.send(message)
			return

	message = f"All rules chunks are valid."
	log(message)
	await statusChannel.send(message)

	# If we're in push mode, clear the rules channel and post there.
	if mode == _rules_mode_push:
		log("Grabbing rules channel.")
		rulesChannel = discord.utils.get(guild.text_channels, name=_rules_channel)

		message = f"Attempting to purge rules channel."
		log(message)
		await statusChannel.send(message)

		await rulesChannel.purge()

		message = f"Purge complete, attempting to post to rules channel."
		log(message)
		await statusChannel.send(message)

		for r in rules:
			await rulesChannel.send(r)

		await statusChannel.send("Rules posted to rules channel.")
	else:
		# Otherwise, just post them to the status channel.
		await statusChannel.send("---BEGINNING RULES---")

		for r in rules:
			await statusChannel.send(r)

		await statusChannel.send("---END OF RULES---")

	message = "Rules update complete."
	log(message)
	await statusChannel.send(message)


	# TODO
	# check if it works if the rules channel is made uneditable by onboarding setup

# Handle errors for the UpdateRules command.
@UpdateRules.error
async def UpdateRules_error(ctx, error):
	statusChannel = discord.utils.get(ctx.guild.text_channels, name=_status_messages_channel)

	if isinstance(error, commands.MissingRequiredArgument):
		message = "Error: The `UpdateRules` command requires a mode as an argument."
		message += f"\n\nMode `{_rules_mode_test}` will output the rules to the #bot-messages channel for testing."
		message += f"\nMode `{_rules_mode_push}` will clear the #rules channel and output the new rules to that channel."
		log(message)
		await statusChannel.send(message)
	elif isinstance(error, commands.MissingRole):
		message = "Error: Only Mysterium Staff can use the `UpdateRules` command."
		log(message)
		await statusChannel.send(message)

log("Bot starting...")

if __name__ == "__main__":
	bot.run(TOKEN)
