import  uuid
import time
from datetime import datetime
import json
import os
import re
import numpy as np
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, abort, Response, stream_with_context
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func
from sqlalchemy.orm import relationship
from g4f.client import Client
import markdown
from PIL import Image
import imageio.v3 as iio
import numpy as np
import os
import random

app = Flask(__name__)


# Custom template filters
@app.template_filter('from_json')
def from_json(value):
    try:
        return json.loads(value)
    except:
        return []

@app.template_filter('format_datetime')
def format_datetime(value):
    """Format a datetime object to a readable string"""
    now = datetime.now()
    diff = now - value
    
    if diff.days == 0:
        if diff.seconds < 30:  # أقل من 30 ثانية
            return "الآن"
        elif diff.seconds < 60:  # أقل من دقيقة
            return f"منذ {diff.seconds} ثانية"
        elif diff.seconds < 3600:  # أقل من ساعة
            minutes = diff.seconds // 60
            if minutes == 1:
                return "منذ دقيقة واحدة"
            elif minutes == 2:
                return "منذ دقيقتين"
            elif minutes <= 10:
                return f"منذ {minutes} دقائق"
            else:
                return f"منذ {minutes} دقيقة"
        else:  # أقل من يوم
            hours = diff.seconds // 3600
            if hours == 1:
                return "منذ ساعة واحدة"
            elif hours == 2:
                return "منذ ساعتين"
            elif hours <= 10:
                return f"منذ {hours} ساعات"
            else:
                return f"منذ {hours} ساعة"
    elif diff.days == 1:
        return "منذ يوم واحد"
    elif diff.days == 2:
        return "منذ يومين"
    elif diff.days <= 10:
        return f"منذ {diff.days} أيام"
    elif diff.days < 30:
        return f"منذ {diff.days} يوماً"
    else:
        # تنسيق 12 ساعة مع صباحاً/مساءً
        return value.strftime("%I:%M %p").replace("AM", "صباحاً").replace("PM", "مساءً") + " " + value.strftime("%Y-%m-%d")

app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db?check_same_thread=False'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER2'] = 'static/videos/video'
app.config['THUMBNAIL_FOLDER'] = 'static/videos/thumbnails'
from sqlalchemy.pool import NullPool

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'poolclass': NullPool}
from sqlalchemy.orm import scoped_session, sessionmaker

# إنشاء جلسة ديناميكية


db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    profession = db.Column(db.String(120), nullable=False)
    skills = db.Column(db.String(500), nullable=False)
    security_question = db.Column(db.String(200), nullable=False)
    security_answer = db.Column(db.String(200), nullable=False)
    profile_photo = db.Column(db.String(200), nullable=True, default='uploads/default-avatar.jpg')


# إضافة نموذج Post
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)  # Parent comment ID for nested replies
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship for nested replies
    replies = relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=True)  # عنوان اختياري
    content = db.Column(db.Text, nullable=True)  # محتوى النص
    image_url = db.Column(db.String(120), nullable=True)  # رابط الصورة
    video_url = db.Column(db.String(120), nullable=True)  # رابط الفيديو
    background_color = db.Column(db.String(20), nullable=True)  # لون خلفية النص
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_email = db.Column(db.String(120), nullable=False)  # إيميل المستخدم
    user_profession = db.Column(db.String(120), nullable=False)  # تخصص المستخدم
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    
    def __repr__(self):
        return f'<Post {self.title}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# نموذج الرسالة
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text)  # نص الرسالة (اختياري)
    file_url = db.Column(db.String(255))  # رابط الملف (صورة/فيديو)
    file_type = db.Column(db.String(50))  # نوع الملف: 'image', 'video', 'audio', إلخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    watched_by_receiver = db.Column(db.Boolean, default=False)
    watched_by_sender = db.Column(db.Boolean, default=False)
    last_updated = db.Column(db.DateTime, onupdate=datetime.utcnow)



# تعريف نموذج قاعدة البيانات
class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    user = db.Column(db.String(100), nullable=False)
    id_user = db.Column(db.String(100), nullable=False)
    photo_user = db.Column(db.String(100), nullable=False)
    profession_user = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_path = db.Column(db.String(200), nullable=False)
    thumbnail_path = db.Column(db.String(200), nullable=True)
    uploader_name = db.Column(db.String(80), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    uploader_image = db.Column(db.String(200), nullable=True)
    upload_time = db.Column(db.DateTime, default=datetime.utcnow)
    title = db.Column(db.String(200), nullable=False)  # عنوان الفيديو
    category = db.Column(db.String(100), nullable=False)  # فئة الفيديو


class Playlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    is_public = db.Column(db.Boolean, default=True)  # True = عامة, False = خاصة
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)



class PlaylistVideo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlist.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

@app.route('/post/<int:post_id>')
def view_post(post_id):
    # جلب المنشور بناءً على الـ ID
    post = Post.query.get_or_404(post_id)
    
    # جلب بيانات المستخدم بناءً على ID المستخدم المرتبط بالمنشور
    user = User.query.get_or_404(post.user_id)

    # جلب جميع المنشورات لعرضها في dashboard.html باستثناء المنشور الذي يتم عرض تفاصيله
    posts = Post.query.filter(
        Post.user_profession == current_user.profession,
        Post.user_email != current_user.email,
        Post.id != post_id  # استبعاد المنشور الذي يتم عرضه حاليا
    ).order_by(Post.id.desc()).all()

    # بناء قاموس يحتوي على صور الملف الشخصي لكل مستخدم
    post_authors = {}
    for p in posts:
        if p.user_email not in post_authors:
            author = User.query.filter_by(email=p.user_email).first()
            post_authors[p.user_email] = author.profile_photo if author else 'uploads/default-avatar.jpg'

    # تمرير بيانات المنشور إلى dashboard.html مع إشارة لفتح modal
    return render_template('dashboard.html', posts=posts, post=post, user=user, show_post_modal=True, post_authors=post_authors)

# لسه تابع الفكرة
# @app.route('/post/<int:post_id>')
# def view_post(post_id):
#     post = Post.query.get_or_404(post_id)
#     # جلب بيانات المستخدم المرتبط بالمنشور
#     user = User.query.get_or_404(post.user_id)

#     # عند الوصول إلى رابط المنشور، نمرر المنشور إلى صفحة dashboard.html
#     return render_template('dashboard.html', post=post, user=user)

@app.route('/share/<int:post_id>', methods=['POST'])
def share_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.commit()
    return jsonify({"success": True})



