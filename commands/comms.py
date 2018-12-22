# -*- coding: utf-8 -*-

"""
Comsystem command module.

Contrary to the Evennia default comm system, channels in Avenew are
available to logged-in characters only, not to accounts through the OOC
mode (there's not much of an OOC mode in Avenew).  The default commands
are therefore removed from the AccountCmdSet, while the new commands are
added into the CharacterCmdSet.

"""

from django.utils.translation import ugettext as _
from evennia import SESSION_HANDLER
from evennia.commands.default.muxcommand import MuxCommand
from evennia.comms.channelhandler import CHANNELHANDLER
from evennia.comms.models import ChannelDB
from evennia.locks.lockhandler import LockException
from evennia.utils import evtable
from evennia.utils.logger import tail_log_file
from evennia.utils.search import search_channel

from commands.command import Command

class ChannelCommand(Command):
    """
    {channelkey} channel

    {channeldesc}

    Syntaxe :
      {lower_channelkey} <message>
      {lower_channelkey}/history [début]
      {lower_channelkey}/me <message>
      {lower_channelkey}/who

    Switch :
      history : Voit les 20 derniers messages du canal, soit depuis la fin soit
                depuis le nombre précisé en paramètre.
      me : Fait une action dans ce canal.
      who : Affiche la liste des connectés au canal.

    Exemple :
      {lower_channelkey} Bonjour !
      {lower_channelkey}/history
      {lower_channelkey}/history 30
      {lower_channelkey}/me sourit.
      {lower_channelkey}/who
    """
    # ^note that channeldesc and lower_channelkey will be filled
    # automatically by ChannelHandler

    # this flag is what identifies this cmd as a channel cmd
    # and branches off to the system send-to-channel command
    # (which is customizable by admin)
    is_channel = True
    key = "general"
    help_category = "Channel Names"
    obj = None
    arg_regex = ""

    def parse(self):
        """
        Simple parser
        """
        # cmdhandler sends channame:msg here.
        channelname, msg = self.args.split(":", 1)
        self.history_start = None
        self.switch = None
        if msg.startswith("/"):
            try:
                switch, msg = msg[1:].split(" ", 1)
            except ValueError:
                switch = msg[1:]
                msg = ""

            self.switch = switch.lower().strip()

        # If /history
        if self.switch == "history":
            try:
                self.history_start = int(msg) if msg else 0
            except ValueError:
                # if no valid number was given, ignore it
                pass

        self.args = (channelname.strip(), msg.strip())

    def func(self):
        """
        Create a new message and send it to channel, using
        the already formatted input.
        """
        channelkey, msg = self.args
        caller = self.caller
        channel = ChannelDB.objects.get_channel(channelkey)
        admin_switches = ("destroy", "emit", "lock", "locks", "desc", "kick")

        # Check that the channel exist
        if not channel:
            self.msg(_("Channel '%s' not found.") % channelkey)
            return

        # Check that the caller is connected
        if not channel.has_connection(caller):
            string = _("You are not connected to channel '%s'.")
            self.msg(string % channelkey)
            return

        # Check that the caller has send access
        if not channel.access(caller, 'send'):
            string = _("You are not permitted to send to channel '%s'.")
            self.msg(string % channelkey)
            return

        # Get the list of connected to this channel
        connected = [obj for obj in channel.subscriptions.all() if getattr(obj, "is_connected", False)]

        # Handle the various switches
        if self.switch == "me":
            if not msg:
                self.msg("Quelle action voulez-vous faire dans ce canal ?")
            else:
                msg = "{} {}".format(caller.key, msg)
                channel.msg(msg, online=True)
        elif self.switch == "who":
            keys = [obj.username for obj in connected]
            keys.sort()
            string = "Connectés au canal {} : ".format(channel.key)
            string += ", ".join(keys) if keys else "(no one)"
            string += "."
            self.msg(string)
        elif channel.access(caller, 'control') and self.switch in admin_switches:
            if self.switch == "destroy":
                confirm = yield("Are you sure you want to delete the channel {}? (Y?N)".format(channel.key))
                if confirm.lower() in ("y", "yes"):
                    channel.msg("Destroying the channel.")
                    channel.delete()
                    CHANNELHANDLER.update()
                    self.msg("The channel was destroyed.")
                else:
                    self.msg("Operation cancelled, do not destroy.")
            elif self.switch == "emit":
                if not msg:
                    self.msg("What do you want to say on this channel?")
                else:
                    channel.msg(msg, online=True)
            elif self.switch in ("lock", "locks"):
                if msg:
                    try:
                        channel.locks.add(msg)
                    except LockException, err:
                        self.msg(err)
                        return
                    else:
                        self.msg("Channel permissions were edited.")

                string = "Current locks on {}:\n  {}".format(channel.key, channel.locks)
                self.msg(string)
            elif self.switch == "desc":
                if msg:
                    channel.db.desc = msg
                    self.msg("Channel description was updated.")

                self.msg("Description of the {} channel: {}".format(
                        channel.key, channel.db.desc))
            elif self.switch == "kick":
                if not msg:
                    self.msg("Who do you want to kick from this channel?")
                else:
                    to_kick = caller.search(msg, candidates=connected)
                    if to_kick is None:
                        return

                    channel.disconnect(to_kick)
                    channel.msg("{} has been kicked from the channel.".format(to_kick.key))
                    to_kick.msg("You have been kicked from the {} channel.".format(channel.key))
        elif self.history_start is not None:
            # Try to view history
            log_file = channel.attributes.get("log_file", default="channel_%s.log" % channel.key)
            send_msg = lambda lines: self.msg("".join(line.split("[-]", 1)[1]
                                                    if "[-]" in line else line for line in lines))
            tail_log_file(log_file, self.history_start, 20, callback=send_msg)
        elif self.switch:
            self.msg("{}: Switch invalide {}.".format(channel.key, self.switch))
        elif not msg:
            self.msg(_("Say what?"))
            return
        else:
            if caller in channel.mutelist:
                self.msg("You currently have %s muted." % channel)
                return
            channel.msg(msg, senders=self.caller, online=True)

    def get_extra_info(self, caller, **kwargs):
        """
        Let users know that this command is for communicating on a channel.

        Args:
            caller (TypedObject): A Character or Account who has entered an ambiguous command.

        Returns:
            A string with identifying information to disambiguate the object, conventionally with a preceding space.
        """
        return _(" (channel)")

    def get_help(self, caller, cmdset):
        """
        Return the help message for this command and this caller.

        By default, return self.__doc__ (the docstring just under
        the class definition).  You can override this behavior,
        though, and even customize it depending on the caller, or other
        commands the caller can use.

        Args:
            caller (Object or Account): the caller asking for help on the command.
            cmdset (CmdSet): the command set (if you need additional commands).

        Returns:
            docstring (str): the help text to provide the caller for this command.

        """
        docstring = self.__doc__
        channel = ChannelDB.objects.get_channel(self.key)
        if channel and channel.access(caller, 'control'):
            # Add in the command administration switches
            docstring += HELP_COMM_ADMIN.format(lower_channelkey=self.key.lower())

        return docstring


# Help entry for command administrators
HELP_COMM_ADMIN = r"""

    Administrator switches:
      {lower_channelkey}/kick <username>: kick a user from a channel.
      {lower_channelkey}/desc [description]: see or change the channel description.
      {lower_channelkey}/lock [lockstring]: see or change the channel permissions.
      {lower_channelkey}/emit <message>: admin emit to the channel.
      {lower_channelkey}/destroy: destroy the channel.
"""
