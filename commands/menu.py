# -*- coding: utf-8 -*-

"""The login menu."""

import re
from textwrap import dedent

from django.conf import settings

from evennia import Command, CmdSet
from evennia import logger
from evennia import managers
from evennia import ObjectDB
from evennia.server.models import ServerConfig
from evennia import syscmdkeys
from evennia.utils.evmenu import EvMenu
from evennia.utils.utils import random_string_from_module

# Constants
RE_VALID_USERNAME = re.compile(r"^[a-z]{3,}$", re.I)
LEN_PASSWD = 6
CONNECTION_SCREEN_MODULE = settings.CONNECTION_SCREEN_MODULE

# Menu nodes (top-level functions)


def start(caller):
    """The user should enter his/her username or NEW to create one.

    This node is called at the very beginning of the menu, when
    a session has been created OR if an error occurs further
    down the menu tree.  From there, users can either enter a
    username (if this username exists) or type NEW (capitalized
    or not) to create a new account.

    """
    text = random_string_from_module(CONNECTION_SCREEN_MODULE)
    text += "\n\n" + dedent("""
            Si vous aviez un compte enregistré sur l'ancien Vancia et souhaitez
            récupérer le nom d'un de ses personnages, entrez son nom ci-dessous.

            Entrez votre nom de compte ou |yNOUVEAU|n pour en créer un.
        """).strip()
    options = (
        {
            "key": "nouveau",
            "goto": "create_account",
        },
        {
            "key": "quit",
            "goto": "quit",
        },
        {
            "key": "_default",
            "goto": "username",
        },
    )
    return text, options


def username(caller, string_input):
    """Check that the username leads to an existing account.

    Check that the specified username exists.  If the username doesn't
    exist, display an error message and ask the user to try again.  If
    entering an empty string, return to start node.  If user exists,
    move to the next node (enter password).

    """
    string_input = string_input.strip()
    account = managers.accounts.get_account_from_name(string_input)
    if account is None:
        text = dedent("""
            |rCe nom d'utilisateur n'existe pas.|n L'avez-vous créé ?
            Essayez un nouveau nom d'utilisateur existant, ou entrez |yr|n
            pour revenir à l'écran d'accueil.
        """.strip("\n")).format(string_input)
        options = (
            {
                "key": "r",
                "goto": "start",
            },
            {
                "key": "_default",
                "goto": "username",
            },
        )
    else:
        caller.ndb._menutree.account = account
        text = "Entrez le mot de passe pour l'utilisateur {}.".format(account.name)
        # Disables echo for the password
        caller.msg("", options={"echo": False})
        options = (
            {
                "key": "r",
                "exec": lambda caller: caller.msg("", options={"echo": True}),
                "goto": "start",
            },
            {
                "key": "_default",
                "goto": "ask_password",
            },
        )

    return text, options


def ask_password(caller, string_input):
    """Ask the user to enter the password to this account.

    This is assuming the user exists (see 'create_username' and
    'create_password').  This node "loops" if needed:  if the
    user specifies a wrong password, offers the user to try
    again or to go back by entering 'b'.
    If the password is correct, then login.

    """
    menutree = caller.ndb._menutree
    string_input = string_input.strip()

    # Check the password and login is correct; also check for bans

    account = menutree.account
    password_attempts = getattr(menutree, "password_attempts", 0)
    bans = ServerConfig.objects.conf("server_bans")
    banned = bans and (any(tup[0] == account.name.lower() for tup in bans) or
                       any(tup[2].match(caller.address) for tup in bans if tup[2]))

    if not account.check_password(string_input):
        # Didn't enter a correct password
        password_attempts += 1
        if password_attempts > 2:
            # Too many tries
            caller.sessionhandler.disconnect(
                caller, "|rIl y a eu trop de tentatives de connexion erronnées. Déconnexion...|n")
            text = ""
            options = {}
        else:
            menutree.password_attempts = password_attempts
            text = dedent("""
                |rMot de passe invalide.|n
                Essayez un autre mot de passe ou entrez |yr|n pour revenir à l'écran d'accueil.
            """.strip("\n"))
            # Loops on the same node
            options = (
                {
                    "key": "r",
                    "exec": lambda caller: caller.msg("", options={"echo": True}),
                    "goto": "start",
                },
                {
                    "key": "_default",
                    "goto": "ask_password",
                },
            )
    elif banned:
        # This is a banned IP or name!
        string = dedent("""
            |rVous avez été banni(e) et ne pouvez vous connecter.
            Si vous pensez que ce bannissement est une erreur, contactez les administrateurs à
            equipe@vanciamud.fr
        """.strip("\n"))
        caller.sessionhandler.disconnect(caller, string)
        text = ""
        options = {}
    else:
        # We are OK, log us in.
        text = ""
        options = {}
        caller.msg("", options={"echo": True})
        caller.sessionhandler.login(caller, account)

    return text, options


def create_account(caller):
    """Create a new account.

    This node simply prompts the user to entere a username.
    The input is redirected to 'create_username'.

    """
    text = "Entrez le nom de votre nouvel utilisateur."
    options = (
        {
            "key": "_default",
            "goto": "create_username",
        },
    )
    return text, options