@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = f"{username}@moltka.eg"
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        profession = request.form.get('profession')
        skills = request.form.get('skills')
        security_question = request.form.get('security_question')
        security_answer = request.form.get('security_answer')

        if password != confirm_password:
            flash('كلمات المرور غير متطابقة!', 'error')
            return redirect(url_for('register'))

        user = User.query.filter_by(email=email).first()
        if user:
            flash('اسم المستخدم موجود بالفعل!', 'error')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(
            username=username,
            email=email,
            password=hashed_password,
            profession=profession,
            skills=skills,
            security_question=security_question,
            security_answer=security_answer
        )

        db.session.add(new_user)
        db.session.commit()

        flash('تم إنشاء الحساب بنجاح!', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        email = f"{username}@moltka.eg"
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        
        flash('اسم المستخدم أو كلمة المرور غير صحيحة!', 'error')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # حساب اللون بناءً على اسم المستخدم باستخدام hash
    user_hash = str(uuid.uuid5(uuid.NAMESPACE_DNS, current_user.username))[:6]  # أول 6 أحرف من الـ UUID
    
    # جلب المنشورات التي تطابق تخصص المستخدم ولم يقم بنشرها
    posts = Post.query.filter(
        Post.user_profession == current_user.profession,  # نفس التخصص
        Post.user_email != current_user.email  # ليست من منشورات المستخدم الحالي
    ).order_by(Post.id.desc()).all()
    
    # جلب صور الملف الشخصي لكل مستخدم
    post_authors = {}
    for post in posts:
        if post.user_email not in post_authors:
            author = User.query.filter_by(email=post.user_email).first()
            post_authors[post.user_email] = author.profile_photo if author else 'uploads/default-avatar.jpg'
    
    # حساب عدد الرسائل غير المقروءة باستخدام watched_by_receiver
    unread_count = Message.query.filter_by(receiver_id=current_user.id, watched_by_receiver=False).count()
    
    return render_template('dashboard.html', user_hash=user_hash, posts=posts, post_authors=post_authors, unread_count=unread_count)
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح', 'success')
    return redirect(url_for('login'))

@app.route('/validate-username')
def validate_username():
    username = request.args.get('username')
    email = f"{username}@moltka.eg"
    user = User.query.filter_by(email=email).first()
    return jsonify({'exists': user is not None})

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if user:
            return render_template('reset_password.html', email=email)
        else:
            flash('البريد الإلكتروني غير موجود!', 'error')

    return render_template('forgot_password.html')

@app.route('/reset_password', methods=['POST'])
def reset_password():
    email = request.form.get('email')
    security_answer = request.form.get('security_answer')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    user = User.query.filter_by(email=email).first()

    if user and user.security_answer == security_answer:
        if new_password == confirm_password:
            hashed_password = generate_password_hash(new_password)
            user.password = hashed_password
            db.session.commit()
            flash('تم تغيير كلمة المرور بنجاح!', 'success')
            return redirect(url_for('login'))
        else:
            flash('كلمات المرور غير متطابقة!', 'error')
    else:
        flash('الإجابة على سؤال الأمان غير صحيحة!', 'error')

    return redirect(url_for('forgot_password'))


@app.route('/validate_security_answer', methods=['POST'])
def validate_security_answer():
    data = request.get_json()
    email = data.get('email')
    security_answer = data.get('security_answer')

    user = User.query.filter_by(email=email).first()
    if user and user.security_answer == security_answer:
        return jsonify({'valid': True})
    else:
        return jsonify({'valid': False})

@app.route('/profile')
@login_required
def profile():
    # جلب منشورات المستخدم الحالي فقط
    posts = Post.query.filter_by(
        user_email=current_user.email
    ).order_by(Post.id.desc()).all()
    
    return render_template('profile.html', posts=posts)



@app.route('/profile/<user_email>')
def public_profile(user_email):
    user = User.query.filter_by(email=user_email).first()
    if not user:
        abort(404)  # المستخدم غير موجود
    posts = Post.query.filter_by(user_email=user_email).all()
    return render_template('public_profile.html', user=user, posts=posts)


@app.route('/edit_post_content', methods=['POST'])
@login_required
def edit_post_content():
    post_id = request.form.get('post_id')
    new_content = request.form.get('new_content')
    
    post = Post.query.get(post_id)
    if post and post.user_email == current_user.email:
        post.content = new_content
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/delete_post', methods=['POST'])
@login_required
def delete_post():
    post_id = request.form.get('post_id')
    post = Post.query.get(post_id)
    
    if post and post.user_email == current_user.email:
        db.session.delete(post)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    username = request.form.get('username')
    profession = request.form.get('profession')
    skills = request.form.get('skills')
    
    if not username or not profession:
        flash('جميع الحقول مطلوبة!', 'error')
        return redirect(url_for('profile'))
    
    # التحقق من أن اسم المستخدم غير مستخدم من قبل مستخدم آخر
    if username != current_user.username:
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('اسم المستخدم مستخدم بالفعل!', 'error')
            return redirect(url_for('profile'))
    
    try:
        # تحديث بيانات المستخدم
        current_user.username = username
        current_user.email = f"{username}@moltka.eg"
        current_user.profession = profession
        current_user.skills = skills
        
        # معالجة الصورة الشخصية
        avatar = request.files.get('avatar')
        remove_photo = request.form.get('remove_photo')
        
        if remove_photo:
            # إعادة تعيين الصورة الافتراضية
            if current_user.profile_photo != 'uploads/default-avatar.jpg':
                # حذف الصورة القديمة إذا كانت موجودة
                old_photo_path = os.path.join('static', current_user.profile_photo)
                if os.path.exists(old_photo_path) and 'default-avatar' not in old_photo_path:
                    os.remove(old_photo_path)
            current_user.profile_photo = 'uploads/default-avatar.jpg'
        elif avatar and avatar.filename:
            # حذف الصورة القديمة إذا كانت موجودة
            if current_user.profile_photo != 'uploads/default-avatar.jpg':
                old_photo_path = os.path.join('static', current_user.profile_photo)
                if os.path.exists(old_photo_path) and 'default-avatar' not in old_photo_path:
                    os.remove(old_photo_path)
            
            # حفظ الصورة الجديدة
            filename = f"{int(time.time())}_{secure_filename(avatar.filename)}"
            avatar.save(os.path.join('static/uploads', filename))
            current_user.profile_photo = 'uploads/' + filename
        
        # تحديث المنشورات المرتبطة بالمستخدم
        posts = Post.query.filter_by(user_email=f"{current_user.username}@moltka.eg").all()
        for post in posts:
            post.user_email = f"{username}@moltka.eg"
            post.user_profession = profession
        
        db.session.commit()
        flash('تم تحديث الملف الشخصي بنجاح!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('حدث خطأ أثناء تحديث الملف الشخصي!', 'error')
        print(f"Error updating profile: {str(e)}")
    
    return redirect(url_for('profile'))




@app.route('/add_comment', methods=['POST'])
@login_required
def add_comment():
    post_id = request.form.get('post_id')
    content = request.form.get('content')
    parent_id = request.form.get('parent_id')  # Optional parent comment ID for replies

    if not content or not post_id:
        return jsonify({'success': False, 'message': 'Content and post ID are required.'})
    
    try:
        # Create new comment
        comment = Comment(
            content=content,
            user_id=current_user.id,
            post_id=post_id,
            parent_id=parent_id if parent_id else None,  # Associate reply with parent comment if provided
            created_at=datetime.now()
        )
        db.session.add(comment)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error adding comment: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred while adding the comment.'})


def serialize_comment(comment):
    """Serialize comment and its nested replies."""
    return {
        'id': comment.id,
        'content': comment.content,
        'username': User.query.get(comment.user_id).username if comment.user_id else 'Unknown User',
        'created_at': format_datetime(comment.created_at),
        'profile_photo': User.query.get(comment.user_id).profile_photo if comment.user_id else 'uploads/default-avatar.jpg',
        'replies': [serialize_comment(reply) for reply in comment.replies.order_by(Comment.created_at.asc())]
    }

@app.route('/get_comments/<int:post_id>')
@login_required
def get_comments(post_id):
    comments = Comment.query.filter_by(post_id=post_id, parent_id=None).order_by(Comment.created_at.desc()).all()
    serialized_comments = [serialize_comment(comment) for comment in comments]
    return jsonify(serialized_comments)


@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'GET':
        return render_template('create_post.html')
    
    content = request.form.get('content')
    media = request.files.get('media')
    background_color = request.form.get('background_color')
    
    # معالجة الوسائط المرفقة
    image_url = None
    video_url = None
    if media and media.filename:
        filename = f"{int(time.time())}_{secure_filename(media.filename)}"
        if media.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
            image_url = 'uploads/' + filename
            media.save(os.path.join('static/uploads', filename))
        elif media.filename.lower().endswith(('.mp4', '.mov', '.avi')):
            video_url = 'uploads/' + filename
            media.save(os.path.join('static/uploads', filename))
    
    # إنشاء المنشور باستخدام التوقيت المحلي
    post = Post(
        content=content,
        image_url=image_url,
        video_url=video_url,
        background_color=background_color,
        user_id=current_user.id,
        user_email=current_user.email,  # إضافة إيميل المستخدم تلقائياً
        user_profession=current_user.profession,  # إضافة تخصص المستخدم تلقائياً
        created_at=datetime.now()  # استخدام التوقيت المحلي
    )
    db.session.add(post)
    db.session.commit()
    
    # إرسال رسالة نجاح عبر JavaScript
    return """
        <script>
            window.parent.postMessage('success', '*');
            window.parent.location.reload();
        </script>
    """

# تحميل المستخدم
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

active_users = set()  # قائمة بالمستخدمين النشطين في المحادثة

print(active_users)
# صفحة الرسائل
@app.route('/messages/<user_email>')
@login_required
def messages(user_email):
    user = User.query.filter_by(email=user_email).first()
    if not user:
        abort(404)
    
    # إضافة المستخدم إلى قائمة المستخدمين النشطين
    active_users.add(current_user.id)
    active_users.add(user.id)

    # تحديث الرسائل إلى "مقروءة" من قبل المستقبل عند فتح الصفحة
    Message.query.filter_by(receiver_id=current_user.id, sender_id=user.id, watched_by_receiver=False).update({'watched_by_receiver': True})
    db.session.commit()

    return render_template('messages.html', user=user, current_user=current_user)

# الحصول على الرسائل
@app.route('/get_messages/<int:user_id>', methods=['GET'])
@login_required
def get_messages(user_id):
    # تحديث حالة الرسائل إلى "مقروءة" من قبل المستقبل عند فتح المحادثة
    Message.query.filter_by(receiver_id=current_user.id, sender_id=user_id, watched_by_receiver=False).update({'watched_by_receiver': True})
    db.session.commit()

    # تحديث حالة الرسائل إلى "مقروءة" من قبل المرسل عند فتح المحادثة
    Message.query.filter_by(sender_id=current_user.id, receiver_id=user_id, watched_by_sender=False).update({'watched_by_sender': True})
    db.session.commit()

    # الحصول على الرسائل بترتيب تصاعدي
    messages = Message.query.filter(
        (Message.sender_id == current_user.id) & (Message.receiver_id == user_id) |
        (Message.sender_id == user_id) & (Message.receiver_id == current_user.id)
    ).order_by(Message.created_at.asc()).all()
    
    messages_data = [
        {
            'id': message.id,
            'sender_id': message.sender_id,
            'receiver_id': message.receiver_id,
            'content': message.content,
            'file_url': message.file_url,
            'file_type': message.file_type,
            'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'watched_by_receiver': message.watched_by_receiver,  # حالة مشاهدة المستقبل
            'watched_by_sender': message.watched_by_sender       # حالة مشاهدة المرسل
        } for message in messages
    ]
    return jsonify(messages_data)

# إرسال رسالة


# إعدادات الرفع
app.config['UPLOAD_FOLDER'] = 'static/uploads'  # مجلد الرفع
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}  # الامتدادات المسموحة

# دالة للتحقق من امتداد الملف
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# دالة لتحميل الملف
# دالة لتحميل الملف
def upload_file(file):
    if file and allowed_file(file.filename):
        # تأكد من أن الملف يحتوي على اسم صالح
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)  # حفظ الملف في المجلد المحدد
        # تعديل المسار ليكون متوافقًا مع الويب
        return filepath.replace("\\", "/")  # استبدال "\" بـ "/"
    return None  # إذا كان الملف غير صالح أو لم يتم رفعه

