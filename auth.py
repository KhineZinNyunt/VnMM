from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from supabase import create_client
import os
from datetime import datetime
import uuid
from werkzeug.utils import secure_filename

auth = Blueprint('auth', __name__)

# Supabase connection
SUPABASE_URL = "https://vzzkvfxwhjmgmvgiievp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ6emt2Znh3aGptZ212Z2lpZXZwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ2MTMzNjAsImV4cCI6MjA5MDE4OTM2MH0.gvFlaSoivHMR2Go27kGjXCBfVoGWazaGybEkwHHl3kE"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Upload configuration
UPLOAD_FOLDER = 'static/profile_images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_profile_image(file):
    if file and allowed_file(file.filename):
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        return f"/static/profile_images/{filename}"
    return None

def get_customer():
    customer_id = session.get('customer_id')
    if customer_id:
        try:
            customer = supabase.table('customers').select('*').eq('id', customer_id).execute()
            if customer.data and len(customer.data) > 0:
                return customer.data[0]
        except Exception as e:
            print(f"Error getting customer: {e}")
            return None
    return None

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        country_code = request.form.get('country_code')
        phone = request.form.get('phone')
        address = request.form.get('address')
        city = request.form.get('city')
        country = request.form.get('country')
        
        full_phone = f"{country_code} {phone}" if phone and country_code else phone
        
        try:
            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            
            customer_data = {
                'id': auth_response.user.id,
                'email': email,
                'full_name': full_name,
                'phone': full_phone,
                'address': address,
                'city': city,
                'country': country,
                'created_at': datetime.now().isoformat()
            }
            supabase.table('customers').insert(customer_data).execute()
            
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            flash('Error creating account. Email might already exist.', 'error')
    
    return render_template('auth/register.html')

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            customer = supabase.table('customers').select('*').eq('email', email).execute()
            
            if customer.data and len(customer.data) > 0:
                session['customer_id'] = customer.data[0]['id']
                session['customer_email'] = customer.data[0]['email']
                session['customer_name'] = customer.data[0]['full_name']
                session['profile_image'] = customer.data[0].get('profile_image', '')
                flash(f'Welcome back, {customer.data[0]["full_name"]}!', 'success')
                return redirect(url_for('home'))
            else:
                flash('User not found', 'error')
                
        except Exception as e:
            flash('Invalid email or password', 'error')
    
    return render_template('auth/login.html')

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        try:
            customer = supabase.table('customers').select('*').eq('email', email).execute()
            
            if customer.data and len(customer.data) > 0:
                flash(f'Password reset request received for {email}. Please check your email.', 'info')
            else:
                flash(f'If an account exists with {email}, you will receive password reset instructions shortly.', 'info')
            
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            flash('Please contact support for password reset assistance.', 'info')
            return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html')

