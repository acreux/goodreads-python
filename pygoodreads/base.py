from requests_oauthlib import OAuth1Session
from config import get_config
import os
import ConfigParser
from xmltodict import parse

import functools

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
        res = self.get("https://www.goodreads.com/user/41256554/followers.xml?key={}".format(self.developer_key))
        return (res.status_code == 200)

    def connect(self):
        if self._connected():
            return
        else:
            self._clean_oauth()
            self._authenticate()

    def _authenticate(self):
        self.fetch_request_token(self.REQUEST_TOKEN_URL)

        authorization_url = self.authorization_url(self.AUTHORIZATION_BASE_URL)
        print 'Please go here and authorize,'
        print authorization_url
        res = None
        while res != "y":
            res = raw_input("Have you authorized?(y/n)")
        print self.fetch_access_token(self.ACCESS_TOKEN_URL, verifier=u"verifier")
        print self._try_connect()

    def get(self, *args, **kwargs):
        url = args[0]
        if url.startswith("http"):
            return OAuth1Session.get(self, *args, **kwargs)
        else:
            return OAuth1Session.get(self, self.BASE_URL + url, *(args[1:]), **kwargs)

    def xml(self, *args, **kwargs):
        res = self.get(*args, **kwargs)
        if res.status_code > 400:
            raise Exception(res.text)
        else:
            return parse(res.content, dict_constructor=dict)['GoodreadsResponse']

    @auth
    def reviews(self, user_id, **kwargs):
        """Get the books on a members shelf.
        Parameters are:
        * shelf: read, currently-reading, to-read, etc. (optional)
        * sort: title, author, cover, rating, year_pub, date_pub, date_pub_edition, date_started, date_read, date_updated, date_added, recommender, avg_rating, num_ratings, review, read_count, votes, random, comments, notes, isbn, isbn13, asin, num_pages, format, position, shelves, owned, date_purchased, purchase_location, condition (optional)
        * search[query]: query text to match against member's books (optional)
        * order: a, d (optional)
        * page: 1-N (optional)

        Access can be forbidden
        """
        params_dict = {"v": "2",
                       "id": str(user_id),
                       "per_page":"200"}
        params_dict.update(kwargs)
        try:
            data_dict = self.xml("review/list.xml", params=params_dict)
        except Exception as e:
            print e, "for ", user_id
            return {}
        return data_dict['reviews']

    @auth
    def review_list_all(self, user_id):
        """Get all books on a members shelf.
        Return a generator of all books found on this member shelf
        """
        # Let s make a first query to get the number of reviews
        current_page = 1
        review_dict = self.reviews(user_id, shelf="all", page=str(current_page))
        if not review_dict:
            return

        total_reviews = review_dict['@total']
        current_end = review_dict['@end']
        # current_start = review_dict['@start']

        # Yield the review already queried
        try:
            # If only one review is available, review_dict['review'] is a dict
            if isinstance(review_dict['review'], dict):
                yield review_dict['review']
            else:
                for review in review_dict['review']:
                    yield review
        except KeyError:
            print 'no review for ', user_id
            return

        # safety measure: if we go too far, @end=0
        while not current_end in (total_reviews, 0):
            current_page += 1
            review_dict = self.reviews(user_id, page=str(current_page))
            if review_dict:  # We should have access anyway
                current_end = review_dict['@end']
                for review in review_dict['review']:
                    yield review

    @auth
    def friends(self, user_id, page=1, sort=None):
        params = {
            "format":"xml",
            "page":1,
            "key": self.client_id
        }
        self.get('friend/user/{}', )

    @auth
    def friends_id_all(self, user_id):
        for friend_id, friend_name in self.get_friends(user_id):
            yield friend_id

    def group_members(self, group_id, page=1):
        response = self.xml("group/members/{0}.xml".format(group_id),
                            params={"page":str(page)})
        try:
            return response['group_users']['group_user']
        except KeyError:  # No more user
            return []

    def all_group_members(self, group_id):
        # Let s make a first query to get the number of reviews
        current_page = 1
        group_members = self.group_members(group_id, page=str(current_page))
        while group_members:
            for member in group_members:
                yield member
            current_page += 1
            group_members = self.group_members(group_id, page=str(current_page))