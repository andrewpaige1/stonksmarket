from flask import Flask, render_template, url_for, request, session, redirect
from flask_pymongo import PyMongo
import bcrypt
from flask_cors import CORS
from flask_uploads import UploadSet, configure_uploads, IMAGES, patch_request_class
import datetime
from bson.json_util import dumps
import json
import random
import cloudinary as Cloud
from os import environ
import cloudinary.uploader

app = Flask('app')
app.config.from_pyfile('config.cfg')
mongo = PyMongo(app)
CORS(app)
patch_request_class(app, 32 * 1024 * 1024)

app.config['MEME_UPLOADS'] = 'static/img'
meme_folder = UploadSet('meme', IMAGES, default_dest=lambda app: app.config['MEME_UPLOADS'])
configure_uploads(app, meme_folder)
app.secret_key = environ.get('SECRET_KEY')

Cloud.config.update = ({
    'cloud_name':environ.get('CLOUDINARY_CLOUD_NAME'),
    'api_key': environ.get('CLOUDINARY_API_KEY'),
    'api_secret': environ.get('CLOUDINARY_API_SECRET')
})

@app.route('/')
def index():
    if 'username' in session:
        posts = mongo.db.posts
        all_docs = posts.find({})
        all_docs_string = dumps(all_docs)
        all_posts2 = json.loads(all_docs_string)
        urls = []
        """
        for post in all_posts2:
            img = cloudinary.CloudinaryImage(post['memeName'])
            url = img.build_url()
            urls.append(url)
        """
        users = mongo.db.users
        user = users.find_one({'name': session['username']})
        if user is None:
            return redirect(url_for('register'))

        def truncate(n):
            return int(n * 100) / 100
        rounded_monies = truncate(user['monies'])
        users_portfolio = mongo.db[session['username']+'Portfolio']
        all_posts = users_portfolio.find({})
        all_posts_string = dumps(all_posts)
        all_buys = json.loads(all_posts_string)
        return render_template('home.html', user=session['username'], post_data=all_posts2, monies=rounded_monies, portfolio=all_buys)
    return render_template('landing.html')

@app.route('/login')
def login_view():
    return render_template('login.html')


@app.route('/loginAuth', methods=['POST'])
def login():
    users = mongo.db.users
    login_user = users.find_one({'name': request.form['username']})

    if login_user:
        if bcrypt.hashpw(request.form['pass'].encode('utf-8'), login_user['password']) == login_user['password']:
            session['username'] = request.form['username']
            return redirect(url_for('index'))

    return redirect(url_for('index'))


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'POST':
        age = request.form['year']
        now = datetime.datetime.now()
        current_year = now.year
        if len(request.form['username']) < 3:
            return render_template('register.html', message="Your username must be 3 characters or more.")
        if len(request.form['pass']) < 5:
            return render_template('register.html', message="Your password must be at least 5 characters long")
        if age.isnumeric():
            age = int(age)
        else:
            return render_template('register.html', message="Please enter a valid year!")
        day = request.form['day']

        if day.isnumeric():
            day = int(day)
            if day > 31:
                return render_template('register.html', message="Please enter a valid day!")
        else:
            return render_template('register.html', message="Please enter a valid day!")

        if current_year - age >= 13:
            users = mongo.db.users
            existing_user = users.find_one({'name': request.form['username']})

            if existing_user is None:
                hashpass = bcrypt.hashpw(request.form['pass'].encode('utf-8'), bcrypt.gensalt())
                users.insert_one(
                    {'name': request.form['username'], 'password': hashpass, 'monies': 25000})
                session['username'] = request.form['username']
                return redirect(url_for('index'))
            return render_template('register.html', message="This name is already taken!")
        elif age > current_year:
            return render_template('register.html', message="please enter a valid year")
        else:
            return render_template('register.html', message="please do not use our site. you are underage")

    return render_template('register.html', message="")


@app.before_request
def make_session_permanent():
    session.permanent = True


@app.route('/privacypolicy', methods=['GET', 'POST'])
def privacy_policy():
    return render_template('privacypolicy.html')


@app.route('/terms', methods=['GET', 'POST'])
def terms():
    return render_template('terms.html')


