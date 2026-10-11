"""Exercise the public demo without ML models, cloud keys or real payments."""
import os
from pathlib import Path
import tempfile
import unittest

_test_dir = tempfile.TemporaryDirectory(prefix='postflow-tests-')
os.environ['DATABASE_URL'] = ''
os.environ['POSTFLOW_SQLITE_PATH'] = str(Path(_test_dir.name) / 'orders.db')

from fastapi.testclient import TestClient
from backend.app import app, _orders_in_progress
from backend.database import get_order


def tearDownModule():
    _test_dir.cleanup()


ORDER = {
    'sender_name': 'Demo Sender', 'sender_phone': '0000000000',
    'sender_province': 'Hà Nội', 'sender_ward': 'Phường Demo',
    'sender_address': 'Địa chỉ giả lập người gửi',
    'receiver_name': 'Demo Receiver', 'receiver_phone': '0000000000',
    'receiver_province': 'Đà Nẵng', 'receiver_ward': 'Phường Demo',
    'receiver_address': 'Địa chỉ giả lập người nhận',
    'service': 'ETN011', 'item_description': 'Hộp demo',
}
MEASUREMENT = {'actual_weight_kg': 2.2, 'length_cm': 50, 'width_cm': 20, 'height_cm': 20}


class DemoAPITests(unittest.TestCase):
    def setUp(self):
        _orders_in_progress.clear()
        self.client = TestClient(app)

    def test_health_and_frontend_assets(self):
        self.assertEqual(self.client.get('/health').status_code, 200)
        for route in ('/', '/app.js', '/styles.css'):
            self.assertEqual(self.client.get(route).status_code, 200, route)

    def test_quote_without_models_or_cloud(self):
        response = self.client.post('/quotes', json={
            'service': 'ETN011', 'origin': 'Hà Nội', 'destination': 'Đà Nẵng', **MEASUREMENT})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['amount_vnd'], 72000)

    def test_order_is_saved_after_simulated_payment(self):
        created = self.client.post('/orders', json=ORDER)
        self.assertEqual(created.status_code, 201)
        tracking = created.json()['tracking_code']
        self.assertIsNone(get_order(tracking))
        premature = self.client.post(f'/orders/{tracking}/mock-payment')
        self.assertEqual(premature.status_code, 409)
        measured = self.client.post(f'/orders/{tracking}/measurements', json=MEASUREMENT)
        self.assertEqual(measured.json()['status'], 'WAITING_FOR_PAYMENT')
        paid = self.client.post(f'/orders/{tracking}/mock-payment')
        self.assertEqual(paid.status_code, 200)
        self.assertEqual(get_order(tracking)['status'], 'PAID')
        self.assertNotIn(tracking, _orders_in_progress)
        fetched = self.client.get(f'/orders/{tracking}')
        self.assertEqual(fetched.json()['amount_vnd'], 72000)
        barcode = self.client.get(f'/orders/{tracking}/barcode')
        self.assertEqual(barcode.status_code, 200)
        self.assertTrue(barcode.content.startswith(b'\x89PNG'))

    def test_invalid_measurement_and_unknown_order(self):
        response = self.client.post('/quotes', json={
            'service': 'ETN011', 'origin': 'Hà Nội', 'destination': 'Đà Nẵng',
            **MEASUREMENT, 'length_cm': -1})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get('/orders/PFUNKNOWN').status_code, 404)

    def test_simulation_qr_can_be_generated_without_private_image(self):
        response = self.client.get('/qrcode?amount_vnd=72000')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['content-type'], 'image/png')
        self.assertTrue(response.content.startswith(b'\x89PNG'))
        self.assertEqual(self.client.get('/qrcode?amount_vnd=-1').status_code, 422)
