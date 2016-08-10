import csv
import random
from datetime import date
from protorpc import messages
from google.appengine.ext import ndb


class User(ndb.Model):
    """User Profile"""
    name = ndb.StringProperty(required=True)
    email = ndb.StringProperty()
    wins = ndb.IntegerProperty(required=True, default=0)
    total_games = ndb.IntegerProperty(required=True, default=0)
    win_ratio = ndb.FloatProperty()
    won_games_difficulty = ndb.IntegerProperty(required=True, default=0)
    avg_won_difficulty = ndb.FloatProperty()
    misses = ndb.IntegerProperty(required=True, default=0)
    avg_misses = ndb.FloatProperty()

    def to_rankings_form(self):
        """Returns UserRankingForm representation of user rankings."""
        return UserRankingForm(
            user_name=self.name,
            win_ratio=self.win_ratio,
            avg_won_difficulty=self.avg_won_difficulty,
            avg_misses=self.avg_misses,
            wins=self.wins,
            total_games=self.total_games)


class Game(ndb.Model):
    """Game Object"""
    allowed_misses = ndb.IntegerProperty(required=True, default=6)
    secret_word = ndb.StringProperty(required=True)
    # difficulty is not selectable, so for now it is only used as
    # a tiebreaker in high scores and user rankings.
    difficulty = ndb.IntegerProperty(required=True)
    # guessed_word is the word as seen by the user which will
    # have dashes for letters that have not been guessed yet.
    guessed_word = ndb.StringProperty(required=True)
    missed_letters = ndb.StringProperty(required=True, default='')
    # misses can be between 6 and 10. 6 is default so the frontend
    # could represent head, body, 2 arms and 2 legs for the hangman
    # picture. At 10 you could add hands and feet.
    misses_left = ndb.IntegerProperty(required=True, default=6)
    game_over = ndb.BooleanProperty(required=True, default=False)
    user = ndb.KeyProperty(required=True, kind='User')
    # turn_history will be array of OrderedDicts and converted
    # to JSON before being returned by endpoint.
    turn_history = ndb.PickleProperty(default=[])

    @classmethod
    def new_game(cls, user, allowed_misses):
        """Creates a new game"""
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
        """Retuns a GameForm representation of the Game."""
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
        """Ends the game."""
        self.game_over = True
        self.put()
        # Add the game to the score 'board'
        score = Score(user=self.user, date=date.today(), won=won,
                      misses=self.allowed_misses - self.misses_left,
                      difficulty=self.difficulty)
        score.put()
        user = User.query(User.key == self.user).get()
        # Add data to User Object for ranking users.
        user.total_games += 1
        user.misses += self.allowed_misses - self.misses_left
        user.avg_misses = user.misses / float(user.total_games)
        if won:
            user.wins += 1
            user.won_games_difficulty += self.difficulty
            user.avg_won_difficulty = \
                user.won_games_difficulty / float(user.wins)
        user.win_ratio = user.wins / float(user.total_games)
        user.put()

    @staticmethod
    def generate_word_list():
        """Returns secret word list."""
        word_list = []
        with open('words.csv', 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                word_list.append(row[0])
        return word_list

    @staticmethod
    def check_word_difficulty(secret_word):
        """ Returns a word difficulty score."""
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


class Score(ndb.Model):
    """Score Object"""
    user = ndb.KeyProperty(required=True, kind='User')
    date = ndb.DateProperty(required=True)
    won = ndb.BooleanProperty(required=True)
    misses = ndb.IntegerProperty(required=True)
    difficulty = ndb.IntegerProperty(required=True)

    def to_form(self):
        return ScoreForm(user_name=self.user.get().name,
                         won=self.won,
                         date=str(self.date),
                         misses=self.misses,
                         difficulty=self.difficulty)


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
    """Used to make a move in an existing game."""
    guess = messages.StringField(1, required=True)


class ScoreForm(messages.Message):
    user_name = messages.StringField(1, required=True)
    date = messages.StringField(2, required=True)
    won = messages.BooleanField(3, required=True)
    misses = messages.IntegerField(4, required=True)
    difficulty = messages.IntegerField(5, required=True)


class NewGameForm(messages.Message):
    """Used to create a new game."""
    user_name = messages.StringField(1, required=True)
    allowed_misses = messages.IntegerField(2, default=6)


class ScoreForms(messages.Message):
    """Return multiple ScoreForms."""
    items = messages.MessageField(ScoreForm, 1, repeated=True)


class UserGameForms(messages.Message):
    """Returns multiple GameForms for a specific user."""
    items = messages.MessageField(GameForm, 1, repeated=True)


class UserRankingForm(messages.Message):
    """Return User Rankings."""
    user_name = messages.StringField(1, required=True)
    win_ratio = messages.FloatField(2, required=True)
    wins = messages.IntegerField(3, required=True)
    total_games = messages.IntegerField(4, required=True)
    avg_won_difficulty = messages.FloatField(5)
    avg_misses = messages.FloatField(6)


class UserRankingForms(messages.Message):
    """Return multiple UserRankingForms."""
    items = messages.MessageField(UserRankingForm, 1, repeated=True)


class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    message = messages.StringField(1, required=True)
