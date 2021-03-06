# -*- coding: utf-8 -*-

"""The login menu."""

import os
import re
import string
from textwrap import dedent

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from evennia import Command, CmdSet
from evennia import logger
from evennia import managers
from evennia import ObjectDB
from evennia.server.models import ServerConfig
from evennia import syscmdkeys
from evennia.utils.evmenu import EvMenu
from evennia.utils.utils import random_string_from_module
from web.mailgun.utils import send_email

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
            |rNotez qu'il s'agit bien du nom du personnage, pas du nom du compte.|n

            Entrez votre nom d'utilisateur ou |yNOUVEAU|n pour en créer un.
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
    elif account.email and not any([account.db.valid, account.db.sent_validation, account.db.validation_code]):
        # This account isn't valid yet, send an email, update the password
        # Generate a random password
        caller.ndb._menutree.account = account
        password = _generate_password(6, string.lowercase + string.digits)
        account.set_password(password, force=True)
        send_email("NOREPLY", account.email, "[VanciaMUD] Demande de récupération de l'utilisateur {}".format(account.username), dedent("""
                Bonjour,

                Une demande de récupération de l'utilisateur {username} a été faite depuis vanciamud.fr.
                Cet e-mail vous est envoyé car l'utilisateur en question n'a pas été validé.
                Pour le valider, vous devez entrer dans votre client MUD le mot de passe suivant :

                Mot de passe temporaire : {password}

                Une fois connecté, vous aurez la possibilité de changer ce mot de passe, étape
                recommandée pour des raisons de sécurité.

                Si cette demande n'a pas été faite par vous, reprenez au plus vite le contrôle
                de votre utilisateur et changez de mot de passe. Si le problème persiste, vous
                pouvez également contacter les administrateurs de VanciaMUD, à l'adresse admin@vanciamud.fr .

                À très bientôt,

                L'équipe des administrateurs de VanciaMUD
        """.format(username=account.username, password=password)).strip(), store=False)
        account.db.sent_validation = True
        text = dedent("""
            Un e-mail de confirmation a été envoyé à l'ancienne adresse e-mail de cet utilisateur.
            Cet e-mail contient le mot de passe temporaire de l'utilisateur, que vous devez à
            présent entrer dans votre client MUD. Si vous perdez la connexion, reconnectez-vous
            en entrant le même nom d'utilisateur. Si votre ancienne adresse e-mail n'est plus
            valide et que vous ne recevez pas l'e-mail de confirmation, envoyez un e-mail
            à admin@vanciamud.fr en précisant votre ancienne adresse e-mail à des fins
            d'identification.

            Entrez le mot de passe temporaire reçu par e-mail :
        """).strip()
        options = (
            {
                "key": "_default",
                "goto": "check_temporary_password",
            },
        )
    elif not account.db.valid and account.db.sent_validation:
        caller.ndb._menutree.account = account
        text = dedent("""
            Entrez le mot de passe temporaire reçu par e-mail :
        """).strip()
        options = (
            {
                "key": "_default",
                "goto": "check_temporary_password",
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
            admin@vanciamud.fr
        """.strip("\n"))
        caller.sessionhandler.disconnect(caller, string)
        text = ""
        options = {}
    elif not account.email:
        text = dedent("""
            Vous n'avez pas précisé d'adresse e-mail valide pour ce compte. Il vous faut préciser
            une adresse e-mail valide. Un e-mail vous sera envoyé à cette adresse, contenant un code
            de validation à 4 chiffres.

            Entrez votre adresse e-mail :
        """).strip()
        options = (
            {
                "key": "_default",
                "goto": "create_email_address",
            },
        )
    elif account.db.validation_code:
        text = dedent("""
            Un code de validaiton à 4 chiffres vous a précédemment été envoyé par e-mail.
            Veuillez entrer ce code pour valider cet utilisateur.

            Code à 4 chiffres :
        """).strip()
        options = (
            {
                "key": "_default",
                "goto": "validate_account",
            },
        )
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
        from evennia.commands.default import unloggedin
        try:
            permissions = settings.PERMISSION_ACCOUNT_DEFAULT
            typeclass = settings.BASE_CHARACTER_TYPECLASS
            new_account = unloggedin._create_account(caller, accountname,
                                                     password, permissions)
            if new_account:
                new_account.email = ""
                new_account.save()
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
                à admin@vanciamud.fr pour signaler ce problème.
            """.strip("\n")))
            logger.log_trace()
        else:
            menutree.account = new_account
            caller.msg("", options={"echo": True})
            text = dedent("""
                Le nouvel utilisateur a bien été créé.

                Pour l'utiliser, il vous faut préciser une adresse e-mail valide. Un code
                de validation vous sera envoyé par e-mail. Vous devrez entrer ce code de
                validation dans votre client pour utiliser ce compte.

                Veuillez entrer une adresse e-mail valide :
            """).strip()
            options = (
                {
                    "key": "_default",
                    "goto": "create_email_address",
                },
            )

    return text, options