# نقطة النهاية لإرسال الرسالة
@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    data = request.form
    receiver_id = data.get('receiver_id')
    content = data.get('content')
    file = request.files.get('file')

    if not receiver_id or (not content and not file):
        return jsonify({'success': False, 'error': 'Missing receiver_id or content/file'}), 400

    try:
        # إنشاء رسالة جديدة
        new_message = Message(
            sender_id=current_user.id,
            receiver_id=receiver_id,
            content=content,
            file_url=upload_file(file) if file else None,  # استخدام دالة upload_file لتحميل الملف
            file_type=file.content_type if file else None,
            watched_by_receiver=False,
            watched_by_sender=True
        )
        db.session.add(new_message)
        db.session.commit()

        # إرجاع معرف الرسالة في الاستجابة
        return jsonify({
            'success': True,
            'message_id': new_message.id  # تأكد من إرجاع معرف الرسالة
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
# SSE endpoint
@app.route('/stream_messages/<int:user_id>')
@login_required
def stream_messages(user_id):
    def event_stream():
        last_message_id = None  # لتتبع آخر رسالة تم إرسالها

        while True:
            try:
                # تحقق من وجود رسائل جديدة
                query = Message.query.filter(
                    ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id)) |
                    ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
                ).order_by(Message.created_at.desc())

                if last_message_id:
                    query = query.filter(Message.id > last_message_id)  # التحقق من الرسائل الجديدة فقط

                messages = query.limit(1).all()

                if messages:
                    message = messages[0]
                    last_message_id = message.id  # تحديث آخر رسالة تم إرسالها

                    # إرسال بيانات الرسالة
                    yield f"data: {json.dumps({
                        'message_id': message.id,
                        'sender_id': message.sender_id,
                        'receiver_id': message.receiver_id,
                        'content': message.content,
                        'file_url': message.file_url,
                        'file_type': message.file_type,
                        'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'watched_by_receiver': message.watched_by_receiver,  # حالة مشاهدة المستقبل
                        'watched_by_sender': message.watched_by_sender       # حالة مشاهدة المرسل
                    })}\n\n"

                time.sleep(1)  # انتظر ثانية قبل التحقق مرة أخرى

            except Exception as e:
                print(f"Error in SSE stream: {e}")
                time.sleep(5)  # انتظر 5 ثوانٍ قبل إعادة المحاولة

    return Response(stream_with_context(event_stream()), content_type='text/event-stream')


