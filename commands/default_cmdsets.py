"""
Command sets

All commands in the game must be grouped in a cmdset.  A given command
can be part of any number of cmdsets and cmdsets can be added/removed
and merged onto entities at runtime.

To create new commands to populate the cmdset, see
`commands/command.py`.

This module wraps the default command sets of Evennia; overloads them
to add/remove commands from the default lineup. You can create your
own cmdsets by inheriting from them or directly from `evennia.CmdSet`.

"""

from evennia import default_cmds
from evennia.commands.default import account


from commands.general import CmdAfk, CmdEmote, CmdSay, CmdTell, CmdWho

class CharacterCmdSet(default_cmds.CharacterCmdSet):
    """
    The `CharacterCmdSet` contains general in-game commands like `look`,
    `get`, etc available on in-game Character objects. It is merged with
    the `AccountCmdSet` when an Account puppets a Character.
    """
    key = "DefaultCharacter"

    def at_cmdset_creation(self):
        """
        Populates the cmdset
        """
        super(CharacterCmdSet, self).at_cmdset_creation()
        self.remove(default_cmds.CmdDrop())
        self.remove(default_cmds.CmdGet())
        self.remove(default_cmds.CmdGive())
        self.remove(default_cmds.CmdHome())
        self.remove(default_cmds.CmdInventory())
        self.remove(default_cmds.CmdPose())
        self.remove(default_cmds.CmdSay())
        self.remove(default_cmds.CmdSetDesc())
        self.remove(default_cmds.CmdWho())
        self.remove(default_cmds.CmdWhisper())
        self.remove(default_cmds.CmdAbout())
        self.remove(default_cmds.CmdTime())
        self.remove(default_cmds.CmdAccess())
        self.remove(default_cmds.CmdNick())

        # Add Vancia commands
        self.add(CmdAfk())
        self.add(CmdEmote())
        self.add(CmdSay())
        self.add(CmdTell())
        self.add(CmdWho())


class AccountCmdSet(default_cmds.AccountCmdSet):
    """
    This is the cmdset available to the Account at all times. It is
    combined with the `CharacterCmdSet` when the Account puppets a
    Character. It holds game-account-specific commands, channel
    commands, etc.
    """
    key = "DefaultAccount"

    def at_cmdset_creation(self):
        """
        Populates the cmdset
        """
        super(AccountCmdSet, self).at_cmdset_creation()
        self.remove(default_cmds.CmdPage())
        self.remove(default_cmds.CmdCharCreate())
        self.remove(account.CmdCharDelete())
        self.remove(default_cmds.CmdQuell())
        self.remove(default_cmds.CmdIC())
        self.remove(default_cmds.CmdOOC())
        self.remove(default_cmds.CmdWho())
        self.remove(default_cmds.CmdNick())
        self.remove(default_cmds.CmdChannelCreate())
        self.remove(default_cmds.CmdCBoot())
        self.remove(default_cmds.CmdCdesc())
        self.remove(default_cmds.CmdCdestroy())
        self.remove(default_cmds.CmdCemit())
        self.remove(default_cmds.CmdClock())
        self.remove(default_cmds.CmdCWho())
        self.remove(default_cmds.CmdAddCom())
        self.remove(default_cmds.CmdAllCom())
        self.remove(default_cmds.CmdDelCom())
        self.remove(default_cmds.CmdChannels())


class UnloggedinCmdSet(default_cmds.UnloggedinCmdSet):
    """
    Command set available to the Session before being logged in.  This
    holds commands like creating a new account, logging in, etc.
    """
    key = "DefaultUnloggedin"

    def at_cmdset_creation(self):
        """
        Populates the cmdset
        """
        super(UnloggedinCmdSet, self).at_cmdset_creation()
        #
        # any commands you add below will overload the default ones.
        #


class SessionCmdSet(default_cmds.SessionCmdSet):
    """
    This cmdset is made available on Session level once logged in. It
    is empty by default.
    """
    key = "DefaultSession"

    def at_cmdset_creation(self):
        """
        This is the only method defined in a cmdset, called during
        its creation. It should populate the set with command instances.

        As and example we just add the empty base `Command` object.
        It prints some info.
        """
        super(SessionCmdSet, self).at_cmdset_creation()
        #
        # any commands you add below will overload the default ones.
        #