def create_email_address(caller, email_address):
    """Validate and test the received email address."""
    menutree = caller.ndb._menutree
    account = menutree.account
    text = ""
    options = (
        {
            "key": "_default",
            "desc": "Enter a valid email address.",
            "goto": "create_email_address",
        },
    )

    email_address = email_address.strip()

    # Try to validate the email address
    try:
        validate_email(email_address)
    except ValidationError:
        valid = False
    else:
        valid = True

    if not valid:
        # The email address doesn't seem to be valid
        text = dedent("""
            |rDésolé, l'adresse e-mail {} ne semble pas valide.|n

            Essayez d'entrer une adresse e-mail de nouveau.
        """.strip("\n")).format(email_address)
    else:
        account.email = email_address
        account.save()

        # Generates the 4-digit validation code
        validation_code = _generate_password(4, string.digits)
        account.db.validation_code = validation_code
        send_email("NOREPLY", account.email, "[VanciaMUD] Validation de l'utilisateur {}".format(account.username), dedent("""
                Bonjour,

                Le nouvel utilisateur {username} a été créé sur vanciamud.fr.
                Cet e-mail vous est envoyé car l'utilisateur en question a précisé cette adresse
                e-mail. Pour commencer à jouer avec cet utilisateur, il vous suffit d'entrer
                le code à 4 chiffres suivant :

                Code de validation : {validation_code}

                Si cette demande n'a pas été faite par vous, ignorez simplement ce message,
                ou contacter un administrateur si d'autres e-mails similaires arrivent dans
                votre boîte de réception : admin@vanciamud.fr.

                À très bientôt,

                L'équipe des administrateurs de VanciaMUD
        """.format(username=account.username, validation_code=validation_code)).strip(), store=False)
        text = dedent("""
            Un e-mail de confirmation a été envoyé à cette adresse e-mail.
            Cet e-mail contient le code de validation de l'utilisateur, que vous devez à
            présent entrer dans votre client MUD. Si vous perdez la connexion, reconnectez-vous
            en entrant le même nom d'utilisateur.

            Entrez le code de validation à 4 chiffres :
        """).strip()
        options = (
            {
                "key": "_default",
                "goto": "validate_account",
            },
        )

    return text, options

def validate_account(caller, input):
    """Prompt the user to enter the received validation code."""
    text = ""
    options = (
        {
            "key": "_default",
            "desc": "Enter the validation code.",
            "goto": "validate_account",
        },
    )

    menutree = caller.ndb._menutree
    account = menutree.account
    if account.db.validation_code != input.strip():
        text = dedent("""
            |rDésolé, le code de validation spécifié {} ne correpsond pas à celui attendu par cet utilisateur.
            Est-ce bien le code que vous avez reçu par e-mail ? Vous pouvez essayer de
            l'entrer à nouveau.
        """.strip("\n")).format(input.strip())
    else:
        text = ""
        options = {}
        account.db.valid = True
        account.attributes.remove("validation_code")
        account.record_email_address()
        caller.msg("|gBienvenue sur l'ancien VanciaMUD !|n")
        caller.sessionhandler.login(caller, account)

    return text, options


def quit(caller):
    caller.sessionhandler.disconnect(caller, "Au revoir ! Déconnexion...")
    return "", {}


def check_temporary_password(caller, string_input):
    """Check the temporary password."""
    menutree = caller.ndb._menutree
    string_input = string_input.strip()
    account = menutree.account
    password_attempts = getattr(menutree, "password_attempts", 0)
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
                    "key": "_default",
                    "goto": "check_temporary_password",
                },
            )
    else:
        text = dedent("""
                Mot de passe temporaire valide.

                Changement de mot de passe : entrez un nouveau mot de passe pour cet utilisateur.

                Nouveau mot de passe :
        """).strip()
        options = (
            {
                "key": "_default",
                "goto": "change_temporary_password",
            },
        )

    return text, options

def change_temporary_password(caller, string_input):
    """Change the temporary password."""
    menutree = caller.ndb._menutree
    string_input = string_input.strip()
    account = menutree.account

    if account.validate_password(string_input):
        account.set_password(string_input)
        account.db.valid = True
        text = ""
        options = {}
        caller.msg("", options={"echo": True})
        caller.sessionhandler.login(caller, account)
    else:
        text = "|rCe mot de passe n'est pas valide.|n Entrez un nouveau mot de passe :"
        options = (
            {
                "key": "_default",
                "goto": "change_temporary_password",
            },
        )

    return text, options

# Other functions


def _formatter(nodetext, optionstext, caller=None):
    """Do not display the options, only the text.

    This function is used by EvMenu to format the text of nodes.
    Options are not displayed for this menu, where it doesn't often
    make much sense to do so.  Thus, only the node text is displayed.

    """
    return nodetext

def _generate_password(length, charset):
    """
    Return a randomly-generated password.

    Args:
        length (int): the length of the password to generate.
    charset (str, iterable): the charset to generate from.

    Note:
        The generated password will only contain characters from the charset.

    Returns:
        password (str): the randomly-generated password.

    Example:
        >>> import string
        >>> _generate_password(6, string.lowercase + string.digits)
        'zf3x97pc'

    """
    random_bytes = os.urandom(length)
    indices = [int(len(charset) * (ord(byte) / 256.0)) for byte in random_bytes]
    return "".join([charset[index] for index in indices])


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