@app.route('/is_user_active/<int:user_id>')
@login_required
def is_user_active(user_id):
    # تحقق مما إذا كان المستخدم نشطًا (مثال: من مجموعة active_users)
    is_active = user_id in active_users  # active_users هي مجموعة تحتوي على معرفات المستخدمين النشطين
    print(is_active)
    return jsonify({
        'active': is_active
    })




# دالة لتحديد نوع الملف (صورة أو فيديو)
def get_file_type(content, file_url):
    if content:  # إذا كان هناك محتوى نصي
        return 'text'  # نص عادي

    # إذا كان content فارغًا وكان file_url يحتوي على امتداد صورة أو فيديو
    if file_url:
        _, ext = os.path.splitext(file_url)  # استخراج الامتداد من رابط الملف
        if ext.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:  # امتدادات الصور
            return 'image'  # نوع الملف صورة
        elif ext.lower() in ['.mp4', '.avi', '.mov', '.mkv']:  # امتدادات الفيديو
            return 'video'  # نوع الملف فيديو

    return 'text'  # إذا لم يتم التحديد (نص افتراضي)


@app.route('/get_notifications')
@login_required
def get_notifications():
    # الحصول على جميع الرسائل المرسلة إلى المستخدم الحالي (التي استلمها)
    received_messages = Message.query.filter(
        (Message.receiver_id == current_user.id) &  # الرسائل التي استلمها المستخدم الحالي
        (Message.sender_id != current_user.id)      # استبعاد الرسائل التي أرسلها المستخدم الحالي إلى نفسه
    ).order_by(Message.created_at.desc()).all()

    # الحصول على جميع الرسائل التي أرسلها المستخدم الحالي (ولم يرَ أن المستقبل شاهدها)
    sent_messages = Message.query.filter(
        (Message.sender_id == current_user.id) &    # الرسائل التي أرسلها المستخدم الحالي
        (Message.watched_by_sender == False)        # الرسائل التي لم يرَ المرسل أن المستقبل شاهدها
    ).order_by(Message.created_at.desc()).all()

    # دمج الرسائل المستلمة والمرسلة
    notifications = []

    for message in received_messages:
        sender = User.query.get(message.sender_id)
        file_type = get_file_type(message.content, message.file_url)  # تحديد نوع الملف بناءً على content و file_url
        notifications.append({
            'id': message.id,
            'sender_id': message.sender_id,
            'sender_name': sender.username,
            'sender_email': sender.email,
            'sender_photo': url_for('static', filename=sender.profile_photo),
            'content': message.content,
            'file_url': message.file_url,  # إضافة رابط الملف
            'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'watched_by_receiver': message.watched_by_receiver,  # حالة مشاهدة المستقبل
            'is_received': True,  # تم استلام الرسالة
            'file_type': file_type  # إضافة نوع الملف
        })

    for message in sent_messages:
        receiver = User.query.get(message.receiver_id)
        file_type = get_file_type(message.content, message.file_url)  # تحديد نوع الملف بناءً على content و file_url
        notifications.append({
            'id': message.id,
            'receiver_id': message.receiver_id,
            'receiver_name': receiver.username,
            'receiver_email': receiver.email,
            'receiver_photo': url_for('static', filename=receiver.profile_photo),
            'content': message.content,
            'file_url': message.file_url,  # إضافة رابط الملف
            'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'watched_by_sender': message.watched_by_sender,  # حالة مشاهدة المرسل
            'is_received': False,  # تم إرسال الرسالة
            'file_type': file_type  # إضافة نوع الملف
        })

    return jsonify(notifications)

# تحديث جميع الرسائل غير المقروءة إلى "مقروءة"
@app.route('/mark_all_as_read', methods=['POST'])
@login_required
def mark_all_as_read():
    # تحديث جميع الرسائل غير المقروءة إلى "مقروءة"
    Message.query.filter_by(receiver_id=current_user.id, watched_by_receiver=False).update({'watched_by_receiver': False})
    db.session.commit()
    return jsonify({'success': True})

# بث عدد الرسائل غير المقروءة
@app.route('/stream_unread_count')
@login_required
def stream_unread_count():
    def event_stream():
        last_count = None  # لتتبع آخر عدد تم إرساله

        while True:
            # الحصول على عدد الرسائل غير المقروءة
            unread_count = Message.query.filter(
                (Message.receiver_id == current_user.id) &  # الرسائل التي استلمها المستخدم الحالي
                (Message.watched_by_receiver == False)      # الرسائل غير المقروءة
            ).count()

            # إرسال التحديث فقط إذا تغير العدد
            if unread_count != last_count:
                last_count = unread_count
                yield f"data: {json.dumps({'unread_count': unread_count})}\n\n"

            time.sleep(1)  # انتظر ثانية قبل التحقق مرة أخرى

    return Response(stream_with_context(event_stream()), content_type='text/event-stream')


