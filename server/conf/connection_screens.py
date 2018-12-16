# -*- coding: utf-8 -*-
"""
Connection screen

Texts in this module will be shown to the user at login-time.

Evennia will look at global string variables (variables defined
at the "outermost" scope of this module and use it as the
connection screen. If there are more than one, Evennia will
randomize which one it displays.

The commands available to the user when the connection screen is shown
are defined in commands.default_cmdsets. UnloggedinCmdSet and the
screen is read and displayed by the unlogged-in "look" command.

"""

from django.conf import settings
from evennia import utils

CONNECTION_SCREEN = r"""
Bienvenue sur l'ancien
  __     __               _       __  __ _   _ ____
  \ \   / /_ _ _ __   ___(_) __ _|  \/  | | | |  _ \
   \ \ / / _` | '_ \ / __| |/ _` | |\/| | | | | | | |
    \ V / (_| | | | | (__| | (_| | |  | | |_| | |_| |
     \_/ \__,_|_| |_|\___|_|\__,_|_|  |_|\___/|____/


                                        Basé sur |gEvennia {}|n""" \
    .format(utils.get_evennia_version())
