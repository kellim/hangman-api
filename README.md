# Hangman API

## About
This hangman backend uses Google App Engine and has endpoints for playing the 
game and for information/statistics about games and scores. It is my submission 
for the Design a Game project for Udacity's Full Stack Web Developer Nanodegree. 
It uses/adapts some [skeleton code from Udacity's Guess a Number game]
(https://github.com/udacity/FSND-P4-Design-A-Game).

## Set-Up Instructions:
1.  Update the value of `application` in `app.yaml.config` to the app ID you have 
    registered in the App Engine admin console and would like to use to host your 
    instance of this sample, then rename it to `app.yaml`.
1.  Run the app with the devserver using `dev_appserver.py DIR`, and ensure it's
    running by visiting the API Explorer - by default `localhost:8080/_ah/api/explorer`.
1.  (Optional) Generate your client library(ies) with the endpoints tool.
    Deploy your application.

##Game Description:
Each game begins with a secret word chosen by the app, and the user will have
to guess the word within the amount of allowed misses. An amount of 6 to 10
misses can be chosen before starting the game, with the default being 6.

The `get_game` endpoint will provide the user with information needed to start the game.
A string of dashes represents "blanks" in the word, or letters that have not been guessed
correctly yet. Note that as a user guesses letters correctly, these blanks will be replaced
with the guessed letters. They will also be provided with how many misses are available, 
which is how many times they can guess a wrong letter in the word.

Guesses will be sent to the `make_move` endpoint which will reply with a message like 
"Guessed letter not in secret word!" or "Guessed letter is in secret word!" If they win
or lose the game, that will be added to the message, along with what the secret word
was. Also, if they provide invalid data, they will get a message informing them of the 
issue, and will need to try again.<br><br>

In addition to a message, the `make_move` endpoint will also return game data such as the
partially revealed word with dashes for blanks, a string of missed letters, and how many
misses are left.

Gameplay continues with the user guessing a letter until either they guess the secret word,
or they reach the number of allowed misses.

Many different Hangman games can be played by many different users at any
given time. Each game can be retrieved or played by using the path parameter
`urlsafe_game_key`.

##Files Included:
 - `api.py`: Contains endpoints and game playing logic.
 - `app.yaml.config`: App configuration. Rename to `app.yaml` after changing `application` 
  to your unique app ID.
 - `index.yaml`: Autogenerated file with indexes.
 - `cron.yaml`: Cronjob configuration.
 - `main.py`: Handler for taskqueue handler.
 - `models.py`: Entity and message definitions including helper methods.
 - `utils.py`: Helper function for retrieving ndb.Models by urlsafe Key string.
 - `words.csv`: list of words that can be used as secret word in app.

##Endpoints Included:
 - **create_user**
    - Path: 'user'
    - Method: POST
    - Parameters: user_name, email (optional)
    - Returns: Message confirming creation of the User.
    - Description: Creates a new User. user_name provided must be unique. Will 
    raise a ConflictException if a User with that user_name already exists. It
    will also raise a BadRequestException if user_name is empty, less than 3
    characters, or is not alphanumeric.
    
 - **new_game**
    - Path: 'game'
    - Method: POST
    - Parameters: user_name, allowed_misses
    - Returns: GameForm with initial game state.
    - Description: Creates a new Game. user_name provided must correspond to an
    existing user - will raise a NotFoundException if not. A BadRequestException
    will be raised if allowed_misses is not between 6 and 10. The default is 6.
    Also adds a task to a task queue to update the average misses remaining for
    active games.
     
 - **get_game**
    - Path: 'game/{urlsafe_game_key}'
    - Method: GET
    - Parameters: urlsafe_game_key
    - Returns: GameForm with current game state.
    - Description: Returns the current state of a game using GameForm. If no game 
    was found, it returns a NotFoundException. If a Game was found, the message will
    indicate "Time to take a turn!" if it's an active game, or "The game is over!" 
    if the game is over.
    
 - **make_move**
    - Path: 'game/{urlsafe_game_key}'
    - Method: PUT
    - Parameters: urlsafe_game_key, guess
    - Returns: GameForm with new game state.
    - Description: Accepts a 'guess' and returns the updated state of the game.
    Exactly 1 alphabetic character must be entered or a BadRequestException will be
    raised. If the user enters a letter that was previously guessed, the message will
    say "The letter was already guessed. Try a different
    letter!"<br><br>
    If the guess is valid, the message will either indicate "Guessed letter is in 
    secret word!" or "Guessed letter not in secret word!" as appropriate. If guess is in
    the secret word, then the blanks (dashes) in guessed_word will be updated with the guessed
    letter. If guess isn't in the secret word, then missed_letters (a string of missed letters)
    will be updated to include the guess.<br><br>
    If the guess causes the game to end, the message will include that the game was lost or 
    won along with what the secret word was. Also, when the game ends, a corresponding Score
    entity will be created, and the User object will be updated with data for ranking users.
    
 - **get_high_scores**
    - Path: 'scores/high'
    - Method: GET
    - Parameters: number_of_results (optional)
    - Returns: ScoreForms.
    - Description: Returns a list of high scores with up to `number of results` results
    for games that were won.
    
 - **get_user_scores**
    - Path: 'scores/user/{user_name}'
    - Method: GET
    - Parameters: user_name
    - Returns: ScoreForms. 
    - Description: Returns all Scores recorded by the provided player (unordered).
    Will raise a NotFoundException if the User does not exist.
    
 - **get_average_misses**
    - Path: 'games/average_misses'
    - Method: GET
    - Parameters: None
    - Returns: StringMessage
    - Description: Gets and returns the average number of misses remaining for all games
    from a previously cached memcache key.

 - **get_user_games**
    - Path: 'games/active/user/{user_name}'
    - Method: GET
    - Parameters: user_name
    - Returns: UserGameForms
    - Description: Returns all of an individual user's active games. Will raise a 
    NotFoundException if the User does not exist.

 - **cancel_game**
    - Path: 'game/cancel/{urlsafe_game_key}'
    - Method: PUT
    - Parameters: urlsafe_game_key
    - Returns: StringMessage
    - Description: Cancels game by deleting it from the datastore and returns the message
    "Game has been cancelled!" if successful. Will raise a NotFoundException if the Game
    does not exist. If the Game is already over, it cannot be cancelled and it will return
    the message "Failed to cancel: Game already over!" 
 
 - **get_user_rankings**
    - Path: 'scores/user-rankings'
    - Method: GET
    - Parameters: number_of_results (optional)
    - Returns: UserRankingForms
    - Description: Returns a list of ranked users (who have completed at least one game)
    with up to `number_of_results` results. The user with the highest ranking will be 
    listed first, the user with the second highest ranking will be listed second, and
    so on.

 - **get_game_history**
    - Path: 'game/history/{urlsafe_game_key}'
    - Method: GET
    - Parameters: urlsafe_game_key
    - Returns: StringMessage
    - Description: Returns a list of Turn History for the game as the message, which for 
    each turn includes the guess, result, and the word guessed so far with blanks (dashes)
    for letters yet to be guessed. Will raise a NotFoundException if the Game does not exist
   or the Game is new and has no history yet.

##Models Included:
 - **User**
    - Stores unique user_name and (optional) email address as well as some stats to 
    determine user rankings.
    
 - **Game**
    - Stores unique game states. Associated with User model via KeyProperty.
    
 - **Score**
    - Records completed games. Associated with Users model via KeyProperty.

##Forms Included:
 - **GameForm**
    - Representation of a Game's state (urlsafe_key, misses_left, missed_letters, 
    guessed_word, game_over flag, message, user_name).
 - **UserGameForms**
    - Multiple GameForm container used to return multiple GameForms for a specific user.
 - **NewGameForm**
    - Used to create a new game (user_name, allowed_misses).
 - **MakeMoveForm**
    - Inbound make move form (guess).
 - **ScoreForm**
    - Representation of a completed game's Score (user_name, date, won flag,
    misses, difficulty).
 - **ScoreForms**
    - Multiple ScoreForm container.
 - **UserRankingForm**
    - Representation of a user who is being ranked against other users by their 
    completed game stats (user_name, win_ratio, wins, total_games, avg_won_difficulty, avg_misses).
 - **UserRankingForms**
    - Multiple UserRankingForm container.
 - **StringMessage**
    - General purpose String container.
