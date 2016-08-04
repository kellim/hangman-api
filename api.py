import logging
import endpoints
from protorpc import remote, messages

from models import User, Game
from models import StringMessage, NewGameForm, GameForm
from utils import get_by_urlsafe


USER_REQUEST = endpoints.ResourceContainer(user_name=messages.StringField(1),
                                           email=messages.StringField(2))
GET_GAME_REQUEST = endpoints.ResourceContainer(
    urlsafe_game_key=messages.StringField(1))

NEW_GAME_REQUEST = endpoints.ResourceContainer(NewGameForm)


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
    def get_game(self,request):
        """Return the current game state."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game:
            if not game.game_over:
                return game.to_form('It\'s time to take a turn!')
            else:
                return game.to_form('The game is over!')
        else:
            raise endpoints.NotFoundException('No game was found!')

api = endpoints.api_server([HangmanApi])
