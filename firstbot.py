''' firstbot
    Adam Hodges

    firstbot.py
'''
import json
import urllib, urllib2
import cookielib
import time
import sqlite3
import os

'''
firstbot searches f7u12 for any submissions containing the word "first"
this is a list of inclusion terms and exclusion terms to further filter the comics
these can be tweaked in an attempt to eliminate false positives.
'''
inclusionterms=['[first]','(first)','first rage','first comic', 'first post']
exclusionterms=['[fixed]', '(fixed)', 'her first', 'his first', '\'s first', 'their first','after first', 'submitted my first', 'after submitting', 'comic rage', 'second']

#delay between general requests to reddit
CRAWLER_DELAY=4

#delay between comments. currently very high to avoid rate-limiting.
COMMENT_DELAY=600

#delay between new search requests
SEARCH_DELAY=480

class database:
    '''class designed to provide an interface to a sqlite3 database'''
    def __init__(self):
        '''create database and schema if it doesnt exist. open connection'''
        db_is_new = not os.path.exists('firstbot.db')
        self.conn = sqlite3.connect('firstbot.db')
        self.cursor=self.conn.cursor()
        if db_is_new:
            self.cursor.execute('create table submission (name text primary key not null, isfirst integer not null);')
        self.conn.commit() 

    def check(self,name):
        '''check to see if a rage comic has already been logged'''
        self.cursor.execute('select * from submission where name = \''+ name + '\'')
        if len(self.cursor.fetchall()) > 0:
            return True
        else:
            return False

    def insert(self, name, isfirst):
        '''mark a rage comic as logged, and record if it was legitimately a [first] submission'''
        self.cursor.execute('insert into submission values(\''+ name+'\', \''+str(isfirst)+'\')')
        self.conn.commit()

def login():
    '''login to reddit.com with the firstbot user'''
    url="http://www.reddit.com/api/login/firstbot"
    values={'user':'firstbot', 'passwd':'password', 'api_type':'json'}
    #use a custom urlopener to save the auth cookie after login
    cj=cookielib.CookieJar()
    urlOpener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))

    #prepare request and POST to api
    data=urllib.urlencode(values)
    req=urllib2.Request(url,data)
    response=urlOpener.open(req)

    #parse json response
    text=response.read()
    jsonobj=json.loads(text)

    #return custom urlopener and modhash. these are what you need for reddit authentication
    modhash=jsonobj['json']['data']['modhash']
    return([urlOpener, modhash])

def search(auth, db):
    '''search for f7u12 "first" submissions'''
    urlOpener=auth[0]
    modhash=auth[1]

    #form request and sleep
    url="http://www.reddit.com/r/fffffffuuuuuuuuuuuu/search.json?q=first&restrict_sr=on&sort=new"
    req=urllib2.Request(url)
    time.sleep(CRAWLER_DELAY)

    #parse response as json
    response=urlOpener.open(req)
    text=response.read()
    jsonobj=json.loads(text)

    #for every submission in search results
    for row in jsonobj['data']['children']:
        claimedfirst=False
        title=row['data']['title']
        #filter the title using inclusion and exclusion terms 
        for interm in inclusionterms:
            if interm in title.lower():
                claimedfirst=True
        for exterm in exclusionterms:
            if exterm in title.lower():
                claimedfirst=False

        if claimedfirst:
            author=row['data']['author']
            name=row['data']['name']
            created=row['data']['created']
            #check to see if we have already seen this comic
            if not db.check(name):
                print(title)
                #call ragecount to verify "first" status
                submissions=ragecount(auth, author, created)
                print(str(submissions) + " previous submissions")
                if submissions > 0:
                    #user is probably lying, leave them a comment about it
                    report(auth,name,submissions,db)
                else:
                    #user checks out. mark the comic as investigated
                    db.insert(name, True)

def ragecount(auth, author, created):
    '''count the number of rage comics submitted prior to the created parameter'''
    urlOpener=auth[0]
    modhash=auth[1]

    #form request and sleep
    url="http://www.reddit.com/user/"+author+"/submitted.json"
    req=urllib2.Request(url)
    time.sleep(CRAWLER_DELAY)

    #parse response as json
    response=urlOpener.open(req)
    text=response.read()
    jsonobj=json.loads(text)

    submissioncount=0

    #for every submission in the user's history
    for row in jsonobj['data']['children']:
        if 'title' in row['data'].keys():
            title=row['data']['title']
            #if the subreddit is f7u12 and the created date is before the one we're investigating
            if row['data']['subreddit'] == 'fffffffuuuuuuuuuuuu':
                if row['data']['created'] < created:
                    #add it to the submission count
                    submissioncount=submissioncount+1

    #handle multiple pages of results
    while jsonobj['data']['after'] is not None:
        #form request and sleep
        afterurl=url+"?after="+jsonobj['data']['after']
        req=urllib2.Request(afterurl)
        time.sleep(CRAWLER_DELAY)

        #parse response as json
        response=urlOpener.open(req)
        text=response.read()
        jsonobj=json.loads(text)

        #for every submission in the user's history
        for row in jsonobj['data']['children']:
            if 'title' in row['data'].keys():
                title=row['data']['title']
                #if the subreddit is f7u12 and the created date is before the one we're investigating
                if row['data']['subreddit'] == 'fffffffuuuuuuuuuuuu':
                    if row['data']['created'] < created:
                        #add it to the submission count
                        submissioncount=submissioncount+1

    #return the number of rage comics discovered
    return submissioncount
    
def report(auth, name, submissioncount, db):
    '''function that posts a comment on the offending submission'''
    urlOpener=auth[0]
    modhash=auth[1]
    
    #construct comment contents
    message="firstbot^beta - please take it easy on me!\n\n"
    message=message+"This user has submitted " + str(submissioncount) + " rage comics before this one.\n\n"
    message=message+"STOP RIGHT THERE, CRIMINAL SCUM!\n\n"
    message=message+"Unless I am mistaken, you are trying to use the [first] tag to get more karma. Shame on you. Shame. On. You.\n\n"
    message=message+"*This comment generated by an automated bot.*"

    #form request and sleep
    url="http://www.reddit.com/api/comment"
    values={'thing_id':name, 'text':message, 'uh':modhash}
    data=urllib.urlencode(values)
    req=urllib2.Request(url,data)
    time.sleep(COMMENT_DELAY)

    #POST to api and parse json response
    response=urlOpener.open(req)
    text=response.read()
    jsonobj=json.loads(text)

    #log as processed (and illegitimate) in db
    if submissioncount > 0:
        db.insert(name, False)


def main():
    #init database
    db=database()

    #login to reddit
    auth=login()

    #loop indefinitely
    while(True):
        search(auth, db)
        time.sleep(SEARCH_DELAY)
    
if __name__ == '__main__':
    main()
