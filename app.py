import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from supabase import create_client
from datetime import datetime
import secrets

# Import blueprints
from admin import admin
from auth import auth

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Register blueprints
app.register_blueprint(admin)
app.register_blueprint(auth)

# Supabase connection
SUPABASE_URL = "https://vzzkvfxwhjmgmvgiievp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ6emt2Znh3aGptZ212Z2lpZXZwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ2MTMzNjAsImV4cCI6MjA5MDE4OTM2MH0.gvFlaSoivHMR2Go27kGjXCBfVoGWazaGybEkwHHl3kE"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========== MAIN ROUTES ==========

@app.route('/')
def home():
    """Homepage with categories and featured products"""
    # Get categories with error handling
    try:
        categories = supabase.table('categories').select('*').order('display_order').execute()
        categories_data = categories.data or []
    except Exception as e:
        print(f"Error fetching categories: {e}")
        categories_data = []
    
    # Get featured products (newest 8)
    try:
        featured = supabase.table('products').select('*').eq('is_active', True).order('created_at', desc=True).limit(8).execute()
        featured_data = featured.data or []
    except Exception as e:
        print(f"Error fetching featured: {e}")
        featured_data = []
    
    # Get Vietnam products (for Myanmar customers)
    try:
        vietnam_products = supabase.table('products').select('*').eq('origin', 'vietnam').eq('is_active', True).limit(4).execute()
        vietnam_data = vietnam_products.data or []
    except Exception as e:
        print(f"Error fetching Vietnam products: {e}")
        vietnam_data = []
    
    # Get Myanmar products (for Vietnam customers)
    try:
        myanmar_products = supabase.table('products').select('*').eq('origin', 'myanmar').eq('is_active', True).limit(4).execute()
        myanmar_data = myanmar_products.data or []
    except Exception as e:
        print(f"Error fetching Myanmar products: {e}")
        myanmar_data = []
    
    return render_template('index.html', 
                         categories=categories_data,
                         featured=featured_data,
                         vietnam_products=vietnam_data,
                         myanmar_products=myanmar_data)

@app.route('/category/<slug>')
def category(slug):
    """Products by category"""
    try:
        # Get category info
        category_data = supabase.table('categories').select('*').eq('slug', slug).execute()
        
        if not category_data.data:
            flash('Category not found', 'error')
            return redirect(url_for('home'))
        
        category_info = category_data.data[0]
        
        # Get products in this category
        products = supabase.table('products').select('*').eq('category_id', category_info['id']).execute()
        products_data = products.data or []
        
        return render_template('category.html', 
                             category=category_info, 
                             products=products_data)
    
    except Exception as e:
        print(f"Error in category route: {e}")
        flash('Error loading category', 'error')
        return redirect(url_for('home'))

@app.route('/product/<slug>')
def product(slug):
    """Single product detail"""
    try:
        # Get product
        product_data = supabase.table('products').select('*').eq('slug', slug).execute()
        
        if not product_data.data:
            flash('Product not found', 'error')
            return redirect(url_for('home'))
        
        product_info = product_data.data[0]
        
        # Get related products from same category
        try:
            related = supabase.table('products').select('*').eq('category_id', product_info['category_id']).eq('is_active', True).limit(4).execute()
            related_data = related.data or []
        except:
            related_data = []
        
        return render_template('product.html', 
                             product=product_info,
                             related=related_data)
    
    except Exception as e:
        print(f"Error in product route: {e}")
        flash('Error loading product', 'error')
        return redirect(url_for('home'))

@app.route('/order', methods=['POST'])
def place_order():
    """Place an order"""
    try:
        order_number = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        order_data = {
            'order_number': order_number,
            'customer_name': request.form.get('name'),
            'customer_email': request.form.get('email'),
            'customer_phone': request.form.get('phone'),
            'customer_city': request.form.get('city'),
            'customer_country': request.form.get('country'),
            'product_id': int(request.form.get('product_id')),
            'quantity': int(request.form.get('quantity')),
            'total_amount': float(request.form.get('total', 0)),
            'payment_method': request.form.get('payment_method'),
            'status': 'pending',
            'created_at': datetime.now().isoformat()
        }
        
        # If customer is logged in, link order to customer
        customer_id = session.get('customer_id')
        if customer_id:
            order_data['customer_id'] = customer_id
        
        # Insert order
        supabase.table('orders').insert(order_data).execute()
        
        # Show payment instructions based on country
        if order_data['customer_country'] == 'myanmar':
            flash(f'✅ Order {order_number} placed! Please transfer payment to: KBZ Pay 09-xxx-xxx-xxx. Use order number as reference.', 'success')
        else:
            flash(f'✅ Order {order_number} placed! Please transfer payment to: Vietcombank xxx-xxx-xxx. Use order number as reference.', 'success')
        
        # If user is logged in, redirect to account
        if customer_id:
            return redirect(url_for('auth.account'))
        else:
            return redirect(url_for('home'))
    
    except Exception as e:
        print(f"Error placing order: {e}")
        flash(f'❌ Error placing order. Please try again.', 'error')
        return redirect(url_for('home'))

@app.route('/track', methods=['GET'])
def track():
    """Public order tracking page"""
    order_number = request.args.get('order_number')
    if order_number:
        return redirect(url_for('track_order_public', order_number=order_number))
    return render_template('track.html')

@app.route('/track/<order_number>')
def track_order_public(order_number):
    """Public order tracking without login"""
    try:
        order = supabase.table('orders').select('*, products(name)').eq('order_number', order_number).execute()
        
        if not order.data:
            flash('Order not found.', 'error')
            return redirect(url_for('home'))
        
        return render_template('auth/track.html', order=order.data[0])
    
    except Exception as e:
        print(f"Error tracking order: {e}")
        flash('Error tracking order', 'error')
        return redirect(url_for('home'))
@app.context_processor
def utility_processor():
    """Make variables available to all templates"""
    logo_path = os.path.join('static', 'images', 'logo.png')
    return {
        'logo_exists': os.path.exists(logo_path)
    }

# ========== ERROR HANDLERS ==========

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return render_template('404.html'), 404
@app.route('/debug-session')
def debug_session():
    return f"Session contents: {dict(session)}"
@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    flash('Something went wrong. Please try again.', 'error')
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)