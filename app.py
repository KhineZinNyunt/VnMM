import os
import json
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from supabase import create_client
from datetime import datetime
import secrets
import uuid

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
    try:
        categories = supabase.table('categories').select('*').order('display_order').execute()
        categories_data = categories.data or []
    except Exception as e:
        print(f"Error fetching categories: {e}")
        categories_data = []
    
    try:
        all_products = supabase.table('products').select('*').eq('is_active', True).order('created_at', desc=True).limit(8).execute()
        featured_data = all_products.data or []
    except Exception as e:
        print(f"Error fetching products: {e}")
        featured_data = []
    
    return render_template('index.html', 
                         categories=categories_data,
                         featured=featured_data)

@app.route('/category/<slug>')
def category(slug):
    """Products by category"""
    try:
        category_data = supabase.table('categories').select('*').eq('slug', slug).execute()
        
        if not category_data.data:
            flash('Category not found', 'error')
            return redirect(url_for('home'))
        
        category_info = category_data.data[0]
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
        product_data = supabase.table('products').select('*').eq('slug', slug).execute()
        
        if not product_data.data:
            flash('Product not found', 'error')
            return redirect(url_for('home'))
        
        product_info = product_data.data[0]
        
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
    """Place an order (direct product purchase)"""
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
        
        customer_id = session.get('customer_id')
        if customer_id:
            order_data['customer_id'] = customer_id
        
        supabase.table('orders').insert(order_data).execute()
        
        if order_data['customer_country'] == 'myanmar':
            flash(f'✅ Order {order_number} placed! Please transfer payment to: KBZ Pay 09-xxx-xxx-xxx. Use order number as reference.', 'success')
        else:
            flash(f'✅ Order {order_number} placed! Please transfer payment to: Vietcombank xxx-xxx-xxx. Use order number as reference.', 'success')
        
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

@app.route('/vietnam')
def vietnam_products():
    """Products from Vietnam with filtering"""
    search = request.args.get('search', '')
    category_slug = request.args.get('category', '')
    subcategory = request.args.get('subcategory', '')
    min_price = request.args.get('min_price', '')
    max_price = request.args.get('max_price', '')
    sort_by = request.args.get('sort', 'newest')
    
    query = supabase.table('products').select('*').eq('origin', 'vietnam').eq('is_active', True)
    
    if subcategory:
        query = query.eq('category_slug', subcategory)
    elif category_slug:
        query = query.eq('category_slug', category_slug)
    
    if search:
        query = query.ilike('name', f'%{search}%')
    
    if min_price:
        query = query.gte('price_mmk', float(min_price))
    if max_price:
        query = query.lte('price_mmk', float(max_price))
    
    if sort_by == 'price_asc':
        query = query.order('price_mmk')
    elif sort_by == 'price_desc':
        query = query.order('price_mmk', desc=True)
    else:
        query = query.order('created_at', desc=True)
    
    result = query.execute()
    products = result.data if result.data else []
    
    categories_result = supabase.table('categories').select('*').order('display_order').execute()
    categories = categories_result.data if categories_result.data else []
    
    return render_template('vietnam.html', categories=categories, products=products)

@app.route('/myanmar')
def myanmar_products():
    """Products from Myanmar with filtering"""
    search = request.args.get('search', '')
    category_slug = request.args.get('category', '')
    subcategory = request.args.get('subcategory', '')
    min_price = request.args.get('min_price', '')
    max_price = request.args.get('max_price', '')
    sort_by = request.args.get('sort', 'newest')
    
    query = supabase.table('products').select('*').eq('origin', 'myanmar').eq('is_active', True)
    
    if subcategory:
        query = query.eq('category_slug', subcategory)
    elif category_slug:
        query = query.eq('category_slug', category_slug)
    
    if search:
        query = query.ilike('name', f'%{search}%')
    
    if min_price:
        query = query.gte('price_mmk', float(min_price))
    if max_price:
        query = query.lte('price_mmk', float(max_price))
    
    if sort_by == 'price_asc':
        query = query.order('price_mmk')
    elif sort_by == 'price_desc':
        query = query.order('price_mmk', desc=True)
    else:
        query = query.order('created_at', desc=True)
    
    result = query.execute()
    products = result.data if result.data else []
    
    categories_result = supabase.table('categories').select('*').order('display_order').execute()
    categories = categories_result.data if categories_result.data else []
    
    return render_template('myanmar.html', categories=categories, products=products)

# ========== CARGO ROUTES ==========

@app.route('/cargo')
def cargo():
    """Air Cargo Service page"""
    return render_template('cargo.html')

