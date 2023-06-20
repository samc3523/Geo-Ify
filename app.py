csvpath = "/home/Samc22/geoify/static/cleancity.csv"  #defines the path for the csv for the city and music genre
geopath = "/home/Samc22/geoify/static/citygeos.pkl"   #defines the path for pickle file where coodinates are stored
from flask import Flask,request,url_for,session,redirect,render_template
import json
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
import pandas as pd
import plotly.graph_objects as go
import plotly
import pickle
import random
from flask_session import Session
from cred import CLIENT_ID,CLIENT_SECRET,SECRET_KEY
#helper functions
#helper fucntion - relates users genres to their corresponding cities
def urbanify(user_genres):
    user_cities = {}
    df  = pd.read_csv(csvpath,header=0)
    for genre in user_genres:
        for column in df:
            citygenres = df[column].tolist()
            for cgenre in citygenres:
                if genre == cgenre:
                    keylist = user_cities.keys()
                    if column not in keylist:
                        genrelist = [genre]
                        dictentry = {column:genrelist}
                        user_cities.update(dictentry)
                    else:
                        if genre not in user_cities[column]:
                            user_cities[column].append(genre)
    return user_cities
    #^ a dictionary of cities and their corresponding  genres

# takes in the dictionary genereated by urbanify and returns the geos for mapping - the city dictionary again and the list of cities
def getlatlong(citydict):
    with open(geopath, 'rb') as f:
        geodict = pickle.load(f)
    citylist = list(citydict.keys())
    citygeos = []
    for city in citylist:
        location = geodict[city]
        citygeos.append(location)
    return(citygeos,citydict,citylist)

#takes the geos from the geo function above and  the citydict and city list and plots them
def mapit(geos,citydict,citylist):
    lats = []
    longs = []
    names = []
    citygenres = []
    i = 0
    for item in citylist:
        citydict[item].insert(0,item)   #adds city name to begging of each list to show name on city in plotly tooltip
    for item in geos:
        names.append(item.address)
        lats.append(item.latitude)
        longs.append(item.longitude)
        city = citylist[i]
        citygenres.append(citydict[city])
        i = i + 1



    df = pd.DataFrame(list(zip(names,citygenres,lats,longs)),
               columns =['Address', 'Text', 'Latitude',"Longitude"])

    fig = go.Figure(data=go.Scattergeo(

        lon = df['Longitude'],
        lat = df['Latitude'],
        text = df['Text'],
        mode = 'markers',
        marker_color = 'red'

        ))

    fig.update_geos(
        resolution=50,
        showland=True, landcolor="black",
        showocean=True, oceancolor="pink",
        projection_type="equirectangular",
        visible=False,
        showcountries=True, countrycolor="black",
        )

    fig.update_layout(paper_bgcolor="rgba(0, 0, 0, 0)")

    fig.layout.xaxis.fixedrange = True
    fig.layout.yaxis.fixedrange = True
    return fig


#constants for spotify authentifiation and flask app

TOKEN_INFO ='token_info'
cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)

#spotify authentification helper function
def create_spotify_oauth():
    return SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri= 'https://www.geo-ify.com/redirectPage',
        cache_handler=cache_handler,
        show_dialog=True,
        scope="user-top-read"
        )

#flask app configuration

app = Flask(__name__)
app.secret_key = SECRET_KEY
SESSION_TYPE = 'filesystem'
SESSION_FILE_THRESHOLD = 1
SESSION_FILE_DIR = '/home/Samc22/geoify/Geo-ify-sessions'
SESSION_PERMANENT = False
app.config.from_object(__name__)
Session(app)
app.jinja_env.lstrip_blocks = True
app.jinja_env.trim_blocks = True

#begin flask app view functions

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/login")
def login():
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route("/redirectPage")
def redirectPage():
    sp_oauth = create_spotify_oauth()
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session[TOKEN_INFO] = token_info
    return redirect(url_for("geoify", _external = True))

def get_token():
    token_info = session.get(TOKEN_INFO, None)
    if not token_info:
        raise "exception"
    now = int(time.time())
    is_expired = token_info['expires_at'] - now < 60
    if (is_expired):
        sp_oauth = create_spotify_oauth()
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
    return token_info

