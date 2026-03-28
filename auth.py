from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from supabase import create_client
import os
from datetime import datetime
import requests

auth = Blueprint('auth', __name__)

# Supabase connection
SUPABASE_URL = "https://vzzkvfxwhjmgmvgiievp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ6emt2Znh3aGptZ212Z2lpZXZwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ2MTMzNjAsImV4cCI6MjA5MDE4OTM2MH0.gvFlaSoivHMR2Go27kGjXCBfVoGWazaGybEkwHHl3kE"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_customer():
    """Get current logged in customer from session"""
    customer_id = session.get('customer_id')
    if customer_id:
        customer = supabase.table('customers').select('*').eq('id', customer_id).execute()
        if customer.data:
            return customer.data[0]
    return None

@auth.route('/register', methods=['GET', 'POST'])
def register():
    """Customer registration"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        
        try:
            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            
            customer_data = {
                'id': auth_response.user.id,
                'email': email,
                'full_name': full_name,
                'phone': phone,
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
    """Customer login"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            customer = supabase.table('customers').select('*').eq('email', email).execute()
            
            if customer.data:
                session['customer_id'] = customer.data[0]['id']
                session['customer_email'] = customer.data[0]['email']
                session['customer_name'] = customer.data[0]['full_name']
                flash(f'Welcome back, {customer.data[0]["full_name"]}!', 'success')
                return redirect(url_for('auth.account'))
            else:
                flash('User not found', 'error')
                
        except Exception as e:
            flash('Invalid email or password', 'error')
    
    return render_template('auth/login.html')

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password - request reset link"""
    if request.method == 'POST':
        email = request.form.get('email')
        
        try:
            # Check if email exists
            customer = supabase.table('customers').select('*').eq('email', email).execute()
            
            if customer.data:
                # Send password reset email via Supabase
                supabase.auth.reset_password_for_email(email)
                flash(f'Password reset email sent to {email}. Please check your inbox and spam folder.', 'success')
            else:
                # Don't reveal if email doesn't exist for security
                flash(f'If an account exists with {email}, a password reset email has been sent.', 'info')
            
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            print(f"Forgot password error: {e}")
            flash('Please contact support for password reset assistance.', 'info')
            return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html')

@auth.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Reset password with token from email"""
    
    # Check if we have a recovery session
    try:
        # Try to get the current user from the session (set by Supabase redirect)
        user = supabase.auth.get_user()
        if user and user.user:
            # User is authenticated via recovery link
            if request.method == 'POST':
                password = request.form.get('password')
                confirm_password = request.form.get('confirm_password')
                
                if password != confirm_password:
                    flash('Passwords do not match!', 'error')
                    return render_template('auth/reset_password.html')
                
                if len(password) < 6:
                    flash('Password must be at least 6 characters!', 'error')
                    return render_template('auth/reset_password.html')
                
                try:
                    # Update the user's password
                    supabase.auth.update_user({
                        "password": password
                    })
                    flash('Password updated successfully! Please login with your new password.', 'success')
                    return redirect(url_for('auth.login'))
                except Exception as e:
                    print(f"Update password error: {e}")
                    flash('Error updating password. Please try again or request a new reset link.', 'error')
            
            return render_template('auth/reset_password.html')
        
    except Exception as e:
        print(f"Reset password session error: {e}")
        # No active recovery session
        flash('Invalid or expired reset link. Please request a new password reset.', 'error')
        return redirect(url_for('auth.forgot_password'))
    
    # If we get here, no valid session
    flash('Invalid or expired reset link. Please request a new password reset.', 'error')
    return redirect(url_for('auth.forgot_password'))

@auth.route('/logout')
def logout():
    """Customer logout"""
    session.pop('customer_id', None)
    session.pop('customer_email', None)
    session.pop('customer_name', None)
    supabase.auth.sign_out()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@auth.route('/account')
def account():
    """Customer account dashboard"""
    customer = get_customer()
    if not customer:
        flash('Please login to view your account.', 'warning')
        return redirect(url_for('auth.login'))
    
    orders = supabase.table('orders').select('*, products(name)').eq('customer_id', customer['id']).order('created_at', desc=True).execute()
    
    return render_template('auth/account.html', 
                         customer=customer,
                         orders=orders.data or [])

@auth.route('/account/update', methods=['POST'])
def update_account():
    """Update customer profile"""
    customer = get_customer()
    if not customer:
        return redirect(url_for('auth.login'))
    
    data = {
        'full_name': request.form.get('full_name'),
        'phone': request.form.get('phone'),
        'address': request.form.get('address'),
        'city': request.form.get('city'),
        'country': request.form.get('country')
    }
    
    supabase.table('customers').update(data).eq('id', customer['id']).execute()
    session['customer_name'] = data['full_name']
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('auth.account'))

@auth.route('/account/change-password', methods=['POST'])
def change_password():
    """Customer change password while logged in"""
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
        print(f"Change password error: {e}")
        flash('Error changing password. Please try again.', 'error')
    
    return redirect(url_for('auth.account'))

@auth.route('/track-order/<order_number>')
def track_order(order_number):
    """Track order status"""
    customer = get_customer()
    
    order = supabase.table('orders').select('*, products(name)').eq('order_number', order_number).execute()
    
    if not order.data:
        flash('Order not found.', 'error')
        return redirect(url_for('home'))
    
    if customer and order.data[0].get('customer_id') != customer['id']:
        flash('You do not have permission to view this order.', 'error')
        return redirect(url_for('home'))
    
    return render_template('auth/track.html', order=order.data[0])