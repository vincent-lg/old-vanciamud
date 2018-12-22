# -*- coding: utf-8 -*-

"""General commands."""

from evennia import AccountDB
from evennia.server.sessionhandler import SESSIONS
from evennia.utils.ansi import raw

from commands.command import Command

class CmdAfk(Command):

    """
    Passe AFK.

    Syntaxe :
        afk [message]

    Passe AFK, précisant un message optionnel. Entrez la commande sans argument pour
    quitter l'AFK.

    Exemple :
        afk jusqu'à 20h

    """

    key = "afk"
    aliases = ["away"]

    def func(self):
        """Command body."""
        caller = self.caller
        message = raw(self.args.strip())

        if caller.db.afk:
            del caller.db.afk
            self.msg("|gVous n'êtes plus AFK.|n")
        else:
            if message:
                self.msg("|gVous passez AFK|n {}.".format(message))
            else:
                self.msg("|gVous passez AFK.")
            caller.db.afk = message or True


class CmdEmote(Command):

    """
    Effectue une action RP dans la salle où vous vous trouvez.

    Syntaxe :
        emote <message à afficher>

    Cette commande permet d'effectuer une action RP dans la salle où vous vous
    trouvez.

    Exemple :
        emote sourit.

    """

    key = "emote"
    aliases = ["pose", ":", "me"]

    def func(self):
        caller = self.caller
        message = raw(self.args.strip())

        if not message:
            self.msg("|rPrécisez une action à faire avec emote.|n")
            return

        caller.location.msg_contents("{who} {what}.", mapping=dict(who=caller, what=message))


class CmdSay(Command):

    """
    Dit quelque chose dans la salle où vous vous trouvez.

    Syntaxe :
        say <message à dire>

    Dit quelque chose dans la salle où vous vous trouvez.

    Exemple :
        say Bonjour tout le monde !

    """

    key = "say"
    aliases = ["dire"]

    def func(self):
        caller = self.caller
        message = raw(self.args.strip())

        if not message:
            self.msg("|rQue voulez-vous dire ?|n")
            return

        self.msg("|gVous dites|n : {}".format(message))
        caller.location.msg_contents("|g{who} dit|n : {what}", exclude=[self], mapping=dict(who=caller, what=message))


class CmdTell(Command):

    """
    Dit quelque chose HRP à un joueur présent ou non.

    Syntaxe :
        tell <nom du joueur> <message>

    Dit quelque chose sans contrainte RP et sans que les autres ne voient le
    message. Précisez en premier paramètre le nom du joueur sans espace, et en
    second paramètre le message à lui envoyer.

    Exemple :
        tell Kredh Cela marche

    """

    key = "tell"
    aliases = ["parler", "page"]

    def func(self):
        caller = self.caller
        message = raw(self.args.strip())

        if not message:
            self.msg("|rÀ qui voulez-vous parler ?|n")
            return

        if " " not in message:
            self.msg("|rPrécisez le nom du joueur, un espace et le message à lui envoyer.|n")
            return

        name, message = message.split(" ", 1)
        try:
            account = AccountDB.objects.get(username__iexact=name)
        except AccountDB.DoesNotExist:
            self.msg("|rL'utilisateur {} n'existe pas.".format(name))
            return

        self.msg("Vous dites à {} : {}".format(account.username, message))
        account.msg("{} vous dit : {}".format(caller.account.username, message))


class CmdWho(Command):

    """
    Affiche la liste des connectés.

    Syntaxe :
        who

    """

    key = "who"
    aliases = []

    def func(self):
        """Command body."""
        sessions = list(SESSIONS.get_sessions())
        sessions = [session for session in sessions if session.puppet]
        sessions.sort(key=lambda session: session.puppet.key)

        lines = []
        for session in sessions:
            puppet = session.puppet
            afk = ""
            if puppet.db.afk:
                afk = "AFK"
                if isinstance(puppet.db.afk, basestring):
                    afk += " (" + puppet.db.afk + ")"

            lines.append("|   {:<15} {:<55} |".format(puppet.key, afk))

        lines.insert(0, "+" + "-" * 75 + "+")
        lines.append("+" + "-" * 75 + "+")
        lines.append("|   " + "{} utilisateur{s} connecté{s}".format(len(sessions), s="s" if len(sessions) > 1 else "").ljust(72) + " |")
        lines.append("+" + "-" * 75 + "+")
        self.msg("\n".join(lines))