def create_username(caller, string_input):
    """Prompt to enter a valid username (one that doesnt exist).

    'string_input' contains the new username.  If it exists, prompt
    the username to retry or go back to the login screen.

    """
    menutree = caller.ndb._menutree
    string_input = string_input.strip()
    account = managers.accounts.get_account_from_name(string_input)

    # If an account with that name exists, a new one will not be created
    if account:
        text = dedent("""
            |rL'utilisateur {} existe déjà.|n
            Entrez un autre nom d'utilisateur, ou entrez |yr|n pour revenir à l'écran d'accueil.
        """.strip("\n")).format(string_input)
        # Loops on the same node
        options = (
            {
                "key": "r",
                "goto": "start",
            },
            {
                "key": "_default",
                "goto": "create_username",
            },
        )
    elif not RE_VALID_USERNAME.search(string_input):
        text = dedent("""
            |rCe nom d'utilisateur n'est pas valide.|n
            Seules des lettres sont acceptées.
            Le nom d'utilisateur doit comporter au moins 3 lettres.
            Entrez un nouveau nom d'utilisateur ou entrez |yr|n pour revenir à l'écran d'accueil.
        """.strip("\n"))
        options = (
            {
                "key": "r",
                "goto": "start",
            },
            {
                "key": "_default",
                "goto": "create_username",
            },
        )
    else:
        # a valid username - continue getting the password
        menutree.accountname = string_input
        # Disables echo for entering password
        caller.msg("", options={"echo": False})
        # Redirects to the creation of a password
        text = "Entrez le mot de passe de ce nouvel utilisateur."
        options = (
            {
                "key": "_default",
                "goto": "create_password",
            },
        )

    return text, options


def create_password(caller, string_input):
    """Ask the user to create a password.

    This node is at the end of the menu for account creation.  If
    a proper MULTI_SESSION is configured, a character is also
    created with the same name (we try to login into it).

    """
    menutree = caller.ndb._menutree
    text = ""
    options = (
        {
            "key": "r",
            "exec": lambda caller: caller.msg("", options={"echo": True}),
            "goto": "start",
        },
        {
            "key": "_default",
            "goto": "create_password",
        },
    )

    password = string_input.strip()
    accountname = menutree.accountname

    if len(password) < LEN_PASSWD:
        # The password is too short
        text = dedent("""
            |rLe mot de passe doit comporter au moins {} caractères.|n
            Entrez un nouveau mot de passe ou entrez |yr|n pour revenir à l'écran d'accueil.
        """.strip("\n")).format(LEN_PASSWD)
    else:
        # Everything's OK.  Create the new player account and
        # possibly the character, depending on the multisession mode
        from evennia.commands.default import unloggedin
        # We make use of the helper functions from the default set here.
        try:
            permissions = settings.PERMISSION_ACCOUNT_DEFAULT
            typeclass = settings.BASE_CHARACTER_TYPECLASS
            new_account = unloggedin._create_account(caller, accountname,
                                                     password, permissions)
            if new_account:
                if settings.MULTISESSION_MODE < 2:
                    default_home = ObjectDB.objects.get_id(
                        settings.DEFAULT_HOME)
                    unloggedin._create_character(caller, new_account,
                                                 typeclass, default_home, permissions)
        except Exception:
            # We are in the middle between logged in and -not, so we have
            # to handle tracebacks ourselves at this point. If we don't, we
            # won't see any errors at all.
            caller.msg(dedent("""
                |rUne erreur inattendue s'est produite..|n  S'il vous plaît, envoyez un e-mail
                à equipe@vanciamud.fr pour signaler ce problème.
            """.strip("\n")))
            logger.log_trace()
        else:
            text = ""
            caller.msg("|gBienvenue ! Votre nouvel utilisateur a bien été créé.|n")
            caller.msg("", options={"echo": True})
            caller.sessionhandler.login(caller, new_account)

    return text, options


def quit(caller):
    caller.sessionhandler.disconnect(caller, "Au revoir ! Déconnexion...")
    return "", {}

# Other functions


def _formatter(nodetext, optionstext, caller=None):
    """Do not display the options, only the text.

    This function is used by EvMenu to format the text of nodes.
    Options are not displayed for this menu, where it doesn't often
    make much sense to do so.  Thus, only the node text is displayed.

    """
    return nodetext


# Commands and CmdSets

class UnloggedinCmdSet(CmdSet):
    "Cmdset for the unloggedin state"
    key = "DefaultUnloggedin"
    priority = 0

    def at_cmdset_creation(self):
        "Called when cmdset is first created."
        self.add(CmdUnloggedinLook())


class CmdUnloggedinLook(Command):
    """
    An unloggedin version of the look command. This is called by the server
    when the account first connects. It sets up the menu before handing off
    to the menu's own look command.
    """
    key = syscmdkeys.CMD_LOGINSTART
    locks = "cmd:all()"
    arg_regex = r"^$"

    def func(self):
        "Execute the menu"
        EvMenu(self.caller, "commands.menu",
               startnode="start", auto_look=False, auto_quit=False,
               cmd_on_exit=None, node_formatter=_formatter)