@app.route('/mark_message_as_seen/<int:message_id>', methods=['POST'])
@login_required
def mark_message_as_seen(message_id):
    # تحديث حالة الرسالة إلى "مقروءة" من قبل المستقبل
    message = Message.query.get(message_id)
    if message and message.receiver_id == current_user.id:
        message.watched_by_receiver = True
        message.last_updated = datetime.utcnow()  # تحديث وقت التعديل
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 404



@app.route('/get_unread_count')
@login_required
def get_unread_count():
    # حساب عدد الرسائل غير المقروءة للمستقبل
    unread_receiver_count = Message.query.filter(
        (Message.receiver_id == current_user.id) &  # الرسائل التي استلمها المستخدم الحالي
        (Message.watched_by_receiver == False)      # الرسائل غير المقروءة
    ).count()

    # حساب عدد الرسائل غير المقروءة للمرسل
    unread_sender_count = Message.query.filter(
        (Message.sender_id == current_user.id) &    # الرسائل التي أرسلها المستخدم الحالي
        (Message.watched_by_sender == False)        # الرسائل التي لم يرَ المرسل أن المستقبل شاهدها
    ).count()

    # إجمالي عدد الرسائل غير المقروءة
    total_unread_count = unread_receiver_count + unread_sender_count

    return jsonify({'unread_count': total_unread_count})



@app.route('/stream_message_updates/<int:user_id>')
@login_required
def stream_message_updates(user_id):
    def event_stream():
        last_update_time = datetime.utcnow()  # وقت بدء الاتصال

        while True:
            # البحث عن الرسائل التي تهم المستخدم الحالي (مرسلة أو مستلمة)
            messages = Message.query.filter(
                (
                    (Message.sender_id == current_user.id) |  # الرسائل المرسلة من المستخدم الحالي
                    (Message.receiver_id == current_user.id)  # الرسائل المستلمة للمستخدم الحالي
                ) &
                (Message.last_updated > last_update_time)     # التحديثات الجديدة بعد آخر تحقق
            ).order_by(Message.last_updated.asc()).all()

            if messages:
                last_update_time = messages[-1].last_updated  # تحديث وقت التحقق الأخير

                for message in messages:
                    yield f"data: {json.dumps({
                        'message_id': message.id,
                        'sender_id': message.sender_id,
                        'receiver_id': message.receiver_id,
                        'watched_by_receiver': message.watched_by_receiver,
                        'watched_by_sender': message.watched_by_sender
                    })}\n\n"

            time.sleep(0.5)  # تحقق كل 0.5 ثانية لتحسين الأداء

    return Response(stream_with_context(event_stream()), content_type='text/event-stream')

@app.route('/leave_chat', methods=['POST'])
@login_required
def leave_chat():
    # سجل عند بدء الدالة
    print(f"Attempting to leave chat for user {current_user.id}")
    
    # إزالة المستخدم من قائمة المستخدمين النشطين
    active_users.discard(current_user.id)

    # سجل بعد التعديل على القائمة
    print(f"User {current_user.id} left the chat. Active users: {active_users}")

    return jsonify({'success': True})


@app.route('/join_chat', methods=['POST'])
@login_required
def join_chat():
    # إضافة المستخدم إلى قائمة المستخدمين النشطين
    active_users.add(current_user.id)
    print(active_users)
    return jsonify({'success': True})



@app.route('/mark_all_as_seen', methods=['POST'])
@login_required
def mark_all_as_seen():
    receiver_id = request.form.get('receiver_id')

    # تحديث الرسائل المرسلة من المستخدم الحالي إلى المستقبل (watched_by_receiver)
    Message.query.filter(
        (Message.sender_id == current_user.id) &
        (Message.receiver_id == receiver_id) &
        (Message.watched_by_receiver == False)
    ).update({'watched_by_receiver': True})

    # تحديث الرسائل المستلمة من المستقبل (watched_by_sender)
    Message.query.filter(
        (Message.sender_id == receiver_id) &
        (Message.receiver_id == current_user.id) &
        (Message.watched_by_sender == False)
    ).update({'watched_by_sender': True})

    db.session.commit()
    return jsonify({'success': True})



@app.route('/getchat')
@login_required
def get_chat():
    # الحصول على آخر الرسائل بين المستخدم الحالي والمستخدمين الآخرين
    subquery = db.session.query(
        db.case(
            (Message.sender_id > Message.receiver_id, Message.sender_id),
            else_=Message.receiver_id
        ).label('user1'),
        db.case(
            (Message.sender_id > Message.receiver_id, Message.receiver_id),
            else_=Message.sender_id
        ).label('user2'),
        db.func.max(Message.id).label('last_message_id')
    ).filter(
        (Message.receiver_id == current_user.id) |  # المستخدم الحالي هو المستقبل
        (Message.sender_id == current_user.id)      # أو المستخدم الحالي هو المرسل
    ).group_by('user1', 'user2').subquery()

    # جلب تفاصيل الرسائل
    latest_messages = Message.query.join(
        subquery, Message.id == subquery.c.last_message_id
    ).order_by(Message.created_at.desc()).all()

    # بناء البيانات للإرجاع
    chats = []
    for message in latest_messages:
        # تحديد المستخدم الآخر
        if message.sender_id == current_user.id:
            other_user = User.query.get(message.receiver_id)
        else:
            other_user = User.query.get(message.sender_id)

        # حساب عدد الرسائل غير المقروءة
        unread_count = Message.query.filter(
            (Message.receiver_id == current_user.id) &  # الرسائل التي استلمها المستخدم الحالي
            (Message.sender_id == other_user.id) &     # الرسائل من المستخدم الآخر
            (Message.watched_by_receiver == False)      # الرسائل غير المقروءة
        ).count()

        # تحديد نوع المحتوى بناءً على الرسالة
        last_message = message.content
        message_type = None  # نوع الرسالة (نص، فيديو، صورة)
        
        # تحقق من نوع المحتوى
        if last_message:
            # إذا كان content نصياً وليس صورة
            if not message.file_url or not message.file_url.lower().endswith(('jpg', 'jpeg', 'png')):
                message_type = 'text'
        elif message.file_url:
            # إذا كان content فارغاً وكان file_url به في آخره امتداد فيديو
            if message.file_url.lower().endswith(('mp4', 'avi', 'mov')):
                message_type = 'video'
            # إذا كان content فارغاً وكان file_url به في آخره امتداد صورة
            elif message.file_url.lower().endswith(('jpg', 'jpeg', 'png')):
                message_type = 'image'

        # إضافة بيانات المحادثة
        chats.append({
            'id': message.id,
            'user_id': other_user.id,
            'user_name': other_user.username,
            'user_email': other_user.email,
            'user_photo': url_for('static', filename=other_user.profile_photo),
            'last_message': last_message,
            'message_type': message_type,  # إضافة نوع الرسالة
            'unread_count': unread_count,  # إضافة عدد الرسائل غير المقروءة
            'last_updated': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'is_sender': message.sender_id == current_user.id  # هل المرسل هو المستخدم الحالي؟
        })

    return jsonify(chats)