@app.route("/geoify", methods=['GET', 'POST'])
def geoify():

    try:
        token_info = get_token()
    except:
        print("user not logged in")
        return redirect("/")
    sp = spotipy.Spotify(
        auth=token_info['access_token'],
    )

    current_user_name = sp.current_user()['display_name']

    session["user"] =  current_user_name
    results = sp.current_user_top_artists(
        limit =  50,
        offset = 0,
        time_range = 'long_term')
    artgendict = {}
    i = 0
    for item in results['items']:
        dictentry = {(results['items'][i]['name']):(results['items'][i]['genres'])}
        artgendict.update(dictentry)
        i = 1 + i

    artist_links = {}
    i = 0
    for item in results['items']:
        dictentry = {(results['items'][i]['name']):(results['items'][i]['external_urls']["spotify"])}
        artist_links.update(dictentry)
        i = 1 + i

    session['artist_links'] = artist_links

    session['artgendict'] =  artgendict
    glist = []
    for idx, item in enumerate(results['items']):
        genres = (item['genres'])
        for i in genres:
            glist.append(i)

    citydict = urbanify(glist)
    geos,citydict,citylist, = getlatlong(citydict)
    fig = mapit(geos,citydict,citylist)


    displaydict = citydict #makeing a "copy" of the citydict (same thing but it has the city which is list[0] removed for all the lists)  has for the display
    session['displaydict'] = displaydict


    for key in displaydict.keys():
        new_val_list = displaydict[key]
        del new_val_list[0]
        displaydict[key] = new_val_list

        #the above removes the citynames from the lists leaving just genres

    #the below transforms the plotly object into a json which can be read into the template
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    cityartistdict_total = {}
    for city,genres in displaydict.items():
        for genre in genres:
            for artist, artistgenres in artgendict.items():
                if genre in artistgenres:
                    if city in cityartistdict_total.keys():
                        if artist not in cityartistdict_total[city]:
                            cityartistdict_total[city].append(artist)
                        else:
                            pass
                    else:
                        listentry = [artist]
                        entry = {city:listentry}
                        cityartistdict_total.update(entry)

    session["cityartistdict_total"] = cityartistdict_total
    return render_template(
        'geoify.html',
        graphJSON=graphJSON,
        User = current_user_name,
        City_List = citylist,
        City_Genres = displaydict,
        cityartistdict = cityartistdict_total)

@app.route("/explore")
def explore():
    artist_links = session['artist_links']
    displaydict = session['displaydict']
    artgendict = session['artgendict']
    linkdict = {}
    for key in artgendict.keys():
        genrelist = artgendict[key]
        for genre in genrelist:
            if genre not in linkdict.keys():
                genre_for_link = genre.replace(" ","")
                link = f"https://everynoise.com/engenremap-{genre_for_link}.html"
                entry = {genre:link}
                linkdict.update(entry)

    return render_template(
        'explore.html',
        City_Genres = displaydict,
        artgendisplay = artgendict,
        linkdict = linkdict,
        artist_links = artist_links
        )
@app.route("/tourposter")
def tourposter():
    current_user_name = session['user']
    displaydict = session['displaydict']
    artgendict = session['artgendict']
    tour_list = []
    #d = date.today()


    for key in displaydict.keys():
        #displaydate = d.strftime("%b-%d")
        #entry = key + " " + displaydate
        tour_list.append(key)
        #d = d + timedelta(days = 7)

    cityartistdict_total = session["cityartistdict_total"]
    cityartistdict = {}
    if len(cityartistdict_total) <= 12:
        cityartistdict = cityartistdict_total
    else:
        for i in range(24):
            city, genrelist = random.choice(list(cityartistdict_total.items()))
            dictentry = {city:genrelist}
            cityartistdict.update(dictentry)


    return render_template("tourposter.html", cityartistdict = cityartistdict, tour_list = tour_list, name = current_user_name, artgendisplay = artgendict, citygenredict = displaydict)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect('/')

