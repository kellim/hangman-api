import logging
import endpoints
from protorpc import remote, messages

from models import User, Game
from models import StringMessage, NewGameForm, GameForm, MakeMoveForm
from utils import get_by_urlsafe


USER_REQUEST = endpoints.ResourceContainer(user_name=messages.StringField(1),
                                           email=messages.StringField(2))
GET_GAME_REQUEST = endpoints.ResourceContainer(
    urlsafe_game_key=messages.StringField(1))
NEW_GAME_REQUEST = endpoints.ResourceContainer(NewGameForm)
MAKE_MOVE_REQUEST = endpoints.ResourceContainer(
    MakeMoveForm,
    urlsafe_game_key=messages.StringField(1))


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
        user = User(name=request.user_name, email=request.email)
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
                return game.to_form('It\'s time to take a turn!')
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
                return game.to_form('Turn failed: more than 1 character '
                                    'entered!')
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
                    message += ' You win!'
            else:  # the user guessed a letter NOT in the secret word
                game.misses_left -= 1
                game.missed_letters += request.guess
                message = 'The letter you guessed is not in the word!'
            if game.misses_left < 1:
                game.end_game(False)
                message += ' You lost!'
            game.put()
            return game.to_form(message)

api = endpoints.api_server([HangmanApi])