@app.route('/cargo-request', methods=['POST'])
def cargo_request():
    """Handle cargo quote request - uses account info automatically"""
    try:
        if not session.get('customer_id'):
            flash('Please login to request a shipping quote.', 'warning')
            return redirect(url_for('auth.login'))
        
        print("=== CARGO REQUEST RECEIVED ===")
        
        customer_id = session.get('customer_id')
        customer_data = supabase.table('customers').select('*').eq('id', customer_id).execute()
        
        if not customer_data.data:
            flash('Customer not found. Please login again.', 'error')
            return redirect(url_for('auth.login'))
        
        customer = customer_data.data[0]
        customer_name = customer.get('full_name')
        customer_email = customer.get('email')
        customer_phone = customer.get('phone') or 'Not provided'
        
        direction = request.form.get('direction')
        from_city = request.form.get('from_city')
        to_city = request.form.get('to_city')
        weight = float(request.form.get('weight'))
        package_type = request.form.get('package_type')
        message = request.form.get('message')
        
        if not all([direction, from_city, to_city, weight, package_type]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('cargo'))
        
        request_number = f"CRQ-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        if direction == 'vietnam-to-myanmar':
            if weight <= 5:
                rate = 12000
            elif weight <= 20:
                rate = 10000
            elif weight <= 50:
                rate = 8500
            else:
                rate = 7000
        else:
            if weight <= 5:
                rate = 10000
            elif weight <= 20:
                rate = 8500
            elif weight <= 50:
                rate = 7000
            else:
                rate = 6000
        
        estimated_price = weight * rate
        
        cargo_data = {
            'request_number': request_number,
            'customer_name': customer_name,
            'customer_email': customer_email,
            'customer_phone': customer_phone,
            'direction': direction,
            'from_city': from_city,
            'to_city': to_city,
            'weight': weight,
            'package_type': package_type,
            'message': message,
            'estimated_price': estimated_price,
            'status': 'pending',
            'created_at': datetime.now().isoformat()
        }
        
        result = supabase.table('cargo_requests').insert(cargo_data).execute()
        
        flash(f'Thank you! Your request #{request_number} has been received. We will contact you within 24 hours.', 'success')
        return redirect(url_for('cargo_confirmation', request_number=request_number))
        
    except Exception as e:
        print(f"ERROR in cargo request: {e}")
        flash(f'Error submitting request: {str(e)}', 'error')
        return redirect(url_for('cargo'))

@app.route('/cargo/confirmation/<request_number>')
def cargo_confirmation(request_number):
    """Cargo request confirmation page"""
    try:
        request_data = supabase.table('cargo_requests').select('*').eq('request_number', request_number).execute()
        
        if not request_data.data:
            flash('Request not found', 'error')
            return redirect(url_for('cargo'))
        
        return render_template('cargo_confirmation.html', request=request_data.data[0])
        
    except Exception as e:
        print(f"Error: {e}")
        return redirect(url_for('cargo'))

@app.route('/track-cargo')
def track_cargo():
    """Track cargo shipment page"""
    tracking_number = request.args.get('tracking_number')
    if tracking_number:
        return redirect(url_for('cargo_tracking', tracking_number=tracking_number))
    return render_template('track_cargo.html')

@app.route('/track-cargo/<tracking_number>')
def cargo_tracking(tracking_number):
    """Track specific cargo shipment"""
    try:
        shipment = supabase.table('cargo_shipments').select('*').eq('tracking_number', tracking_number).execute()
        
        if not shipment.data:
            flash('Shipment not found.', 'error')
            return redirect(url_for('track_cargo'))
        
        return render_template('cargo_tracking_detail.html', shipment=shipment.data[0])
        
    except Exception as e:
        print(f"Error: {e}")
        flash('Error tracking shipment', 'error')
        return redirect(url_for('track_cargo'))

# ========== CART ROUTES ==========

