from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, timezone
import os
import requests
import traceback
import json
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from pathlib import Path

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("FLASK_SECRET_KEY")

# Configure upload folders
basedir = Path(__file__).parent
UPLOAD_FOLDER = basedir / 'static' / 'uploads'
RESUME_FOLDER = UPLOAD_FOLDER / 'resumes'
ACHIEVEMENT_FOLDER = UPLOAD_FOLDER / 'achievements'
app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)

# Create folders if they don't exist
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
RESUME_FOLDER.mkdir(exist_ok=True)
ACHIEVEMENT_FOLDER.mkdir(exist_ok=True)

# Initialize MongoDB
mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client.alumni_portal

# Collections
users_collection = db.users
jobs_collection = db.jobs
events_collection = db.events
forum_posts_collection = db.forum_posts
subscriptions_collection = db.subscriptions
achievements_collection = db.achievements
donations_collection = db.donations

# Initialize extensions
login_manager = LoginManager(app)
login_manager.login_view = 'login'
CORS(app)

# OpenRouter API configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "mistralai/mistral-7b-instruct"

# Allowed file extensions
ALLOWED_EXTENSIONS = {'docx', 'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.name = user_data['name']
        self.email = user_data['email']
        self.password = user_data['password']
        self.role = user_data.get('role', 'alumni')
        self.profile_pic = user_data.get('profile_pic')
        self.grad_year = user_data.get('grad_year')
        self.branch = user_data.get('branch')
        self.company = user_data.get('company')
        self.position = user_data.get('position')
        self.linkedin = user_data.get('linkedin')
        self.github = user_data.get('github')
        self.created_at = user_data.get('created_at', datetime.utcnow())

    def get_id(self):
        return str(self.id)

    @property
    def jobs(self):
        return list(jobs_collection.find({'posted_by': ObjectId(self.id)}))

    @property
    def events(self):
        return list(events_collection.find({'created_by': ObjectId(self.id)}))

    @property
    def forum_posts(self):
        return list(forum_posts_collection.find({'user_id': ObjectId(self.id)}))

    @property
    def donations(self):
        return list(donations_collection.find({'user_id': ObjectId(self.id)}))

    @property
    def achievements(self):
        return list(achievements_collection.find({'user_id': ObjectId(self.id)}))

    @staticmethod
    def get(user_id):
        user_data = users_collection.find_one({'_id': ObjectId(user_id)})
        if not user_data:
            return None
        return User(user_data)
    
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('portal'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user_data = users_collection.find_one({'email': email})
        
        if user_data and check_password_hash(user_data['password'], password):
            user = User(user_data)
            login_user(user, remember=True)
            next_page = request.args.get('next')
            flash('Logged in successfully!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('portal'))
        else:
            flash('Login unsuccessful. Please check email and password', 'danger')

    return render_template('login.html', title='Login')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('portal'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not all([name, email, password, confirm_password]):
            flash('All fields are required', 'danger')
            return redirect(url_for('register'))
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))
        if users_collection.find_one({'email': email}):
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))

        try:
            hashed_password = generate_password_hash(password)
            user_data = {
                'name': name,
                'email': email,
                'password': hashed_password,
                'role': 'alumni',
                'created_at': datetime.now(timezone.utc)

            }
            users_collection.insert_one(user_data)
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash('Registration failed. Please try again.', 'danger')

    return render_template('register.html')

@app.route('/post_job', methods=['POST'])
@login_required
def post_job():
    if request.method == 'POST':
        title = request.form.get('title')
        company = request.form.get('company')
        description = request.form.get('description')
        
        if not all([title, company, description]):
            flash('All fields are required', 'danger')
            return redirect(url_for('portal'))
            
        try:
            job_data = {
                'title': title,
                'company': company,
                'description': description,
                'posted_by': ObjectId(current_user.id),
                'created_at': datetime.utcnow()
            }
            jobs_collection.insert_one(job_data)
            flash('Job posted successfully!', 'success')
        except Exception as e:
            flash('Failed to post job. Please try again.', 'danger')
            
    return redirect(url_for('portal'))

@app.route('/events')
def events():
    events = list(events_collection.find().sort('date', 1))
    return render_template('events.html', events=events)

@app.route('/create_event', methods=['POST'])
@login_required
def create_event():
    if request.method == 'POST':
        name = request.form.get('name')
        date_str = request.form.get('date')
        location = request.form.get('location')
        description = request.form.get('description')
        
        if not all([name, date_str, description]):
            flash('Name, date and description are required', 'danger')
            return redirect(url_for('portal'))
            
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
            event_data = {
                'name': name,
                'date': date,
                'location': location,
                'description': description,
                'created_by': ObjectId(current_user.id),
                'created_at': datetime.utcnow()
            }
            events_collection.insert_one(event_data)
            flash('Event created successfully!', 'success')
        except ValueError:
            flash('Invalid date format', 'danger')
        except Exception as e:
            flash('Failed to create event. Please try again.', 'danger')
            
    return redirect(url_for('portal'))