@app.route('/search_users')
def search_users():
    query = request.args.get('q', '')
    if query:
        # البحث في قاعدة البيانات
        users = User.query.filter(User.username.like(f'%{query}%')).all()
        # تجهيز البيانات لعرضها في الواجهة
        results = [{
            'username': user.username,
            'profile_photo': user.profile_photo
        } for user in users]
        return jsonify(results)
    return jsonify([])  # في حالة عدم وجود نتائج

from flask_login import current_user  # تأكد من استيراد current_user

@app.route('/artical', methods=['GET'])
def artical_page():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    
    # جلب المقالات التي تتطابق مع profession الخاص بالمستخدم الحالي
    articles = Article.query.filter_by(profession_user=current_user.profession).order_by(Article.created_at.desc()).all()
    
    return render_template('artical.html', articles=articles)

@app.route('/create', methods=['POST'])
def create_article():
    data = request.get_json()
    title = data['title']

    # جلب اسم المستخدم الحالي من الجلسة
    if current_user.is_authenticated:  # تأكد من أن المستخدم مسجل الدخول
        user = current_user.username  # اسم المستخدم الحالي
        id_user = current_user.id  # معرف المستخدم الحالي
        photo_user = current_user.profile_photo  # صورة المستخدم الحالي
        profession_user = current_user.profession
    else:
        return jsonify({"error": "يجب تسجيل الدخول لإنشاء مقال"}), 401

    # استخدام الذكاء الاصطناعي لإنشاء محتوى المقال
    client = Client()
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"Write an article about {title}"}],
        stream=True,
        web_search=False
    )

    # جمع نص المقال
    content_markdown = ""
    for chunk in stream:
        if chunk.choices[0].delta.content:
            content_markdown += chunk.choices[0].delta.content

    # تحويل Markdown إلى HTML باستخدام إضافات لتحسين النتيجة
    extensions = [
        'fenced_code',  # لدعم code blocks
        'tables',       # لدعم الجداول
        'toc',          # لدعم جدول المحتويات
        'nl2br',        # لتحويل الأسطر الجديدة إلى <br>
    ]
    content_html = markdown.markdown(content_markdown, extensions=extensions)  # تم التصحيح هنا

    # معالجة الأكواد البرمجية بشكل صحيح
    # البحث عن الأكواد البرمجية التي تبدأ بـ ```language وإغلاقها بـ ```
    content_html = re.sub(r'```(\w+)', r'<pre><code class="\1">', content_html)
    content_html = content_html.replace('```', '</code></pre>')

    # حفظ المقال في قاعدة البيانات
    article = Article(title=title, content=content_html, user=user, id_user=id_user, photo_user=photo_user , profession_user = profession_user)
    db.session.add(article)
    db.session.commit()

    # الرد على العميل بإرجاع البيانات التي تم إنشاؤها
    return jsonify({
        "title": article.title,
        "content": article.content,
        "user": article.user,
        "created_at": article.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        "photo_user": f"/static/{article.photo_user}",
        "id_user": id_user 
    })

@app.route('/current_user_id', methods=['GET'])
def get_current_user_id():
    if current_user.is_authenticated:  # التأكد من أن المستخدم مسجل الدخول
        print(f"ID المستخدم الحالي: {current_user.id}")  # عرض id المستخدم في الطرفية
        return jsonify({'id': current_user.id}), 200  # إرجاع id فقط
    else:
        print("المستخدم غير مسجل الدخول")  # عرض رسالة في الطرفية إذا لم يكن المستخدم مسجل الدخول
        return jsonify({'error': 'User not authenticated'}), 401





def calculate_frame_contrast(frame):
    """
    حساب التباين في الإطار باستخدام Pillow
    """
    image = Image.fromarray(frame)
    gray_image = image.convert('L')
    img_array = np.array(gray_image)
    contrast = np.std(img_array)
    return contrast

def get_video_duration(video_path):
    """
    الحصول على مدة الفيديو بالثواني
    """
    return len(list(iio.imiter(video_path)))

def generate_thumbnail(video_path):
    """
    إنشاء صورة مصغرة من ملف فيديو باستخدام 3 إطارات عشوائية
    """
    thumbnail_filename = os.path.splitext(os.path.basename(video_path))[0] + '_thumbnail.jpg'
    thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)

    # الحصول على مدة الفيديو
    video_length = get_video_duration(video_path)
    
    # اختيار 3 أوقات عشوائية متباعدة
    frame_positions = sorted([
        int(video_length * 0.2 + random.randint(0, int(video_length * 0.2))),
        int(video_length * 0.5 + random.randint(0, int(video_length * 0.2))),
        int(video_length * 0.8 + random.randint(0, int(video_length * 0.2)))
    ])

    max_contrast = 0
    best_frame = None
    
    # قراءة الفيديو
    reader = iio.imiter(video_path)
    
    # معالجة الإطارات المختارة فقط
    for i, frame in enumerate(reader):
        if i in frame_positions:
            contrast = calculate_frame_contrast(frame)
            
            if contrast > max_contrast:
                max_contrast = contrast
                best_frame = frame

    if best_frame is not None:
        # تحويل numpy array إلى صورة Pillow
        image = Image.fromarray(best_frame)
        
        # أبعاد الصورة المصغرة المطلوبة
        target_width, target_height = 1280, 720
        
        # حساب نسبة العرض إلى الارتفاع
        original_width, original_height = image.size
        aspect_ratio_original = original_width / original_height
        aspect_ratio_target = target_width / target_height
        
        # تغيير الحجم مع الحفاظ على النسبة
        if aspect_ratio_original > aspect_ratio_target:
            new_width = target_width
            new_height = int(target_width / aspect_ratio_original)
        else:
            new_height = target_height
            new_width = int(target_height * aspect_ratio_original)
        
        # تغيير حجم الصورة
        resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # حساب اللون السائد
        img_array = np.array(image)
        dominant_color = tuple(map(int, np.mean(img_array, axis=(0, 1))))
        
        # إنشاء صورة جديدة بالخلفية
        thumbnail = Image.new('RGB', (target_width, target_height), dominant_color)
        
        # حساب الإزاحة لوضع الصورة في المنتصف
        x_offset = (target_width - new_width) // 2
        y_offset = (target_height - new_height) // 2
        
        # وضع الصورة في المنتصف
        thumbnail.paste(resized_image, (x_offset, y_offset))
        
        # حفظ الصورة المصغرة
        thumbnail.save(thumbnail_path, 'JPEG', quality=95)
    
    return thumbnail_path



