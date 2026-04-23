from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from supabase import create_client
import os
import uuid
from datetime import datetime
import requests

admin = Blueprint('admin', __name__)

# Supabase connection
SUPABASE_URL = "https://vzzkvfxwhjmgmvgiievp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ6emt2Znh3aGptZ212Z2lpZXZwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ2MTMzNjAsImV4cCI6MjA5MDE4OTM2MH0.gvFlaSoivHMR2Go27kGjXCBfVoGWazaGybEkwHHl3kE"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Admin password
ADMIN_PASSWORD = "admin123"

def admin_required():
    """Check if admin is logged in"""
    return session.get('admin_logged_in', False)

def upload_image_to_supabase(file):
    """Upload image to Supabase Storage and return public URL"""
    try:
        # Generate unique filename
        ext = file.filename.split('.')[-1]
        filename = f"{uuid.uuid4()}.{ext}"
        
        # Upload to Supabase Storage
        file_content = file.read()
        
        # Check if bucket exists, if not create it
        try:
            supabase.storage.create_bucket('product-images', {'public': True})
        except:
            pass  # Bucket already exists
        
        # Upload file
        supabase.storage.from_('product-images').upload(filename, file_content)
        
        # Get public URL
        url = f"{SUPABASE_URL}/storage/v1/object/public/product-images/{filename}"
        return url
    except Exception as e:
        print(f"Upload error: {e}")
        return None

