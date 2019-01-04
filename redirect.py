"""Simple endpoint that redirects to the embedded fully qualified URL.

May also instead fetch and convert to AS2, depending on conneg.

Used to wrap ActivityPub ids with the fed.brid.gy domain so that Mastodon
accepts them. Background:

https://github.com/snarfed/bridgy-fed/issues/16#issuecomment-424799599
https://github.com/tootsuite/mastodon/pull/6219#issuecomment-429142747
"""
import logging
import json

from granary import as2, microformats2
import mf2py
import mf2util
import webapp2

import appengine_config
import common


class RedirectHandler(webapp2.RequestHandler):
    """301 redirects to the embedded fully qualified URL.

    e.g. redirects /r/https://foo.com/bar?baz to https://foo.com/bar?baz
    """

    def get(self):
        assert self.request.path_qs.startswith('/r/')
        to = self.request.path_qs[3:]
        if not to.startswith('http://') and not to.startswith('https://'):
            common.error(self, 'Expected fully qualified URL; got %s' % to)

        # poor man's conneg, only handle single Accept values, not multiple with
        # priorities.
        if self.request.headers.get('Accept') in (common.CONTENT_TYPE_AS2,
                                                  common.CONTENT_TYPE_AS2_LD):
            return self.convert_to_as2(to)

        # redirect
        logging.info('redirecting to %s', to)
        self.redirect(to)

    def convert_to_as2(self, url):
        """Fetch a URL as HTML, convert it to AS2, and return it.

        Currently mainly for Pixelfed.
        https://github.com/snarfed/bridgy-fed/issues/39
        """
        resp = common.requests_get(url)
        mf2 = mf2py.parse(resp.text, url=resp.url, img_with_alt=True)
        entry = mf2util.find_first_entry(mf2, ['h-entry'])
        logging.info('Parsed mf2 for %s: %s', resp.url, json.dumps(entry, indent=2))

        obj = common.postprocess_as2(as2.from_as1(microformats2.json_to_object(entry)))
        logging.info('Returning: %s', json.dumps(obj, indent=2))

        self.response.headers.update({
            'Content-Type': common.CONTENT_TYPE_AS2,
            'Access-Control-Allow-Origin': '*',
        })
        self.response.write(json.dumps(obj, indent=2))


app = webapp2.WSGIApplication([
    (r'/r/.+', RedirectHandler),
], debug=appengine_config.DEBUG)
