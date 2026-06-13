import unittest
import json
import os
import sys

# Add the parent directory to the path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app, is_valid_email

class PokeInviteTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        app.config['RATELIMIT_ENABLED'] = False # Disable rate limit for tests
        self.client = app.test_client()
        
        # Ensure guests directory exists and is clean for testing
        os.makedirs('guests', exist_ok=True)
        self.guest_file = 'guests/rsvp_list.json'
        if os.path.exists(self.guest_file):
            with open(self.guest_file, 'w', encoding='utf-8') as f:
                f.write("[]")

    def test_index_loads(self):
        """Test if the home page loads correctly."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Festa', response.data)

    def test_email_validation(self):
        """Test the email validation helper."""
        self.assertTrue(is_valid_email("test@example.com"))
        self.assertTrue(is_valid_email("user.name+tag@domain.co.uk"))
        self.assertFalse(is_valid_email("invalid-email"))
        self.assertFalse(is_valid_email("missing@domain"))
        self.assertFalse(is_valid_email("@no-user.com"))

    def test_rsvp_flow(self):
        """Test a successful RSVP and check for duplicates."""
        test_data = {"name": "Ash", "email": "ash@pallet.com", "pokemon_name": "Pikachu"}
        
        # 1. Success
        response = self.client.post('/rsvp', json=test_data)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        
        # 2. Duplicate
        response = self.client.post('/rsvp', json=test_data)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])

    def test_admin_protection(self):
        """Test that admin routes are protected."""
        # 1. Access without login
        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'password', response.data) # Shows login form
        
        # 2. Delete without login
        response = self.client.post('/admin/delete', json={"email": "ash@pallet.com"})
        self.assertEqual(response.status_code, 403)

    def test_image_caching(self):
        """Test if images have the correct Cache-Control headers."""
        # 0025.webp (Pikachu) should exist in pokemon_logos/
        response = self.client.get('/pokemon_logos/0025.webp')
        if response.status_code == 200:
            self.assertIn('public, max-age=2592000', response.headers.get('Cache-Control', ''))

if __name__ == '__main__':
    unittest.main()