@app.route('/videos', methods=['GET', 'POST'])
@login_required
def videos():
    if request.method == 'POST':
        # الحصول على العنوان من المستخدم
        title = request.form.get('title')

        # تخزين الفئة الحالية للمستخدم وقت الرفع
        category = current_user.profession  

        # التعامل مع رفع الفيديو
        video = request.files.get('video')
        thumbnail = request.files.get('thumbnail')

        if video:
            # معالجة الفيديو
            video_filename = secure_filename(video.filename)
            video_path = os.path.join(app.config['UPLOAD_FOLDER2'], video_filename)
            video.save(video_path)

            # معالجة الصورة المصغرة
            thumbnail_path = None
            if thumbnail:
                thumbnail_filename = secure_filename(thumbnail.filename)
                thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)
                thumbnail.save(thumbnail_path)
            else:
                # إنشاء صورة مصغرة تلقائيًا
                thumbnail_path = generate_thumbnail(video_path)

            # إنشاء كائن فيديو جديد في قاعدة البيانات
            new_video = Video(
                video_path=video_path,
                thumbnail_path=thumbnail_path,
                uploader_name=current_user.username,
                user_id=current_user.id,
                uploader_image=current_user.profile_photo,
                title=title,  # إضافة العنوان
                category=category  # تخزين الفئة بناءً على حالة المستخدم عند رفع الفيديو
            )
            db.session.add(new_video)
            db.session.commit()

            flash('تم رفع الفيديو بنجاح!', 'success')
            return redirect(url_for('videos'))

    # عند جلب الفيديوهات يتم عرض صفحة فقط بدون تحميل الفيديوهات فوراً
    return render_template('videos.html')


@app.route('/get_videos', methods=['GET'])
@login_required
def get_videos():
    current_user_id = current_user.id  # الحصول على معرف المستخدم الحالي

    # تصفية مقاطع الفيديو بناءً على فئة المستخدم الحالية
    videos = Video.query.filter_by(category=current_user.profession).order_by(Video.upload_time.desc()).all()
    
    # تحويل البيانات إلى JSON بحيث يمكن إرسالها إلى المتصفح
    videos_data = [{
        'id': video.id,
        'title': video.title,
        'thumbnail': video.thumbnail_path,
        'uploader_name': video.uploader_name,
        'upload_time': video.upload_time.strftime('%Y-%m-%d %H:%M:%S'),
        'uploader_image': url_for('static', filename=video.uploader_image),
        'category': video.category,  # إضافة الفئة
        'video_path': video.video_path,  # مسار الفيديو
        'is_owner': video.user_id == current_user_id  # تحديد إذا كان المستخدم الحالي هو صاحب الفيديو
    } for video in videos]

    return jsonify(videos_data)





# Route لتعديل عنوان الفيديو
@app.route('/edit_video/<int:video_id>', methods=['POST'])
def edit_video(video_id):
    video = Video.query.get_or_404(video_id)
    data = request.get_json()
    new_title = data.get('title')

    if new_title:
        video.title = new_title
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'العنوان غير صالح'}), 400

# Route لحذف الفيديو
@app.route('/delete_video/<int:video_id>', methods=['DELETE'])
@login_required
def delete_video(video_id):
    # التحقق من أن الفيديو موجود
    video = Video.query.get_or_404(video_id)

    # التحقق من أن المستخدم الحالي هو صاحب الفيديو
    if video.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'غير مصرح لك بحذف هذا الفيديو'}), 403

    # حذف جميع السجلات المرتبطة بالفيديو من جدول playlist_video
    PlaylistVideo.query.filter_by(video_id=video_id).delete()

    # حذف ملف الفيديو من المجلد
    if video.video_path:
        video_file_name = os.path.basename(video.video_path)  # الحصول على اسم الملف فقط
        video_file_path = os.path.join(app.config['UPLOAD_FOLDER2'], video_file_name)
        print(f"Video file path: {video_file_path}")  # طباعة مسار ملف الفيديو
        if os.path.exists(video_file_path):
            os.remove(video_file_path)
        else:
            print("Video file does not exist!")

    # حذف ملف الصورة المصغرة من المجلد
    if video.thumbnail_path:
        thumbnail_file_name = os.path.basename(video.thumbnail_path)  # الحصول على اسم الملف فقط
        thumbnail_file_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_file_name)
        print(f"Thumbnail file path: {thumbnail_file_path}")  # طباعة مسار الصورة المصغرة
        if os.path.exists(thumbnail_file_path):
            os.remove(thumbnail_file_path)
        else:
            print("Thumbnail file does not exist!")

    # حذف الفيديو من جدول الفيديوهات
    db.session.delete(video)
    db.session.commit()

    return jsonify({'success': True})


# Route لإضافة الفيديو إلى قائمة التشغيل
# Route لجلب قوائم التشغيل
@app.route('/get_playlists_with_video_status/<int:video_id>', methods=['GET'])
@login_required
def get_playlists_with_video_status(video_id):
    playlists = Playlist.query.filter_by(user_id=current_user.id).all()
    playlists_data = []
    for playlist in playlists:
        video_exists = PlaylistVideo.query.filter_by(playlist_id=playlist.id, video_id=video_id).first() is not None
        playlists_data.append({
            'id': playlist.id,
            'name': playlist.name,
            'is_public': playlist.is_public,
            'video_exists': video_exists,
        })
    return jsonify(playlists_data)


@app.route('/remove_video_from_playlist/<int:playlist_id>/<int:video_id>', methods=['DELETE'])
@login_required
def remove_video_from_playlist(playlist_id, video_id):
    playlist_video = PlaylistVideo.query.filter_by(playlist_id=playlist_id, video_id=video_id).first()
    if playlist_video:
        db.session.delete(playlist_video)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'الفيديو غير موجود في القائمة'}), 404