@auth.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    access_token = request.args.get('access_token')
    refresh_token = request.args.get('refresh_token')
    type = request.args.get('type')
    
    if access_token and type == 'recovery':
        try:
            supabase.auth.set_session(access_token, refresh_token)
            flash('Please enter your new password.', 'info')
        except Exception as e:
            flash('This reset link is invalid or has expired. Please request a new one.', 'error')
            return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return render_template('auth/reset_password.html')
        
        try:
            supabase.auth.update_user({
                "password": password
            })
            flash('Password updated successfully! Please login with your new password.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            flash('Error updating password. Please try again.', 'error')
    
    return render_template('auth/reset_password.html')

@auth.route('/logout')
def logout():
    session.pop('customer_id', None)
    session.pop('customer_email', None)
    session.pop('customer_name', None)
    session.pop('profile_image', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@auth.route('/account')
def account():
    customer = get_customer()
    if not customer:
        flash('Please login to view your account.', 'warning')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/account.html', customer=customer)

@auth.route('/my-orders')
def my_orders():
    customer = get_customer()
    if not customer:
        flash('Please login to view your orders.', 'warning')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/my_orders.html')

@auth.route('/api/my-orders')
def api_my_orders():
    """API endpoint for orders - returns JSON"""
    customer = get_customer()
    if not customer:
        return jsonify({'error': 'Not logged in'}), 401
    
    orders_list = []
    
    try:
        orders_result = supabase.table('orders').select('*').eq('user_id', customer['id']).order('created_at', desc=True).execute()
        
        if orders_result.data:
            for order_row in orders_result.data:
                order_data = {
                    'order_number': order_row.get('order_number', ''),
                    'created_at': order_row.get('created_at', ''),
                    'total_amount': order_row.get('total_amount', 0),
                    'status': order_row.get('status', 'pending'),
                    'items': []
                }
                
                items_result = supabase.table('order_items').select('*').eq('order_id', order_row['id']).execute()
                
                if items_result.data:
                    for item_row in items_result.data:
                        order_data['items'].append({
                            'product_name': item_row.get('product_name', ''),
                            'quantity': item_row.get('quantity', 1),
                            'price': item_row.get('price', 0),
                            'size': item_row.get('size', 'N/A'),
                            'color': item_row.get('color', 'N/A')
                        })
                
                orders_list.append(order_data)
        
    except Exception as e:
        print(f"Error fetching orders: {e}")
    
    return jsonify(orders_list)

@auth.route('/account/update', methods=['POST'])
def update_account():
    customer = get_customer()
    if not customer:
        return redirect(url_for('auth.login'))
    
    country_code = request.form.get('country_code')
    phone = request.form.get('phone')
    full_phone = f"{country_code} {phone}" if phone and country_code else phone
    
    data = {
        'full_name': request.form.get('full_name'),
        'phone': full_phone,
        'address': request.form.get('address'),
        'city': request.form.get('city'),
        'country': request.form.get('country')
    }
    
    supabase.table('customers').update(data).eq('id', customer['id']).execute()
    session['customer_name'] = data['full_name']
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('auth.account'))

@auth.route('/account/update-profile-image', methods=['POST'])
def update_profile_image():
    customer = get_customer()
    if not customer:
        return redirect(url_for('auth.login'))
    
    if 'profile_image' in request.files:
        file = request.files['profile_image']
        if file and file.filename:
            profile_image = upload_profile_image(file)
            if profile_image:
                supabase.table('customers').update({'profile_image': profile_image}).eq('id', customer['id']).execute()
                session['profile_image'] = profile_image
                flash('Profile image updated!', 'success')
    
    return redirect(url_for('auth.account'))

@auth.route('/account/change-password', methods=['POST'])
def change_password():
    customer = get_customer()
    if not customer:
        flash('Please login to change password.', 'warning')
        return redirect(url_for('auth.login'))
    
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if new_password != confirm_password:
        flash('Passwords do not match!', 'error')
        return redirect(url_for('auth.account'))
    
    if len(new_password) < 6:
        flash('Password must be at least 6 characters!', 'error')
        return redirect(url_for('auth.account'))
    
    try:
        supabase.auth.update_user({
            "password": new_password
        })
        flash('Password changed successfully!', 'success')
    except Exception as e:
        flash('Error changing password. Please try again.', 'error')
    
    return redirect(url_for('auth.account'))

@auth.route('/track-order/<order_number>')
def track_order(order_number):
    customer = get_customer()
    
    order = supabase.table('orders').select('*').eq('order_number', order_number).execute()
    
    if not order.data or len(order.data) == 0:
        flash('Order not found.', 'error')
        return redirect(url_for('home'))
    
    items = supabase.table('order_items').select('*').eq('order_id', order.data[0]['id']).execute()
    
    if customer and order.data[0].get('user_id') != customer['id']:
        flash('You do not have permission to view this order.', 'error')
        return redirect(url_for('home'))
    
    return render_template('auth/track.html', order=order.data[0], items=items.data or [])