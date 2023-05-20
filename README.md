Mysterium's discord bot.

For info about hosting on fly.io, see https://dev.to/denvercoder1/hosting-a-python-discord-bot-for-free-with-flyio-3k19

The link above talks about installing flyctl on your machine, but I couldn't get their install script to work. So I just downloaded the executable from the github repo that their script grabs it from and stuck it in this repo. It'll probably need to be updated now and then, but that shouldn't be a big deal given how infrequently we touch this bot's code.

To deploy a new version, navigate to the root folder for this repository on your local machine and open it in a terminal/console. Run "flyctl.exe deploy". If you haven't used flyctl on the machine before, you may need to log in. It will yell instructions at you if so.
