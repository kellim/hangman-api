#!/usr/bin/env python

"""main.py - This file contains handlers that are called by taskqueue and/or
cronjobs."""
import logging

import webapp2
from google.appengine.api import mail, app_identity
from api import HangmanApi

from models import User, Game


class SendReminderEmail(webapp2.RequestHandler):
    def get(self):
        """Send a reminder email to each User with an at least one
         active game. Called every hour using a cron job"""
        app_id = app_identity.get_application_id()
        # users = User.query(User.email != None)
        games = Game.query(Game.game_over == False)
        users_emailed = []
        for game in games:
            user = User.query(User.key == game.user).get()
            if user.email and user.name not in users_emailed:
                subject = 'Reminder: Time to play Hangman!'
                body = 'Hello {}, you have at least one active game at' \
                       'hangman-game-api.appspot.com! Time to take a ' \
                       'turn!'.format(user.name)
                # This will send test emails, the arguments to send_mail are:
                # from, to, subject, body
                mail.send_mail('noreply@{}.appspotmail.com'.format(app_id),
                               user.email,
                               subject,
                               body)
                users_emailed.append(user.name)


class UpdateAverageMissesRemaining(webapp2.RequestHandler):
    def post(self):
        """Update game listing announcement in memcache."""
        HangmanApi._cache_average_misses()
        self.response.set_status(204)

app = webapp2.WSGIApplication([
    ('/crons/send_reminder', SendReminderEmail),
    ('/tasks/cache_average_misses', UpdateAverageMissesRemaining),
], debug=True)
