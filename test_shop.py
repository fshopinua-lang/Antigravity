import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "finance_web"))
from app import app

class TestShopApp(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_shop_catalog(self):
        res = self.client.get('/shop')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn('MERAI', html)
        self.assertIn('kazerta-chornyi-700001261', html)

    def test_shop_product(self):
        res = self.client.get('/shop/p/kazerta-chornyi-700001261')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn('999 грн', html)
        self.assertIn('S-M', html)

    def test_api_shop_products(self):
        res = self.client.get('/api/shop/products')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_api_shop_checkout(self):
        res = self.client.post('/api/shop/checkout', json={
            "customer_name": "Тест",
            "customer_phone": "+380991234567",
            "items": [{"title": "Сукня", "price": 999, "qty": 1}]
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))
        self.assertIn("order_id", data)

if __name__ == "__main__":
    unittest.main()
