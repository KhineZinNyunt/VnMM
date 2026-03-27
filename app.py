import os
from flask import Flask, render_template, request, redirect, url_for, flash
from supabase import create_client
from datetime import datetime
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Supabase connection
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://vzzkvfxwhjmgmvglievp.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ6emt2Znh3aGptZ212Z2lpZXZwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ2MTMzNjAsImV4cCI6MjA5MDE4OTM2MH0.gvFlaSoivHMR2Go27kGjXCBfVoGWazaGybEkwHHl3kE')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def home():
    """Homepage with categories"""
    categories = supabase.table('categories').select('*').order('display_order').execute()
    return render_template('index.html', categories=categories.data or [])

@app.route('/category/<slug>')
def category(slug):
    """Products by category"""
    category_data = supabase.table('categories').select('*').eq('slug', slug).execute()
    if not category_data.data:
        return redirect(url_for('home'))
    
    products = supabase.table('products').select('*').eq('category_id', category_data.data[0]['id']).execute()
    return render_template('category.html', category=category_data.data[0], products=products.data or [])

@app.route('/product/<slug>')
def product(slug):
    """Single product detail"""
    product_data = supabase.table('products').select('*').eq('slug', slug).execute()
    if not product_data.data:
        return redirect(url_for('home'))
    return render_template('product.html', product=product_data.data[0])

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
            'status': 'pending'
        }
        
        supabase.table('orders').insert(order_data).execute()
        
        # Show payment instructions based on country
        if order_data['customer_country'] == 'myanmar':
            flash(f'✅ Order {order_number} placed! Please transfer payment to: KBZ Pay 09-xxx-xxx-xxx. Use order number as reference.', 'success')
        else:
            flash(f'✅ Order {order_number} placed! Please transfer payment to: Vietcombank xxx-xxx-xxx. Use order number as reference.', 'success')
            
        return redirect(url_for('home'))
    
    except Exception as e:
        flash(f'❌ Error placing order: {str(e)}', 'error')
        return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)