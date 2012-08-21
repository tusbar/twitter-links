#!/usr/bin/env python

import sys
import sqlite3
import string
import datetime

import socket
import httplib
import urllib
import urlparse

from ttp_loader import ttp

import config
import minifiers
import templates

path = sys.argv[1] if len(sys.argv) > 1 else './index.html'

months = 'jan,feb,mar,apr,may,jun,jul,aug,sep,oct,nov,dec'.split(',')
years = '2005,2006,2007,2008,2009,2010,2011,2012,2013,2014,2015'.split(',')

socket.setdefaulttimeout(10)
now = datetime.datetime.utcnow()
last_update = now.isoformat(':')

def format_delta(delta):
    def format_unit(quantity, unit):
        if quantity > 1:
            unit += 's'
        if quantity < 11:
            quantity = ('one', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten')[quantity]
        return '%s %s' % (str(quantity), unit)
    if delta.days < 1:
        if delta.seconds < 60:
            return format_unit(delta.seconds, 'second')
        if delta.seconds < 3600:
            return format_unit(delta.seconds / 60, 'minute')
        if delta.seconds < 24 * 3600:
            return format_unit(delta.seconds / 3600, 'hour')
    else:
        if delta.days < 7:
            return format_unit(delta.days, 'day')
        if delta.days < 6 * 7:
            return format_unit(delta.days / 7, 'week')
        if delta.days < 300:
            return format_unit(delta.days / 30, 'month')
        return format_unit(delta.days / 365, 'year')


def resolve_http_redirect(o, depth=0):
    if depth > 10:
        raise Exception("Redirected "+depth+" times, giving up.")
    conn = httplib.HTTPConnection(o.netloc)
    path = o.path
    if o.query:
        path +='?'+o.query
    conn.request("HEAD", path)
    res = conn.getresponse()
    headers = dict(res.getheaders())
    if headers.has_key('location') and headers['location'] != o.geturl():
        return resolve_http_redirect(urlparse.urlparse(headers['location']), depth+1)
    else:
        return o.geturl()


class Parser(ttp.Parser):
    def __init__(self, conn):
        ttp.Parser.__init__(self)
        self.tags = set([])
        self.conn = conn
        self.c = conn.cursor()

    def format_tag(self, tag, text):
        tag = text.lower()
        self.tags.add(tag)
        return templates.tweet_hash_tag_template.format(
            hash_tag = urllib.quote('#' + text.encode('utf-8')),
            display_hash_tag = ttp.escape(tag)
        )

    def format_url(self, url, text):
        o = urlparse.urlparse(url, allow_fragments=True)
        print o.hostname
        if config.link_resolve_mode == 'all' or config.link_resolve_mode == 'minified' and o.hostname in minifiers.urls:
            self.c.execute('select resolved from urls where minified = ?', (url,))
            urls = self.c.fetchall()
            if len(urls):
                url = urls[0][0]
            else:
                try:
                    resolved_url = resolve_http_redirect(o)
                    self.c.execute('insert or ignore into urls values (?, ?)', (url, resolved_url))
                    self.conn.commit()
                    url = resolved_url
                except:
                    pass

        return templates.tweet_url_template.format(
            url = ttp.escape(url),
            display_url = ttp.escape(url)
        )

    def format_username(self, at_char, user):
        return templates.tweet_user_template.format(
            username = ttp.escape(user),
            display_username = ttp.escape(user)
        )


conn = sqlite3.connect(config.db_file)
p = Parser(conn)

c = conn.cursor()
c.execute('create table if not exists urls (minified unique, resolved)')
c.execute('select user, text, tstamp, id from tweets where text like ?  order by tstamp desc', ('%http://%',))

out = ""

for row in c:
    tweet_user = row[0]
    tweet_text = row[1]
    tweet_id = row[3]

    tweet_time = datetime.datetime.strptime(row[2], '%Y-%m-%d %H:%M:%S')
    tweet_date = format_delta(now - tweet_time) + ' ago'

    tweet = p.parse(tweet_text)

    browse = templates.tweet_id_self_template.format(
        screen_name = config.screen_name,
        tweet_id = tweet_id
    )
    if tweet_user != config.screen_name:
        browse = templates.tweet_id_retweet_template.format(
            screen_name = config.screen_name,
            tweet_id = tweet_id,
            retweet_user = tweet_user
        )

    out += templates.tweet_template.format(
        tweet_link = browse,
        tweet_text = tweet.html,
        tweet_date = tweet_date,
        tweet_time = tweet_time
    )

html = templates.page_template.format(
    tweets = out,
    hash_tags = ','.join(p.tags),
    last_update = last_update
)

open(path, 'w').write(html.encode('utf-8'))