@app.route('/add-to-cart', methods=['POST'])
def add_to_cart():
    """Add item to cart"""
    try:
        if not session.get('customer_id'):
            return jsonify({'success': False, 'message': 'Please login first'}), 401
        
        data = request.get_json()
        user_id = session.get('customer_id')
        
        existing = supabase.table('cart').select('*').eq('user_id', user_id).eq('product_id', data['product_id']).eq('size', data['size']).eq('color', data['color']).execute()
        
        if existing.data:
            new_quantity = existing.data[0]['quantity'] + data['quantity']
            supabase.table('cart').update({'quantity': new_quantity, 'updated_at': datetime.now().isoformat()}).eq('id', existing.data[0]['id']).execute()
        else:
            cart_data = {
                'user_id': user_id,
                'product_id': data['product_id'],
                'product_name': data['product_name'],
                'product_price': data['product_price'],
                'product_image': data['product_image'],
                'quantity': data['quantity'],
                'size': data['size'],
                'color': data['color'],
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            supabase.table('cart').insert(cart_data).execute()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error adding to cart: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/cart-count')
def cart_count():
    """Get cart item count"""
    try:
        if not session.get('customer_id'):
            return jsonify({'count': 0})
        
        user_id = session.get('customer_id')
        result = supabase.table('cart').select('quantity').eq('user_id', user_id).execute()
        
        total = sum(item['quantity'] for item in result.data) if result.data else 0
        return jsonify({'count': total})
        
    except Exception as e:
        return jsonify({'count': 0})

@app.route('/cart')
def view_cart():
    """View shopping cart"""
    if not session.get('customer_id'):
        flash('Please login to view your cart', 'warning')
        return redirect(url_for('auth.login'))
    
    user_id = session.get('customer_id')
    cart_items = supabase.table('cart').select('*').eq('user_id', user_id).execute()
    
    total = sum(item['product_price'] * item['quantity'] for item in cart_items.data) if cart_items.data else 0
    
    return render_template('cart.html', cart_items=cart_items.data or [], total=total)

@app.route('/update-cart', methods=['POST'])
def update_cart():
    """Update cart item quantity"""
    try:
        data = request.get_json()
        item_id = data.get('item_id')
        quantity = data.get('quantity')
        
        if quantity <= 0:
            supabase.table('cart').delete().eq('id', item_id).execute()
        else:
            supabase.table('cart').update({'quantity': quantity, 'updated_at': datetime.now().isoformat()}).eq('id', item_id).execute()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/remove-from-cart', methods=['POST'])
def remove_from_cart():
    """Remove item from cart"""
    try:
        data = request.get_json()
        supabase.table('cart').delete().eq('id', data['item_id']).execute()
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ========== CHECKOUT ROUTES ==========

@app.route('/checkout')
def checkout():
    """Checkout page"""
    if not session.get('customer_id'):
        flash('Please login to checkout', 'warning')
        return redirect(url_for('auth.login'))
    
    return render_template('checkout.html')

@app.route('/get-cart-items')
def get_cart_items():
    """Get cart items for checkout"""
    if not session.get('customer_id'):
        return jsonify({'items': []})
    
    user_id = session.get('customer_id')
    cart_items = supabase.table('cart').select('*').eq('user_id', user_id).execute()
    
    return jsonify({'items': cart_items.data or []})

@app.route('/submit-order', methods=['POST'])
def submit_order():
    """Submit order from cart checkout"""
    print("=== SUBMIT ORDER CALLED ===")
    
    if not session.get('customer_id'):
        flash('Please login to place order', 'warning')
        return redirect(url_for('auth.login'))
    
    cart_data_json = request.form.get('cart_data')
    
    if not cart_data_json or cart_data_json == '[]':
        flash('Your cart is empty. Please add items before checkout.', 'error')
        return redirect(url_for('view_cart'))
    
    try:
        user_id = session.get('customer_id')
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        city = request.form.get('city')
        address = request.form.get('address')
        country = request.form.get('country')
        payment_method = request.form.get('payment_method')
        cart_data = json.loads(cart_data_json)
        
        total_amount = sum(item['product_price'] * item['quantity'] for item in cart_data)
        order_number = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Match your actual orders table structure
        order_data = {
            'order_number': order_number,
            'customer_name': full_name,
            'customer_email': email,
            'customer_phone': phone,
            'customer_city': city,
            'customer_country': country,
            'customer_address': address,
            'user_id': user_id,
            'total_amount': total_amount,
            'status': 'pending',
            'payment_method': payment_method,
            'created_at': datetime.now().isoformat()
        }
        
        print(f"Order data: {order_data}")
        
        result = supabase.table('orders').insert(order_data).execute()
        order_id = result.data[0]['id']
        
        # Insert each cart item into order_items table
        for item in cart_data:
            order_item = {
                'order_id': order_id,
                'product_id': item['product_id'],
                'product_name': item['product_name'],
                'quantity': item['quantity'],
                'price': item['product_price'],
                'size': item.get('size'),
                'color': item.get('color')
            }
            supabase.table('order_items').insert(order_item).execute()
        
        # Clear the cart
        supabase.table('cart').delete().eq('user_id', user_id).execute()
        
        flash(f'Order placed successfully! Order number: {order_number}', 'success')
        return redirect(url_for('order_confirmation', order_number=order_number))
        
    except Exception as e:
        print(f"Error placing order: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Error placing order: {str(e)}', 'error')
        return redirect(url_for('view_cart'))
    
@app.route('/order-confirmation/<order_number>')
def order_confirmation(order_number):
    """Order confirmation page"""
    try:
        order = supabase.table('orders').select('*').eq('order_number', order_number).execute()
        if not order.data:
            flash('Order not found', 'error')
            return redirect(url_for('home'))
        
        items = supabase.table('order_items').select('*').eq('order_id', order.data[0]['id']).execute()
        
        return render_template('order_confirmation.html', order=order.data[0], items=items.data or [])
        
    except Exception as e:
        print(f"Error: {e}")
        flash('Error loading order confirmation', 'error')
        return redirect(url_for('home'))

# ========== CONTEXT PROCESSOR ==========

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

# ========== RUN APP ==========
if __name__ == '__main__':
    app.run(debug=True)