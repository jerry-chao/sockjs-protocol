import unittest
import os
import re
import random
import time
import json
from utils import GET, GET_async, POST, POST_async, OPTIONS, old_POST_async
from utils import WebSocket8Client
from utils import RawHttpConnection
import uuid


# Base URL
# ========

"""
The SockJS server provides one or more SockJS services. The services
are usually exposed with a simple url prefix, like:
`http://localhost:8000/echo` or
`http://localhost:8000/broadcast`. We'll call this kind of url a
`base_url`. There is nothing wrong with base url being more complex,
like `http://localhost:8000/a/b/c/d/echo`. Base url should
never end with a slash.

Base url is the url that needs to be supplied to the SockJS client.

All paths under base url are controlled by SockJS server and are
defined by SockJS protocol.

SockJS protocol can be using either http or https.

To run this tests server pointed by `base_url` needs to support
following services:

 - `echo` - responds with identical data as received
 - `disabled_websocket_echo` - identical to `echo`, but with websockets disabled
 - `cookie_needed_echo` - identical to `echo`, but with JSESSIONID cookies sent
 - `close` - server immediately closes the session

This tests should not be run more often than once in five seconds -
many tests operate on the same (named) sessions and they need to have
enough time to timeout.
"""
test_top_url = os.environ.get('SOCKJS_URL', 'http://localhost:8081')
base_url = test_top_url + '/echo'
close_base_url = test_top_url + '/close'
wsoff_base_url = test_top_url + '/disabled_websocket_echo'
cookie_base_url = test_top_url + '/cookie_needed_echo'


# Static URLs
# ===========

class Test(unittest.TestCase):
    # We are going to test several `404/not found` pages. We don't
    # define a body or a content type.
    def verify404(self, r):
        self.assertEqual(r.status, 404)

    # In some cases `405/method not allowed` is more appropriate.
    def verify405(self, r):
        self.assertEqual(r.status, 405)
        self.assertFalse(r['content-type'])
        self.assertTrue(r['allow'])
        self.assertFalse(r.body)

    # Compare the 'content-type' header ignoring spaces
    def verify_content_type(self, r, content_type):
        self.assertEqual(r['content-type'].replace(' ', ''), content_type)

    # Multiple transport protocols need to support OPTIONS method. All
    # responses to OPTIONS requests must be cacheable and contain
    # appropriate headers.
    def verify_options(self, url, allowed_methods):
        for origin in ['test', 'null']:
            h = {'Access-Control-Request-Method': allowed_methods, 'Origin': origin}
            r = OPTIONS(url, headers=h)
            # A 200 'OK' or a 204 'No Content' should both be acceptable as responses for a CORS request.
            self.assertTrue(r.status == 204 or r.status == 200)
            self.assertTrue(re.search('public', r['Cache-Control']))
            self.assertTrue(re.search('max-age=[1-9][0-9]{6}', r['Cache-Control']),
                            "max-age must be large, one year (31536000) is best")
            self.assertTrue(r['Expires'])
            self.assertTrue(int(r['access-control-max-age']) > 1000000)
            # A server may respond to a preflight request with HTTP methods in addition to method specified in the 'Access-Control-Request-Method' header
            for header in allowed_methods.split(','):
                self.assertTrue(header.strip() in r['Access-Control-Allow-Methods'], 'Access-Control-Allow-Methods did not contain :' + header)
            self.assertFalse(r.body)
            self.verify_cors(r, origin)

    def verify_no_cookie(self, r):
        self.assertFalse(r['Set-Cookie'])

    # Most of the XHR/Ajax based transports do work CORS if proper
    # headers are set.
    def verify_cors(self, r, origin=None):
        if origin:
            self.assertEqual(r['access-control-allow-origin'], origin)
            # In order to get cookies (`JSESSIONID` mostly) flying, we
            # need to set `allow-credentials` header to true.
            self.assertEqual(r['access-control-allow-credentials'], 'true')
        else:
            self.assertEqual(r['access-control-allow-origin'], '*')
            self.assertFalse(r['access-control-allow-credentials'])

    # Sometimes, due to transports limitations we need to request
    # private data using GET method. In such case it's very important
    # to disallow any caching.
    def verify_not_cached(self, r, origin=None):
        self.assertEqual(r['Cache-Control'],
                         'no-store, no-cache, no-transform, must-revalidate, max-age=0')
        self.assertFalse(r['Expires'])
        self.assertFalse(r['Last-Modified'])


# Greeting url: `/`
# ----------------
class BaseUrlGreeting(unittest.TestCase):
    # The most important part of the url scheme, is without doubt, the
    # top url. Make sure the greeting is valid.
    def test_greeting(self):
        for url in [base_url, base_url + '/']:
            r = GET(url)
            self.assertEqual(r.status, 200)
            self.verify_content_type(r, 'text/plain;charset=UTF-8')
            self.assertEqual(r.body, 'Welcome to SockJS!\n')
            self.verify_no_cookie(r)

    # Other simple requests should return 404.
    def test_notFound(self):
        for suffix in ['/a', '/a.html', '//', '///', '/a/a', '/a/a/', '/a',
                       '/a/']:
            self.verify404(GET(base_url + suffix))

if __name__ == '__main__':
    unittest.main()