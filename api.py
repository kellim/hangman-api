import endpoints
import json
from collections import OrderedDict
from protorpc import remote, messages
from google.appengine.api import memcache
from google.appengine.api import taskqueue

from models import User, Game, Score
from models import (StringMessage, NewGameForm, GameForm, MakeMoveForm,
                    ScoreForms, UserGameForms, UserRankingForms)
from utils import get_by_urlsafe


USER_REQUEST = endpoints.ResourceContainer(user_name=messages.StringField(1),
                                           email=messages.StringField(2))
GET_GAME_REQUEST = endpoints.ResourceContainer(
    urlsafe_game_key=messages.StringField(1))
NEW_GAME_REQUEST = endpoints.ResourceContainer(NewGameForm)
MAKE_MOVE_REQUEST = endpoints.ResourceContainer(
    MakeMoveForm,
    urlsafe_game_key=messages.StringField(1))
CANCEL_GAME_REQUEST = endpoints.ResourceContainer(
    urlsafe_game_key=messages.StringField(1))
HIGH_SCORES_REQUEST = endpoints.ResourceContainer(
    number_of_results=messages.IntegerField(1))
MEMCACHE_MISSES_REMAINING = 'MISSES REMAINING'


@endpoints.api(name='hangman', version='v1')
class HangmanApi(remote.Service):
    """Game API"""
    @endpoints.method(request_message=USER_REQUEST,
                      response_message=StringMessage,
                      path='user',
                      name='create_user',
                      http_method='POST')
    def create_user(self, request):
        """Create a User. Requires a unique username."""
        if not request.user_name:
            raise endpoints.BadRequestException(
                'Username is required!')
        elif User.query(User.name == request.user_name).get():
            raise endpoints.ConflictException(
                'A User with that name already exists!')
        elif not request.user_name.isalnum():
            raise endpoints.BadRequestException(
                'Username must be alphanumeric!')
        elif len(request.user_name) < 3:
            raise endpoints.BadRequestException(
                'Username must be at least 3 characters!')
        user = User(name=request.user_name, email=request.email, wins=0,
                    total_games=0, won_games_difficulty=0, misses=0)
        user.put()
        return StringMessage(message='User {} created!'.format(
            request.user_name))

    @endpoints.method(request_message=NEW_GAME_REQUEST,
                      response_message=GameForm,
                      path='game',
                      name='new_game',
                      http_method='POST')
    def new_game(self, request):
        """Creates new game."""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                'A User with that name does not exist!')
        try:
            game = Game.new_game(user.key, request.allowed_misses)
        except ValueError:
            raise endpoints.BadRequestException('Allowed misses must be '
                                                ' between 6 and 10!')
        # Use a task queue to update the average misses remaining.
        # This operation is not needed to complete the creation of a new game
        # so it is performed out of sequence.
        taskqueue.add(url='/tasks/cache_average_misses')
        return game.to_form('Enjoy playing Hangman!')

    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='get_game',
                      http_method='GET')
    def get_game(self, request):
        """Return the current game state."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game:
            if not game.game_over:
                return game.to_form('Time to take a turn!')
            else:
                return game.to_form('The game is over!')
        else:
            raise endpoints.NotFoundException('No game was found!')

    @endpoints.method(request_message=MAKE_MOVE_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='make_move',
                      http_method='PUT')
    def make_move(self, request):
        """Makes a move. Returns a game state with message."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if not game:
            raise endpoints.NotFoundException('No game was found!')
        if game.game_over:
            raise endpoints.NotFoundException('That game is already over. '
                                              'Please enter an active game!')
        else:
            guess = request.guess.lower()
            if not len(guess) == 1:
                raise endpoints.BadRequestException(
                    'Exactly 1 character must be entered!')
            elif not guess.isalpha():
                raise endpoints.BadRequestException(
                    'Non-alphabetic character entered!')
            elif guess in game.missed_letters or guess in game.guessed_word:
                        return game.to_form('That letter was already '
                                            'guessed. Try a different '
                                            'letter!')
            # Converting guessed_word to list lets you easily replace
            # dashes with correctly guessed letters.
            guessed_word_list = list(game.guessed_word)
            if guess in game.secret_word:
                message = 'Guessed letter is in secret word!'
                # Add the letter to guessed_word in place of dashes
                for index, ch in enumerate(game.secret_word):
                    if ch == guess:
                        guessed_word_list[index] = ch
                game.guessed_word = ''.join(guessed_word_list)
                # End the game if the user guessed the full secret word
                if game.guessed_word == game.secret_word:
                    game.end_game(True)
                    message += ' You win! The secret word is %s.' \
                               % game.secret_word
            else:  # the user guessed a letter NOT in the secret word
                game.misses_left -= 1
                game.missed_letters += guess
                message = 'Guessed letter not in secret word!'
            if game.misses_left < 1:
                game.end_game(False)
                message += ' You lost! The secret word was %s.' \
                           % game.secret_word
            # Save data for turn history. Used OrderedDict so it
            # maintains the proper order.
            history = OrderedDict()
            history['guess'] = str(guess)
            history['result'] = str(message)
            history['word'] = str(game.guessed_word)
            game.turn_history.append(history)
            game.put()
            return game.to_form(message)

    @endpoints.method(request_message=USER_REQUEST,
                      response_message=ScoreForms,
                      path='scores/user/{user_name}',
                      name='get_user_scores',
                      http_method='GET')
    def get_user_scores(self, request):
        """Returns all of an individual user's scores."""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                'A User with that name does not exist!')
        scores = Score.query(Score.user == user.key)
        return ScoreForms(items=[score.to_form() for score in scores])

    @endpoints.method(request_message=HIGH_SCORES_REQUEST,
                      response_message=ScoreForms,
                      path='scores/high',
                      name='get_high_scores',
                      http_method='GET')
    def get_high_scores(self, request):
        """Returns a list of high scores of games that were won."""
        # Scores are sorted by least amount of misses. A tiebreaker
        # is word difficulty.
        scores = \
            Score.query(Score.won == True).order(
                Score.misses).order(-Score.difficulty)
        scores = scores.fetch(limit=request.number_of_results)
        return ScoreForms(items=[score.to_form() for score in scores])

    @endpoints.method(request_message=HIGH_SCORES_REQUEST,
                      response_message=UserRankingForms,
                      path='scores/user-rankings',
                      name='get_user_rankings',
                      http_method='GET')
    def get_user_rankings(self, request):
        """Returns user rankings list"""
        # Users must have completed at least one game to be in the
        # rankings list. Ranking list is sorted by the win ratio,
        # then by the average number of misses and finally average
        # difficulty (which is not selected by user, so not placing
        # much importance on difficulty for now.)
        users = \
            User.query(User.win_ratio != None).order(-User.win_ratio).order(
                User.avg_misses).order(-User.avg_won_difficulty)
        users = users.fetch(limit=request.number_of_results)
        return UserRankingForms(
            items=[user.to_rankings_form() for user in users])

    @endpoints.method(request_message=USER_REQUEST,
                      response_message=UserGameForms,
                      path='games/active/user/{user_name}',
                      name='get_user_games',
                      http_method='GET')
    def get_user_games(self, request):
        """Returns all of an individual user's active games."""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                'A User with that name does not exist!')
        games = Game.query(Game.user == user.key, Game.game_over == False)
        return UserGameForms(items=[game.to_form('Time to take a turn!') for game in games])

    @endpoints.method(request_message=CANCEL_GAME_REQUEST,
                      response_message=StringMessage,
                      path='game/cancel/{urlsafe_game_key}',
                      name='cancel_game',
                      http_method='DELETE')
    def cancel_game(self, request):
        """Cancel game by deleting it from datastore."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if not game:
            raise endpoints.NotFoundException(
                'No game was found!')
        if game.game_over:
            return StringMessage(message='Failed to cancel: Game already over!')
        else:
            game.key.delete()
            return StringMessage(message='Game has been cancelled!')

    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=StringMessage,
                      path='game/history/{urlsafe_game_key}',
                      name='get_game_history',
                      http_method='GET')
    def get_game_history(self, request):
        """Returns turn history for a game."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if not game:
            raise endpoints.NotFoundException('No game was found!')
        elif not game.turn_history:
            raise endpoints.NotFoundException('No history for this game was found!')
        else:
            # Convert turn history from OrderedDict to JSON.
            history = json.dumps(game.turn_history)
            # Remove the multiple \" added during JSON conversion
            history = str(history).replace('\"', '')
            return StringMessage(message=history)

    @endpoints.method(response_message=StringMessage,
                      path='games/average_misses',
                      name='get_average_misses_remaining',
                      http_method='GET')
    def get_average_misses(self, request):
        """Get the cached average misses remaining"""
        return StringMessage(message=memcache.get(MEMCACHE_MISSES_REMAINING) or '')

    @staticmethod
    def _cache_average_misses():
        """Populates memcache with the average misses remaining for Games"""
        games = Game.query(Game.game_over == False).fetch()
        if games:
            count = len(games)
            total_misses_remaining = sum([game.misses_left
                                         for game in games])
            average = float(total_misses_remaining)/count
            memcache.set(MEMCACHE_MISSES_REMAINING,
                         'The average misses remaining is {:.2f}'.format(average))

api = endpoints.api_server([HangmanApi])
