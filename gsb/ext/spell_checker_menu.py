"""Provides the SpellCheckerMenu class."""

import re
from functools import partial

from enchant import Dict

from gsb import intercept
from gsb.caller import Caller

dictionary = Dict()


class _SpellCheckerMenuBase:
    def __init__(self, text, after):

        self.text = text
        self.after = after


class SpellCheckerMenu(intercept.Menu, _SpellCheckerMenuBase):
    """A spell checker menu."""

    def __init__(self, ignored=[]):
        super().__init__()

        self.ignored = ignored
        self.recursive = True
        self.persistent = True

    def do_abort(self, caller):
        """Return to what we were doing."""
        self.send(self.aborted, caller)
        caller.text = self.text
        caller.connection.parser = self.restore_parser
        self.after(caller)
        return True

    def add_word(self, caller):
        """Add caller.word to a personal dictionary."""
        raise NotImplementedError

    def check_word(self, caller):
        """Spell check the word found in caller.text. Should return True if the
        word is OK or False otherwise."""
        return False

    def explain(self, connection):
        """Build the menu first."""
        self.word = None  # The misspelled word.
        self.labels.clear()
        self.items.clear()
        for word in re.findall("[a-zA-Z'-]+", self.text):
            if dictionary.check(word) or self.check_word(Caller(connection, text=word)):
                continue
            self.word = word
            self.title = "Misspelled word: %s." % word
            self.add_label("Suggestions", None)
            for suggestion in dictionary.suggest(word):
                self.item(suggestion)(partial(self.replace, word=suggestion))
            self.add_label("Actions", self.items[-1])
            self.item("Ignore")(self.ignore)
            self.item("Add to personal dictionary")(self.add)
            self.item("Edit Word")(self.edit)
            return super(SpellCheckerMenu, self).explain(connection)
        caller = Caller(connection, text=self.text.format(*self.ignored))
        self.after(caller)
        caller.connection.parser = self.restore_parser

    def add(self, caller):
        """Call self.add_word then explain ourselves."""
        self.add_word(caller)
        caller.connection.parser = self

    def replace(self, caller, word=None):
        """Replace a misspelled word with word. If word is None, use
        caller.text."""
        if word is None:
            word = caller.text  # By-hand replacement.
        self.text = self.text.replace(self.word, word)
        caller.connection.notify("Replaced %s with %s.", self.word, word)
        caller.connection.parser = self

    def ignore(self, caller):
        """Ignore all occurrances of a misspelled word."""
        word = self.word
        if word not in self.ignored:
            self.ignored.append(word)
        self.text = self.text.replace(word, "{%d}" % self.ignored.index(word))
        caller.connection.parser = self

    def edit(self, caller):
        """Enter the replacement by hand."""
        caller.connection.notify("Enter the new word:")
        caller.connection.notify(intercept.Reader, self.replace)