# Route لإنشاء قائمة تشغيل جديدة
@app.route('/create_playlist', methods=['POST'])
@login_required
def create_playlist():
    data = request.get_json()
    new_playlist = Playlist(
        name=data['name'],
        is_public=data['is_public'],
        user_id=current_user.id
    )
    db.session.add(new_playlist)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/add_video_to_playlist/<int:playlist_id>/<int:video_id>', methods=['POST'])
@login_required
def add_video_to_playlist(playlist_id, video_id):
    # التحقق من أن الفيديو والقائمة موجودة
    video = Video.query.get_or_404(video_id)
    playlist = Playlist.query.get_or_404(playlist_id)

    # التحقق من أن المستخدم يملك القائمة
    if playlist.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'غير مصرح لك بإضافة الفيديو إلى هذه القائمة'}), 403

    # التحقق من أن الفيديو غير موجود بالفعل في القائمة
    existing_playlist_video = PlaylistVideo.query.filter_by(playlist_id=playlist_id, video_id=video_id).first()
    if existing_playlist_video:
        return jsonify({'success': False, 'message': 'الفيديو موجود بالفعل في القائمة'}), 400

    # إضافة الفيديو إلى القائمة
    playlist_video = PlaylistVideo(playlist_id=playlist_id, video_id=video_id)
    db.session.add(playlist_video)
    db.session.commit()
    return jsonify({'success': True})

    

@app.route('/delete_playlist/<int:playlist_id>', methods=['DELETE'])
@login_required
def delete_playlist(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)

    # التحقق من أن المستخدم يملك القائمة
    if playlist.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'غير مصرح لك بحذف هذه القائمة'}), 403

    # حذف القائمة
    db.session.delete(playlist)
    db.session.commit()
    return jsonify({'success': True})




def get_current_user_id():
    # افترض أنك تستخدم Flask-Login
    if current_user.is_authenticated:
        return current_user.id
    else:
        return None  # أو يمكنك رفع استثناء إذا لم يكن المستخدم معتمدًا

@app.route('/get_playlists')
def get_playlists():
    current_user_id = get_current_user_id()
    
    if current_user_id is None:
        return jsonify({"error": "User not authenticated"}), 401
    
    # جلب القوائم العامة التي لا تنتمي إلى المستخدم الحالي
    playlists = Playlist.query.filter(
        Playlist.is_public == True,  # فقط القوائم العامة
        Playlist.user_id != current_user_id  # استبعاد قوائم المستخدم الحالي
    ).all()
    
    # تحويل البيانات إلى تنسيق JSON
    playlists_data = [{'id': playlist.id, 'name': playlist.name} for playlist in playlists]
    
    return jsonify(playlists_data)


@app.route('/get_user_playlists')
def get_user_playlists():
    # الحصول على معرف المستخدم الحالي
    current_user_id = get_current_user_id()
    
    if current_user_id is None:
        return jsonify({"error": "User not authenticated"}), 401
    
    # جلب قوائم التشغيل الخاصة بالمستخدم الحالي
    playlists = Playlist.query.filter(
        Playlist.user_id == current_user_id  # فقط قوائم المستخدم الحالي
    ).all()
    
    # تحويل البيانات إلى تنسيق JSON
    playlists_data = [{'id': playlist.id, 'name': playlist.name} for playlist in playlists]
    
    return jsonify(playlists_data)


@app.route('/get_playlist_videos/<int:playlist_id>')
@login_required
def get_playlist_videos(playlist_id):
    # جلب قائمة التشغيل بواسطة المعرف، إذا لم توجد ترجع 404
    playlist = Playlist.query.get_or_404(playlist_id)
    
    # جلب الفيديوهات المرتبطة بقائمة التشغيل المحددة باستخدام جدول الوسيط PlaylistVideo
    videos = db.session.query(Video).join(PlaylistVideo).filter(PlaylistVideo.playlist_id == playlist_id).all()
    
    # تحقق إذا كان المستخدم هو مالك قائمة التشغيل
    is_owner = playlist.user_id == current_user.id
    
    # تجهيز البيانات لإرسالها
    videos_data = [{
        'id': video.id,
        'title': video.title,
        'thumbnail_path': video.thumbnail_path,
        'uploader_name': video.uploader_name,
        'uploader_image': video.uploader_image,
        'upload_time': video.upload_time.strftime('%Y-%m-%d %H:%M:%S'),  # تنسيق الوقت
        'is_owner': is_owner  # إضافة إذا كان المستخدم هو مالك القائمة
    } for video in videos]
    
    return jsonify(videos_data)


@app.route('/get_video/<int:video_id>')
def get_video(video_id):
    # جلب الفيديو بواسطة المعرف، إذا لم يكن موجودًا ترجع 404
    video = Video.query.get_or_404(video_id)
    
    # تجهيز البيانات الخاصة بالفيديو لإرسالها
    video_data = {
        'id': video.id,
        'title': video.title,
        'video_path': video.video_path,
        'uploader_name': video.uploader_name,
        'uploader_image': video.uploader_image,
        'upload_time': video.upload_time.strftime('%Y-%m-%d %H:%M:%S')  # تنسيق الوقت
    }
    
    return jsonify(video_data)



# حذف الفيديو من قائمة التشغيل
@app.route('/delete_video_from_playlist', methods=['POST'])
@login_required
def delete_video_from_playlist():
    video_id = request.json.get('video_id')
    playlist_id = request.json.get('playlist_id')

    # التحقق من أن الفيديو موجود في قائمة التشغيل
    playlist_video = PlaylistVideo.query.filter_by(video_id=video_id, playlist_id=playlist_id).first()
    
    if not playlist_video:
        return jsonify({"message": "الفيديو ليس موجودًا في قائمة التشغيل"}), 400

    # التحقق من أن المستخدم هو من أنشأ قائمة التشغيل
    playlist = Playlist.query.get(playlist_id)
    if playlist.user_id != current_user.id:
        return jsonify({"message": "ليس لديك صلاحية لحذف الفيديو من هذه القائمة"}), 403

    # حذف السجل من جدول PlaylistVideo
    db.session.delete(playlist_video)
    db.session.commit()

    return jsonify({"message": "تم حذف الفيديو من قائمة التشغيل بنجاح"}), 200


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        Session = scoped_session(sessionmaker(bind=db.engine))
    app.run(debug=True , host="0.0.0.0")
