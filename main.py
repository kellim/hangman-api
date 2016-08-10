#!/usr/bin/env python

"""main.py - This file contains handlers that are called by taskqueue and/or
cronjobs."""
import logging
import webapp2
from api import HangmanApi


class UpdateAverageMissesRemaining(webapp2.RequestHandler):
    def post(self):
        """Update game listing announcement in memcache."""
        HangmanApi._cache_average_misses()
        self.response.set_status(204)

app = webapp2.WSGIApplication([
    ('/tasks/cache_average_misses', UpdateAverageMissesRemaining),
], debug=True)
