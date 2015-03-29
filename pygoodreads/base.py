import os
import re
import functools
from config import get_config

from requests_oauthlib import OAuth1Session
from xmltodict import parse

from errors import NotFoundProfileException, ProfilePrivateException
def auth(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        self = args[0]
        if not self._connected():
            raise Exception("No authenticated session.")
        else:
            return func(*args, **kwargs)
    return wrapper


class GoodreadsSession(OAuth1Session):

    BASE_URL = "http://www.goodreads.com/"
    REQUEST_TOKEN_URL = BASE_URL + 'oauth/request_token'
    AUTHORIZATION_BASE_URL = BASE_URL + 'oauth/authorize'
    ACCESS_TOKEN_URL = BASE_URL + 'oauth/access_token'

    BOOK_REVIEW_PATTERN = r"""
    .../user/show/                    # Skip leading url
    ...(?P<userid>[0-9]+)-[\w-]*      # Get user_id followed by the username
    ...\\\"\stitle=\\\"[^\\]*\\\"\\u003e[^\\]*\\\u003c/a\\u003e   # Mix of quotes and usernames (username=[^\\]*)
    ...\\n\\n\s{8}rated\sit\\n\s{8}\\u003ca\s       # Static
    ...class=\\\"\sstaticStars\s      # Beginning of the class where the rating is
    ...stars_(?P<bookid>[12345])      # Retrieve the rating
    ...\\\"\sti                       # End of the class
    """
    BOOK_REVIEW_PATTERN_COMPILED = re.compile(BOOK_REVIEW_PATTERN, re.VERBOSE)

    def __init__(self, 
                 client_id=None,
                 client_secret=None,
                 access_token=None,
                 access_token_secret=None,
                 config_file=None):

        config_dict = {}
        if client_id is None and config_file:
            try:
                config_dict = get_config("goodreads")
            except Exception:
                pass
        self.developer_key = client_id or config_dict['client_id']
        OAuth1Session.__init__(self,
                               self.developer_key,
                               client_secret=client_secret or config_dict['client_secret'],
                               callback_uri='https://127.0.0.1/callback',
                               resource_owner_key=access_token or config_dict.get("access_token"),
                               resource_owner_secret=access_token_secret or config_dict.get("access_token_secret"))

    def _clean_oauth(self):
        """If tokens are deprecated"""
        self._client.client.resource_owner_secret = None
        self._client.client.resource_owner_key = None

    def _connected(self):
        return (self._client.client.resource_owner_secret and self._client.client.resource_owner_key)

    def connect(self):
        if self._connected():
            return
        else:
            self._clean_oauth()
            self._authenticate()

    def _authenticate(self):
        """Authenticate the user using the OAuth1 protocol"""
        self.fetch_request_token(self.REQUEST_TOKEN_URL)

        authorization_url = self.authorization_url(self.AUTHORIZATION_BASE_URL)
        print 'Please go here and authorize,'
        print authorization_url
        res = None
        while res != "y":
            res = raw_input("Have you authorized?(y/n)")
        self.fetch_access_token(self.ACCESS_TOKEN_URL, verifier=u"verifier")

    def get(self, *args, **kwargs):
        """Override the OAuth1Session GET method so that we can just call
        ...`friend/user/{}` instead of `http://www.goodreads.com/friend/user/{}`"""
        # get(url, *kwargs)
        url = args[0]
        if url.startswith("http"):
            return OAuth1Session.get(self, *args, **kwargs)
        else:
            return OAuth1Session.get(self, self.BASE_URL + url, *(args[1:]), **kwargs)

    def xml(self, *args, **kwargs):
        """Try parse the response of the GET request
        :rtype: dict"""
        res = self.get(*args, **kwargs)
        if res.status_code > 400:
            if "forbidden" in res.text:
                raise ProfilePrivateException()
            elif "error" in res.text:
                raise NotFoundProfileException()
            else:
                raise Exception(res.text)
        else:
            return parse(res.content, dict_constructor=dict)["GoodreadsResponse"]

    @auth
    def reviews(self, user_id, **kwargs):
        """Get the reviews of a user. Need OAuth authentication.
        
        :param user_id: the id of the user
        :type user_id: string or int
        :param shelf: read, currently-reading, to-read, etc. (optional)
        :param sort: title, author, cover, rating, year_pub, date_pub, date_pub_edition, date_started, date_read, date_updated, date_added, recommender, avg_rating, num_ratings, review, read_count, votes, random, comments, notes, isbn, isbn13, asin, num_pages, format, position, shelves, owned, date_purchased, purchase_location, condition (optional)
        :param search[query]: query text to match against member's books (optional)
        :param order: a, d (optional)
        :param page: 1-N (optional)
        :raises: :class: ProfilePrivateException, NotFoundProfileException, Exception
        """
        params = {"v": "2",
                  "id": str(user_id),
                  "per_page":"200"}
        # The kwargs parameters erase the default params   
        params.update(kwargs)
        data_dict = self.xml("review/list.xml", params=params)
        return data_dict['reviews']

    def _objects_all(self, api_call, field):
        # no do-while loop in python
        # Let s make a first query to get the number of reviews
        current_page = 0

        while True:
            current_page += 1
            response_dict = api_call(page=str(current_page))
            
            try:
                objects = response_dict[field]
            except KeyError:
                return

            # If only one obj is available, response_dict[field] is a dict
            if isinstance(objects, dict):
                yield objects
            else:
                for obj in objects:
                    yield obj

    @auth
    def reviews_all(self, user_id, shelf='read'):
        """Get all reviews written by a user from the shelf .
        """
        api_call = functools.partial(self.reviews, user_id, shelf=shelf)
        reviews_gen = self._objects_all(api_call, "review")
        for r in reviews_gen: yield r

    @auth
    def friends(self, user_id, **kwargs):
        params = {
            "format":"xml",
            "page":1,
            "key": self.developer_key
        }
        params.update(kwargs)
        response = self.xml('friend/user/{}'.format(user_id), params=params)
        return response['friends']

    @auth
    def friends_all(self, user_id, **kwargs):
        sort = kwargs.get("sort", " first_name")
        api_call = functools.partial(self.friends, user_id, sort=sort)
        friends_gen = self._objects_all(api_call, "user")
        for f in friends_gen: yield f

    def group_members(self, group_id, page=1, **kwargs):
        params = {"page":str(page)}
        params.update(kwargs)
        response = self.xml("group/members/{0}.xml".format(group_id),
                            params=params)
        try:
            return response['group_users']['group_user']
        except KeyError:  # No more user
            return []

    def group_members_all(self, group_id, min_page=1, max_page=10**9):
        current_page = min_page
        group_members = self.group_members(group_id, page=str(current_page), sort='num_books')
        while group_members and current_page<max_page:
            for member in group_members:
                yield member
            current_page += 1
            print "members, current page: ", current_page
            group_members = self.group_members(group_id, page=str(current_page))

    @auth
    def book_reviews(self, book_id, page=1):
        unstructured_resp = c.get("book/reviews/{0}".format(book_id), params={"page":page})
        return self.BOOK_REVIEW_PATTERN_COMPILED.findall(unstructured_resp)

    @auth
    def book_reviews_all(self, book_id):
        """100 hundred pages max for reviews from a book id"""
        for page in range(1, 101):
            reviews = self.book_reviews(book_id, page=page)
            if not reviews:
                break
            for user_id, rating in reviews:
                yield user_id, book_id, rating
 