@app.route('/create_post', methods=['POST'])
@login_required
def create_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        
        if not all([title, content]):
            flash('Title and content are required', 'danger')
            return redirect(url_for('portal'))
            
        try:
            post_data = {
                'title': title,
                'content': content,
                'user_id': ObjectId(current_user.id),
                'created_at': datetime.utcnow()
            }
            forum_posts_collection.insert_one(post_data)
            flash('Post created successfully!', 'success')
        except Exception as e:
            flash('Failed to create post. Please try again.', 'danger')
            
    return redirect(url_for('portal'))

@app.route('/subscribe', methods=['POST'])
def subscribe():
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            flash('Email is required', 'danger')
            return redirect(url_for('portal'))
            
        try:
            if subscriptions_collection.find_one({'email': email}):
                flash('This email is already subscribed', 'info')
                return redirect(url_for('portal'))
                
            subscription_data = {
                'email': email,
                'subscribed_at': datetime.utcnow(),
                'is_active': True
            }
            subscriptions_collection.insert_one(subscription_data)
            flash('Thanks for subscribing!', 'success')
        except Exception as e:
            flash('Subscription failed. Please try again.', 'danger')
            
    return redirect(url_for('portal'))

@app.route('/achievements', methods=['GET', 'POST'])
@login_required
def achievements():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        image = request.files.get('image')
        
        if not title or not description:
            flash('Title and description are required', 'danger')
            return redirect(url_for('achievements'))
            
        try:
            image_path = None
            if image and allowed_file(image.filename):
                filename = secure_filename(f"{current_user.id}_{image.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'achievements', filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                image.save(filepath)
                image_path = f"achievements/{filename}"
            
            achievement_data = {
                'user_id': ObjectId(current_user.id),
                'title': title,
                'description': description,
                'image_path': image_path,
                'created_at': datetime.utcnow()
            }
            achievements_collection.insert_one(achievement_data)
            flash('Achievement posted successfully!', 'success')
        except Exception as e:
            flash('Failed to post achievement. Please try again.', 'danger')
    
    achievements = list(achievements_collection.find().sort('created_at', -1))
    return render_template('index.html', achievements=achievements)

@app.route('/facilities')
def facilities():
    return render_template('facilities.html')

@app.route('/donate', methods=['POST'])
@login_required
def donate():
    if request.method == 'POST':
        name = request.form.get('name')
        amount = request.form.get('amount')
        
        if not all([name, amount]):
            flash('Name and amount are required', 'danger')
            return redirect(url_for('portal'))
            
        try:
            donation_data = {
                'donor_name': name,
                'amount': float(amount),
                'user_id': ObjectId(current_user.id),
                'donated_at': datetime.utcnow(),
                'is_anonymous': False
            }
            donations_collection.insert_one(donation_data)
            flash('Thank you for your donation!', 'success')
        except ValueError:
            flash('Invalid amount format', 'danger')
        except Exception as e:
            flash('Donation failed. Please try again.', 'danger')
            
    return redirect(url_for('portal'))

@app.route('/resume', methods=['POST'])
@login_required
def resume():
    if request.method == 'POST':
        if 'resume' not in request.files:
            flash('No file uploaded', 'danger')
            return redirect(url_for('portal'))
            
        file = request.files['resume']
        
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(url_for('portal'))
            
        if not allowed_file(file.filename):
            flash('Only .docx files are allowed', 'danger')
            return redirect(url_for('portal'))
            
        try:
            filename = secure_filename(f"{current_user.id}_{file.filename}")
            filepath = os.path.join(RESUME_FOLDER, filename)
            os.makedirs(RESUME_FOLDER, exist_ok=True)
            file.save(filepath)
            
            result = parse_resume(filepath)
            
            if result.get('status') == 'error':
                flash(f"Error processing resume: {result.get('message', 'Unknown error')}", 'danger')
                return redirect(url_for('portal'))
            
            from urllib.parse import quote
            encoded_results = quote(json.dumps(result))
            
            flash('Resume analyzed successfully!', 'success')
            return redirect(url_for('portal', resume_results=encoded_results))
            
        except Exception as e:
            flash(f'Error processing resume: {str(e)}', 'danger')
            print(f"Resume processing error: {traceback.format_exc()}")
            
    return redirect(url_for('portal'))

@app.route('/portal')
@login_required
def portal():
    resume_results = None
    encoded_results = request.args.get('resume_results')
    
    if encoded_results:
        try:
            from urllib.parse import unquote
            decoded_results = unquote(encoded_results)
            resume_results = json.loads(decoded_results)
        except json.JSONDecodeError as e:
            print(f"Error decoding resume results: {e}")
            flash('Error loading resume analysis', 'danger')
        except Exception as e:
            print(f"Unexpected error: {e}")
            flash('Error processing resume results', 'danger')
        
    # Get recent jobs, events, and posts (not just user's)
    jobs = list(jobs_collection.find().sort('created_at', -1).limit(5))
    events = list(events_collection.find().sort('date', 1).limit(5))
    posts = list(forum_posts_collection.find().sort('created_at', -1).limit(5))
    achievements = list(achievements_collection.find().sort('created_at', -1))
    
    # Add user information to each item
    for job in jobs:
        job['posted_by'] = str(job['posted_by'])
        user = users_collection.find_one({'_id': ObjectId(job['posted_by'])})
        job['user'] = {'name': user['name']} if user else {'name': 'Unknown'}
    
    for event in events:
        event['created_by'] = str(event['created_by'])
        user = users_collection.find_one({'_id': ObjectId(event['created_by'])})
        event['user'] = {'name': user['name']} if user else {'name': 'Unknown'}
    
    for post in posts:
        post['user_id'] = str(post['user_id'])
        user = users_collection.find_one({'_id': ObjectId(post['user_id'])})
        post['user'] = {'name': user['name']} if user else {'name': 'Unknown'}
    
    for achievement in achievements:
        achievement['user_id'] = str(achievement['user_id'])
        user = users_collection.find_one({'_id': ObjectId(achievement['user_id'])})
        achievement['user'] = user if user else {'name': 'Unknown', 'profile_pic': None}
    
    return render_template('index.html', 
                         jobs=jobs, 
                         events=events, 
                         posts=posts,
                         achievements=achievements)

@app.route('/chatbot', methods=['POST'])
@login_required
def chatbot():
    try:
        data = request.get_json()
        message = data.get('message', '').strip()

        if not message:
            return jsonify({'response': "Message is required", 'status': 'error'}), 400

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": request.host_url,
            "X-Title": "Alumni Portal Chatbot",
            "Content-Type": "application/json"
        }
        payload = {
           "model": MODEL_NAME,
           "messages": [
               {
                    "role": "system",
                    "content": """You are AlumniBot, a helpful and accurate assistant for **SRI SIVANI College of Engineering**, located in **Chilakapalem, Srikakulam District, Andhra Pradesh, India**. The official website is https://srisivani.com/

        You ONLY represent this specific college. Do not mention or confuse with any other colleges like Sivananda or colleges in Rajahmundry, Bhimavaram, Tirupati, etc.

        You assist with:
         - Job board postings for alumni
         - Event announcements and registrations
         - Resume tips and analysis
         - Mentorship and alumni connections
         - Donations to the institution

         If someone asks: "Where is the college?", always say:
         "SRI SIVANI College of Engineering is located in Chilakapalem, Srikakulam District, Andhra Pradesh 532402, India."

         Be short, friendly, and accurate. Only use real facts related to this college.
         """
                },
                {
                      "role": "user",
                      "content": message
                }
            ]
        }

        response = requests.post(
            OPENROUTER_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            return jsonify({
                'response': f"Error: {response.status_code} - {response.text}",
                'status': 'error'
            }), 500

        result = response.json()
        reply = result['choices'][0]['message']['content']

        return jsonify({
            'response': reply,
            'status': 'success'
        })

    except Exception as e:
        print("Chatbot Error:", traceback.format_exc())
        return jsonify({
            'response': f"Server Error: {str(e)}",
            'status': 'error'
        }), 500

@app.route('/test_api')
def test_api():
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.get("https://openrouter.ai/api/v1/auth/key", headers=headers)
    return jsonify(response.json())

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    if request.method == 'POST':
        try:
            update_data = {
                'name': request.form.get('name'),
                'profile_pic': request.form.get('profile_pic'),
                'branch': request.form.get('branch')
            }
            
            grad_year = request.form.get('grad_year')
            if grad_year:
                update_data['grad_year'] = int(grad_year)
            
            users_collection.update_one(
                {'_id': ObjectId(current_user.id)},
                {'$set': update_data}
            )
            flash('Profile updated successfully!', 'success')
        except ValueError:
            flash('Graduation year must be a number', 'danger')
        except Exception as e:
            flash('Failed to update profile. Please try again.', 'danger')
    
    return redirect(url_for('portal') + '#profile')

@app.route('/update_professional', methods=['POST'])
@login_required
def update_professional():
    if request.method == 'POST':
        try:
            update_data = {
                'company': request.form.get('company'),
                'position': request.form.get('position'),
                'linkedin': request.form.get('linkedin'),
                'github': request.form.get('github')
            }
            
            users_collection.update_one(
                {'_id': ObjectId(current_user.id)},
                {'$set': update_data}
            )
            flash('Professional details updated successfully!', 'success')
        except Exception as e:
            flash('Failed to update professional details. Please try again.', 'danger')
    
    return redirect(url_for('portal') + '#settings')

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        user_data = users_collection.find_one({'_id': ObjectId(current_user.id)})
        
        if not check_password_hash(user_data['password'], current_password):
            flash('Current password is incorrect', 'danger')
        elif new_password != confirm_password:
            flash('New passwords do not match', 'danger')
        else:
            try:
                users_collection.update_one(
                    {'_id': ObjectId(current_user.id)},
                    {'$set': {'password': generate_password_hash(new_password)}}
                )
                flash('Password changed successfully!', 'success')
            except Exception as e:
                flash('Failed to change password. Please try again.', 'danger')
    
    return redirect(url_for('portal') + '#settings')

if __name__ == '__main__':
    app.run(debug=True)