@app.route('/create', methods=['GET', 'POST'])
def create():
    if 'username' in session:
        if request.method == 'POST' and 'photo' in request.files:
            photo = request.files['photo']
            if photo.filename == '':
                return render_template('create.html', message="please post a valid file")
            posts = mongo.db.posts
            price = request.form['price']
            try:
                price = float(price)
            except ValueError:
                return render_template('create.html', message="please enter a valid number")

            dot = photo.filename.index('.')
            photo_type = photo.filename[dot::]
            meme_name = request.form['memeName']
            existing_meme = posts.find_one({'memeName': meme_name+photo_type})
            random_name = str(random.randint(1000000000, 9999999999)) + str(random.randint(1000000000,
                                                                                           9999999999)) + "_user_uploads"  # Create a random name for the new picture
            if request.form['totalShares'].isnumeric():
                totalShares = int(request.form['totalShares'])
            else:
                return render_template('create.html', message="please enter a valid number of shares")
            if existing_meme is None:
                image_name = Cloud.uploader.upload(request.files['photo'])
               # meme_folder.save(request.files['photo'],
                #                 folder=session['username'], name=random_name + '.')
                posts.insert_one({'owner': session['username'], 
                'memeName': random_name + photo_type, 'price': price, 'url': image_name['secure_url'],
                                  'bought': 0, 'sold': 0, 'regName': meme_name, 'totalShares': totalShares})
                return redirect(url_for('index'))
            return render_template('create.html', message="meme name already exists!")
        return render_template('create.html', message="")
    else:
        return redirect(url_for('index'))


@app.route('/changePrice', methods=['GET', 'POST'])
def change_price():
    posts = mongo.db.posts
    all_posts = posts.find({})
    all_posts_string = dumps(all_posts)
    all_posts2 = json.loads(all_posts_string)
    current_user = session['username']+'Portfolio'
    users_portfolio = mongo.db[current_user]
    for post in all_posts2:
        buys = post['bought']
        sells = post['sold']
        if buys == 0 and sells == 0:
            continue
        elif buys == sells:
            continue
        sells = sells + 2
        total_trades = buys + sells
        buy_percent = buys / total_trades
        sell_percent = sells / total_trades

        if buy_percent > sell_percent:
            inc_percent = buy_percent - 0.5
            price_inc = inc_percent * post['price'] + post['price']

            def truncate(n):
                return int(n * 100) / 100
            final_change = truncate(price_inc)
            posts.update_one({'memeName': post['memeName']}, {'$set': {'price': final_change}})
            users_portfolio.update_one({'stonkInfo.stonkName': post['memeName']}, {
                                       '$set': {'stonkInfo.stonkPrice': final_change}})
        elif buy_percent < sell_percent:
            dec_percent = sell_percent - 0.5
            price_dec = post['price'] - dec_percent * post['price']

            def truncate(n):
                return int(n * 100) / 100
            final_change = truncate(price_dec)
            posts.update_one({'memeName': post['memeName']}, {'$set': {'price': final_change}})
            users_portfolio.update_one({'stonkInfo.stonkName': post['memeName']}, {
                                       '$set': {'stonkInfo.stonkPrice': final_change}})

    all_posts = posts.find({})
    all_posts_string = dumps(all_posts)
    all_posts2 = json.loads(all_posts_string)
    return {'allPosts': all_posts2}


@app.route('/buy/<meme_name>', methods=['GET', 'POST'])
def buy(meme_name):
    post = mongo.db.posts
    users = mongo.db.users
    user = users.find_one({'name': session['username']})
    post_to_update = post.find_one({'memeName': meme_name})

    def truncate(n):
        return int(n * 100) / 100
    dec = post_to_update['price'] * -1
    current_user = session['username']+'Portfolio'
    users_portfolio = mongo.db[current_user]
    if post_to_update['totalShares'] > 0 and user['monies'] > post_to_update['price']:
        post.update_one({'memeName': meme_name}, {'$inc': {'bought': 1, 'totalShares': -1}})
        users.update_one({'name': session['username']}, {'$inc': {'monies': dec}})
        existing_stonk = users_portfolio.find_one({'stonkInfo.stonkName': meme_name})
        if existing_stonk is None:
            users_portfolio.insert_one({'stonkInfo': {'stonkName': meme_name, 'amount': 1, 'stonkPrice': post_to_update['price'],
                                                      'regName': post_to_update['regName']}})
        elif existing_stonk != None:
            users_portfolio.update_one({'stonkInfo.stonkName': meme_name}, {
                                       '$inc': {'stonkInfo.amount': 1}})
    elif user['monies'] < post_to_update['price']:
        updated_post = post.find_one({'memeName': meme_name})
        post_update_string = dumps(updated_post)
        post_to_update2 = json.loads(post_update_string)
        return {'postToUpdate': post_to_update2, 'message': "you don't have enough monie to buy this!", 'monies': -1}
    updated_post = post.find_one({'memeName': meme_name})
    post_update_string = dumps(updated_post)
    post_to_update2 = json.loads(post_update_string)
    updated_user = users.find_one({'name': session['username']})
    rounded_monies = truncate(updated_user['monies'])
    return {'postToUpdate': post_to_update2, 'message': '', 'monies': rounded_monies}