@admin.route('/admin/login', methods=['GET', 'POST'])
def login():
    """Admin login page"""
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('Welcome to admin dashboard!', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Wrong password!', 'error')
    return render_template('admin/login.html')

@admin.route('/admin/logout')
def logout():
    """Admin logout"""
    session.pop('admin_logged_in', None)
    flash('Logged out successfully', 'info')
    return redirect(url_for('admin.login'))

@admin.route('/admin')
def dashboard():
    """Admin dashboard with sales insights"""
    if not admin_required():
        return redirect(url_for('admin.login'))
    
    # Get all orders
    orders = supabase.table('orders').select('*').execute()
    orders_data = orders.data or []
    
    # Get all products
    products = supabase.table('products').select('*').execute()
    products_count = len(products.data or [])
    
    # Get all customers
    customers = supabase.table('customers').select('*').execute()
    customers_count = len(customers.data or [])
    
    # Calculate total revenue
    total_revenue = sum(float(o.get('total_amount', 0)) for o in orders_data)
    
    # Count orders by status
    pending = sum(1 for o in orders_data if o.get('status') == 'pending')
    confirmed = sum(1 for o in orders_data if o.get('status') == 'confirmed')
    shipped = sum(1 for o in orders_data if o.get('status') == 'shipped')
    delivered = sum(1 for o in orders_data if o.get('status') == 'delivered')
    
    # Recent orders (last 5)
    recent_orders = sorted(orders_data, key=lambda x: x.get('created_at', ''), reverse=True)[:5]
    
    return render_template('admin/dashboard.html',
                         total_orders=len(orders_data),
                         total_revenue=total_revenue,
                         products_count=products_count,
                         customers_count=customers_count,
                         pending=pending,
                         confirmed=confirmed,
                         shipped=shipped,
                         delivered=delivered,
                         recent_orders=recent_orders)

@admin.route('/admin/products')
def products():
    """Manage products"""
    if not admin_required():
        return redirect(url_for('admin.login'))
    
    products = supabase.table('products').select('*').order('created_at', desc=True).execute()
    categories = supabase.table('categories').select('*').order('display_order').execute()
    
    return render_template('admin/products.html', 
                         products=products.data or [],
                         categories=categories.data or [])

@admin.route('/admin/products/add', methods=['POST'])
def add_product():
    """Add new product with image upload"""
    if not admin_required():
        return redirect(url_for('admin.login'))
    
    # Handle image upload
    image_url = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename:
            image_url = upload_image_to_supabase(file)
    
    # Generate slug from name
    name = request.form.get('name')
    slug = name.lower().replace(' ', '-').replace('/', '-').replace('&', 'and')
    
    # Check if slug exists, if so add random suffix
    existing = supabase.table('products').select('slug').eq('slug', slug).execute()
    if existing.data:
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"
    
    data = {
        'name': name,
        'slug': slug,
        'description': request.form.get('description'),
        'category_id': int(request.form.get('category_id')) if request.form.get('category_id') else None,
        'price_mmk': float(request.form.get('price_mmk', 0)) if request.form.get('price_mmk') else None,
        'price_vnd': float(request.form.get('price_vnd', 0)) if request.form.get('price_vnd') else None,
        'weight_kg': float(request.form.get('weight_kg', 0.5)),
        'origin': request.form.get('origin'),
        'image_url': image_url,
        'stock': int(request.form.get('stock', 0)),
        'is_active': True,
        'created_at': datetime.now().isoformat()
    }
    
    supabase.table('products').insert(data).execute()
    flash('Product added successfully!', 'success')
    return redirect(url_for('admin.products'))

@admin.route('/admin/products/edit/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    """Edit product"""
    if not admin_required():
        return redirect(url_for('admin.login'))
    
    if request.method == 'POST':
        # Handle image upload if new image provided
        image_url = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                image_url = upload_image_to_supabase(file)
        
        update_data = {
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'category_id': int(request.form.get('category_id')) if request.form.get('category_id') else None,
            'price_mmk': float(request.form.get('price_mmk', 0)) if request.form.get('price_mmk') else None,
            'price_vnd': float(request.form.get('price_vnd', 0)) if request.form.get('price_vnd') else None,
            'weight_kg': float(request.form.get('weight_kg', 0.5)),
            'origin': request.form.get('origin'),
            'stock': int(request.form.get('stock', 0)),
            'is_active': request.form.get('is_active') == 'on'
        }
        
        if image_url:
            update_data['image_url'] = image_url
        
        supabase.table('products').update(update_data).eq('id', product_id).execute()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('admin.products'))
    
    # GET request - show edit form
    product = supabase.table('products').select('*').eq('id', product_id).execute()
    categories = supabase.table('categories').select('*').order('display_order').execute()
    
    if not product.data:
        flash('Product not found', 'error')
        return redirect(url_for('admin.products'))
    
    return render_template('admin/edit_product.html', 
                         product=product.data[0],
                         categories=categories.data or [])

@admin.route('/admin/products/delete/<int:product_id>')
def delete_product(product_id):
    """Delete product"""
    if not admin_required():
        return redirect(url_for('admin.login'))
    
    supabase.table('products').delete().eq('id', product_id).execute()
    flash('Product deleted!', 'success')
    return redirect(url_for('admin.products'))

@admin.route('/admin/orders')
def orders():
    """Manage orders"""
    if not admin_required():
        return redirect(url_for('admin.login'))
    
    orders = supabase.table('orders').select('*, products(name)').order('created_at', desc=True).execute()
    return render_template('admin/orders.html', orders=orders.data or [])

@admin.route('/admin/orders/update/<int:order_id>', methods=['POST'])
def update_order(order_id):
    """Update order status and tracking"""
    if not admin_required():
        return redirect(url_for('admin.login'))
    
    data = {
        'status': request.form.get('status'),
        'tracking_number': request.form.get('tracking_number')
    }
    
    supabase.table('orders').update(data).eq('id', order_id).execute()
    flash('Order updated!', 'success')
    return redirect(url_for('admin.orders'))

@admin.route('/admin/categories')
def categories():
    """Manage categories"""
    if not admin_required():
        return redirect(url_for('admin.login'))
    
    categories = supabase.table('categories').select('*').order('display_order').execute()
    return render_template('admin/categories.html', categories=categories.data or [])

@admin.route('/admin/categories/add', methods=['POST'])
def add_category():
    """Add new category"""
    if not admin_required():
        return redirect(url_for('admin.login'))
    
    name = request.form.get('name')
    slug = name.lower().replace(' ', '-')
    
    data = {
        'name': name,
        'slug': slug,
        'icon': request.form.get('icon'),
        'display_order': int(request.form.get('display_order', 0))
    }
    
    supabase.table('categories').insert(data).execute()
    flash('Category added!', 'success')
    return redirect(url_for('admin.categories'))

@admin.route('/admin/categories/delete/<int:category_id>')
def delete_category(category_id):
    """Delete category"""
    if not admin_required():
        return redirect(url_for('admin.login'))
    
    supabase.table('categories').delete().eq('id', category_id).execute()
    flash('Category deleted!', 'success')
    return redirect(url_for('admin.categories'))

@admin.route('/admin/customers')
def customers():
    """Manage customers"""
    if not admin_required():
        return redirect(url_for('admin.login'))
    
    customers = supabase.table('customers').select('*').order('created_at', desc=True).execute()
    
    customers_with_stats = []
    for c in customers.data or []:
        orders = supabase.table('orders').select('*').eq('customer_id', c['id']).execute()
        total_spent = sum(float(o.get('total_amount', 0)) for o in orders.data or [])
        customers_with_stats.append({
            **c,
            'order_count': len(orders.data or []),
            'total_spent': total_spent
        })
    
    return render_template('admin/customers.html', customers=customers_with_stats)
@admin.route('/admin/cargo-requests')
def cargo_requests():
    """Manage cargo requests"""
    if not admin_required():
        return redirect(url_for('admin.login'))
    
    # Get all cargo requests
    requests = supabase.table('cargo_requests').select('*').order('created_at', desc=True).execute()
    
    return render_template('admin/cargo_requests.html', requests=requests.data or [])

@admin.route('/admin/cargo-requests/view/<int:request_id>')
def view_cargo_request(request_id):
    """View single cargo request"""
    if not admin_required():
        return redirect(url_for('admin.login'))
    
    request_data = supabase.table('cargo_requests').select('*').eq('id', request_id).execute()
    
    if not request_data.data:
        flash('Request not found', 'error')
        return redirect(url_for('admin.cargo_requests'))
    
    return render_template('admin/cargo_request_detail.html', request=request_data.data[0])

@admin.route('/admin/cargo-requests/convert/<int:request_id>', methods=['POST'])
def convert_to_shipment(request_id):
    """Convert cargo request to actual shipment"""
    if not admin_required():
        return redirect(url_for('admin.login'))
    
    # Get the request
    request_data = supabase.table('cargo_requests').select('*').eq('id', request_id).execute()
    
    if not request_data.data:
        flash('Request not found', 'error')
        return redirect(url_for('admin.cargo_requests'))
    
    req = request_data.data[0]
    
    # Generate tracking number
    tracking_number = f"CARGO-{datetime.now().strftime('%Y%m%d')}-{request_id}"
    
    # Create shipment record
    shipment_data = {
        'tracking_number': tracking_number,
        'customer_name': req['customer_name'],
        'customer_email': req['customer_email'],
        'customer_phone': req['customer_phone'],
        'direction': req['direction'],
        'from_city': req['from_city'],
        'to_city': req['to_city'],
        'weight': req['weight'],
        'package_type': req['package_type'],
        'actual_price': request.form.get('actual_price', req.get('estimated_price')),
        'status': 'pending',
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }
    
    supabase.table('cargo_shipments').insert(shipment_data).execute()
    
    # Update request status
    supabase.table('cargo_requests').update({'status': 'converted'}).eq('id', request_id).execute()
    
    flash(f'Request converted to shipment! Tracking number: {tracking_number}', 'success')
    return redirect(url_for('admin.cargo_requests'))

@admin.route('/admin/cargo-shipments')
def cargo_shipments():
    """Manage cargo shipments"""
    if not admin_required():
        return redirect(url_for('admin.login'))
    
    shipments = supabase.table('cargo_shipments').select('*').order('created_at', desc=True).execute()
    
    return render_template('admin/cargo_shipments.html', shipments=shipments.data or [])

@admin.route('/admin/cargo-shipments/update/<int:shipment_id>', methods=['POST'])
def update_cargo_shipment(shipment_id):
    """Update cargo shipment status"""
    if not admin_required():
        return redirect(url_for('admin.login'))
    
    data = {
        'status': request.form.get('status'),
        'current_location': request.form.get('current_location'),
        'tracking_number': request.form.get('tracking_number'),
        'actual_price': float(request.form.get('actual_price', 0)) if request.form.get('actual_price') else None,
        'updated_at': datetime.now().isoformat()
    }
    
    if request.form.get('estimated_delivery'):
        data['estimated_delivery'] = request.form.get('estimated_delivery')
    
    supabase.table('cargo_shipments').update(data).eq('id', shipment_id).execute()
    
    flash('Shipment updated successfully!', 'success')
    return redirect(url_for('admin.cargo_shipments'))

@admin.route('/admin/cargo-shipments/view/<int:shipment_id>')
def view_cargo_shipment(shipment_id):
    """View single cargo shipment"""
    if not admin_required():
        return redirect(url_for('admin.login'))
    
    shipment = supabase.table('cargo_shipments').select('*').eq('id', shipment_id).execute()
    
    if not shipment.data:
        flash('Shipment not found', 'error')
        return redirect(url_for('admin.cargo_shipments'))
    
    return render_template('admin/cargo_shipment_detail.html', shipment=shipment.data[0])

@admin.route('/admin/customers/<customer_id>/orders')
def get_customer_orders(customer_id):
    """Get orders for a specific customer (API endpoint)"""
    if not admin_required():
        return jsonify({'error': 'Unauthorized'}), 401
    
    orders = supabase.table('orders').select('*, products(name)').eq('customer_id', customer_id).order('created_at', desc=True).execute()
    return jsonify(orders.data or [])