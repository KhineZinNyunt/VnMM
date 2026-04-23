from supabase import create_client
from datetime import datetime

url = 'https://vzzkvfxwhjmgmvgiievp.supabase.co'
key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ6emt2Znh3aGptZ212Z2lpZXZwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ2MTMzNjAsImV4cCI6MjA5MDE4OTM2MH0.gvFlaSoivHMR2Go27kGjXCBfVoGWazaGybEkwHHl3kE'
supabase = create_client(url, key)

print("Testing cargo_requests table...")

# First, check if table exists
try:
    # Try to insert a test record
    request_number = f"TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    test_data = {
        'request_number': request_number,
        'customer_name': 'Test User',
        'customer_email': 'test@example.com',
        'customer_phone': '123456789',
        'direction': 'vietnam-to-myanmar',
        'from_city': 'Ho Chi Minh City',
        'to_city': 'Yangon',
        'weight': 5.0,
        'package_type': 'documents',
        'estimated_price': 50000,
        'status': 'pending'
    }
    
    result = supabase.table('cargo_requests').insert(test_data).execute()
    print(f'SUCCESS! Record inserted with request number: {request_number}')
    print(result.data)
    
except Exception as e:
    print(f'ERROR: {e}')
    print('\nThe table "cargo_requests" might not exist.')
    print('Please run the SQL in Supabase to create the table first.')