@app.route('/profile')
def profile():
    if 'username' in session:
        posts = mongo.db.posts
        users_posts = posts.find({})
        users_posts_string = dumps(users_posts)
        users_posts2 = json.loads(users_posts_string)
        final_posts = []
        for post in users_posts2:
            if post['owner'] == session['username']:
                final_posts.append(post)
        users_portfolio = mongo.db[session['username']+'Portfolio']
        all_posts = users_portfolio.find({})
        all_posts_string = dumps(all_posts)
        all_buys = json.loads(all_posts_string)
        users = mongo.db.users
        user = users.find_one({'name': session['username']})

        def truncate(n):
            return int(n * 100) / 100
        rounded_monies = truncate(user['monies'])
        return render_template('profile.html', user=session['username'], portfolio=all_buys, monies=rounded_monies, usersPosts=final_posts)
    else:
        return redirect(url_for('index'))


@app.route('/sell/<meme_name>', methods=['POST'])
def sell(meme_name):
    posts = mongo.db.posts
    users = mongo.db.users
    amount = request.form['amount']
    if amount.isnumeric():
        amount = int(amount)
    else:
        return redirect(url_for('profile'))
    users_portfolio = mongo.db[session['username']+'Portfolio']
   # users.update_one({'name': session['username']}, {'$inc': {'monies': dec} })
    stonk = users_portfolio.find_one({'stonkInfo.stonkName': meme_name})
    stonk_info = stonk['stonkInfo']
    if stonk_info['amount'] < amount:
        return redirect(url_for('profile'))

    increase_monies = stonk_info['stonkPrice'] * amount
    users.update_one({'name': session['username']}, {'$inc': {'monies': increase_monies}})
    if stonk_info['amount'] - amount < 1:
        users_portfolio.delete_one({'stonkInfo.stonkName': meme_name})
    else:
        inc_amount = stonk_info['amount'] - amount
        inc_amount = inc_amount * -1
        users_portfolio.update_one({'stonkInfo.stonkName': meme_name}, {
                                   '$inc': {'stonkInfo.amount': inc_amount}})
    posts.update_one({'memeName': meme_name}, {'$inc': {'sold': amount}})
    posts.update_one({'memeName': meme_name}, {'$inc': {'totalShares': amount}})

    return redirect(url_for('profile'))


@app.route('/indexSell/<meme_name>', methods=['POST'])
def index_sell(meme_name):
    posts = mongo.db.posts
    users = mongo.db.users
    amount = request.form['amount']
    if amount.isnumeric():
        amount = int(amount)
    else:
        return redirect(url_for('index'))
    users_portfolio = mongo.db[session['username']+'Portfolio']
   # users.update_one({'name': session['username']}, {'$inc': {'monies': dec} })
    stonk = users_portfolio.find_one({'stonkInfo.stonkName': meme_name})
    stonk_info = stonk['stonkInfo']
    if stonk_info['amount'] < amount:
        return redirect(url_for('index'))
    increase_monies = stonk_info['stonkPrice'] * amount
    users.update_one({'name': session['username']}, {'$inc': {'monies': increase_monies}})
    if stonk_info['amount'] - amount < 1:
        users_portfolio.delete_one({'stonkInfo.stonkName': meme_name})
    else:
        inc_amount = stonk_info['amount'] - amount
        inc_amount = inc_amount * -1
        users_portfolio.update_one({'stonkInfo.stonkName': meme_name}, {
                                   '$inc': {'stonkInfo.amount': inc_amount}})
    posts.update_one({'memeName': meme_name}, {'$inc': {'sold': amount}})
    posts.update_one({'memeName': meme_name}, {'$inc': {'totalShares': amount}})

    return redirect(url_for('index'))


@app.route('/search', methods=['POST'])
def search():
    search_request = request.form['search']
    posts = mongo.db.posts
    all_docs = posts.find({})
    all_docs_string = dumps(all_docs)
    all_docs2 = json.loads(all_docs_string)
    search_res = []
    try:
        search_num = float(search_request)
        for post in all_docs2:
            if search_num >= post['price']:
                search_res.append(post)
    except ValueError:
        for post in all_docs2:
            if search_request.lower() in post['regName'].lower():
                search_res.append(post)

    # dumb tes

    return render_template("search.html", search_res=search_res, user=session['username'])


if __name__ == '__main__':
    app.run()
    # use app.run(debug=True) when developing
