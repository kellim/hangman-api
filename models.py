import csv
import random
from protorpc import messages
from google.appengine.ext import ndb


class User(ndb.Model):
    """User profile"""
    name = ndb.StringProperty(required=True)
    email = ndb.StringProperty()


class Game(ndb.Model):
    """Game Object"""
    allowed_misses = ndb.IntegerProperty(required=True, default=6)
    secret_word = ndb.StringProperty(required=True)
    difficulty = ndb.IntegerProperty(required=True)
    guessed_word = ndb.StringProperty(required=True)
    missed_letters = ndb.StringProperty(required=True, default='')
    misses_left = ndb.IntegerProperty(required=True, default=6)
    game_over = ndb.BooleanProperty(required=True, default=False)
    user = ndb.KeyProperty(required=True, kind='User')

    @classmethod
    def new_game(cls, user, allowed_misses):
        if allowed_misses < 6 or allowed_misses > 10:
            raise ValueError('Allowed misses must be between 6 and 10')
        secret_word = random.choice(Game.generate_word_list())
        game = Game(user=user,
                    allowed_misses=allowed_misses,
                    secret_word=secret_word,
                    difficulty=Game.check_word_difficulty(secret_word),
                    guessed_word=("-" * len(secret_word)),
                    missed_letters='',
                    misses_left=allowed_misses,
                    game_over=False)
        game.put()
        return game

    def to_form(self, message):
        """Retuns a GameForm representation of the Game"""
        form = GameForm()
        form.urlsafe_key = self.key.urlsafe()
        form.user_name = self.user.get().name
        form.misses_left = self.misses_left
        form.missed_letters = self.missed_letters
        form.guessed_word = self.guessed_word
        form.game_over = self.game_over
        form.message = message
        return form

    def end_game(self, won=False):
        self.game_over = True
        self.put()
        # TODO: ADD CODE FOR SCORING

    @staticmethod
    def generate_word_list():
        word_list = []
        with open('words.csv', 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                word_list.append(row[0])
        return word_list

    @staticmethod
    def check_word_difficulty(secret_word):
        """ Return a word difficulty score"""
        # Add 1 to difficulty for each unique letter
        unique_letters = ''.join(set(secret_word))
        difficulty = len(unique_letters)
        # Add additional points to difficulty for infrequent letters
        for c in secret_word:
            if c in "jqxz":
                difficulty += 4
            elif c in "bkv":
                difficulty += 3
            elif c in "cfgmpwy":
                difficulty += 2
        return difficulty


class GameForm(messages.Message):
    """GameForm for outbound game state information"""
    urlsafe_key = messages.StringField(1, required=True)
    misses_left = messages.IntegerField(2, required=True)
    missed_letters = messages.StringField(3, required=True)
    guessed_word = messages.StringField(4, required=True)
    game_over = messages.BooleanField(5, required=True)
    message = messages.StringField(6, required=True)
    user_name = messages.StringField(7, required=True)


class MakeMoveForm(messages.Message):
    """Used to make a move in an existing game"""
    guess = messages.StringField(1, required=True)


class NewGameForm(messages.Message):
    """Used to create a new game"""
    user_name = messages.StringField(1, required=True)
    allowed_misses = messages.IntegerField(2, default=6)


class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    message = messages.StringField(1, required=True)
