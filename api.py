import logging
import endpoints
from protorpc import remote, messages

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


@endpoints.api(name='hangman', version='v1')
class HangmanApi(remote.Service):
    """Game API"""
    @endpoints.method(request_message=USER_REQUEST,
                      response_message=StringMessage,
                      path='user',
                      name='create_user',
                      http_method='POST')
    def create_user(self, request):
        """Create a User. Requires a unique username"""
        if User.query(User.name == request.user_name).get():
            raise endpoints.ConflictException(
                'A User with that name already exists!')
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
        """Creates new game"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                'A User with that name does not exist!')
        try:
            game = Game.new_game(user.key, request.allowed_misses)
        except ValueError:
            raise endpoints.BadRequestException('Allowed misses must be '
                                                ' between 6 and 10!')
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
        """Makes a move. Returns a game state with message"""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game.game_over:
            return game.to_form('Game already over!')
        else:
            if not len(request.guess) == 1:
                return game.to_form('Turn failed: Exactly 1 character '
                                    'must be entered!')
            elif not request.guess.isalpha():
                return game.to_form('Turn failed: non-alphabetic character '
                                    'entered!')
            elif request.guess in game.missed_letters or request.guess \
                    in game.guessed_word:
                return game.to_form('Turn failed: that letter was already '
                                    'guessed!')
            guessed_word_list = list(game.guessed_word)
            if request.guess in game.secret_word:
                message = 'That letter is in the word!'
                # Add the letter to guessed_word in place of dashes
                for index, ch in enumerate(game.secret_word):
                    if ch == request.guess:
                        guessed_word_list[index] = ch
                game.guessed_word = ''.join(guessed_word_list)
                # End the game if the user guessed the full secret word
                if game.guessed_word == game.secret_word:
                    game.end_game(True)
                    message += ' You win! The secret word is %s.' \
                               % game.secret_word
            else:  # the user guessed a letter NOT in the secret word
                game.misses_left -= 1
                game.missed_letters += request.guess
                message = 'The letter you guessed is not in the word!'
            if game.misses_left < 1:
                game.end_game(False)
                message += ' You lost! The secret word was %s.' \
                           % game.secret_word
            game.put()
            return game.to_form(message)

    @endpoints.method(request_message=USER_REQUEST,
                      response_message=ScoreForms,
                      path='scores/user/{user_name}',
                      name='get_user_scores',
                      http_method='GET')
    def get_user_scores(self, request):
        """Returns all of an individual user's scores"""
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
        """Returns a list of high scores of games that were won"""
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
        """Returns all of an individual user's active games"""
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
                      http_method='PUT')
    def cancel_game(self, request):
        game_to_cancel = get_by_urlsafe(request.urlsafe_game_key, Game)
        if not game_to_cancel:
            raise endpoints.NotFoundException(
                'That game does not exist!'
            )
        if game_to_cancel.game_over:
            return StringMessage(message='Failed to cancel: Game already over!')
        else:
            game_to_cancel.key.delete()
            return StringMessage(message='Game has been cancelled!')

api = endpoints.api_server([HangmanApi])
