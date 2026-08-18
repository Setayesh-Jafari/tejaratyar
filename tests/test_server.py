import json
import unittest
from pathlib import Path
from unittest.mock import patch

import app as server


class ServerTests(unittest.TestCase):
    def setUp(self):
        server.app.config.update(TESTING=True)
        self.client = server.app.test_client()
        self.created = []

    def tearDown(self):
        for job_id in self.created:
            server.JOBS.pop(job_id, None)
            (server.JOBS_DIR / f"{job_id}.json").unlink(missing_ok=True)

    def test_job_requires_private_token_and_defaults_are_generic(self):
        payload = {"product_fa": "کالای آزمون", "product_en": "Test widget", "specs": "220V", "qty_hint": "10 units"}
        with patch("threading.Thread.start", return_value=None):
            response = self.client.post("/api/run", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.created.append(data["job_id"])
        self.assertTrue(data["access_token"])
        denied = self.client.get(f"/api/job/{data['job_id']}")
        self.assertEqual(denied.status_code, 403)
        allowed = self.client.get(f"/api/job/{data['job_id']}?token={data['access_token']}")
        self.assertEqual(allowed.status_code, 200)
        job = allowed.get_json()
        self.assertEqual(job["input"]["owner_fa"], "")
        self.assertEqual(job["input"]["owner_en"], "")

    def test_token_also_accepted_via_header(self):
        payload = {"product_fa": "کالای هدر", "product_en": "Header widget", "specs": "12V", "qty_hint": "5 units"}
        with patch("threading.Thread.start", return_value=None):
            response = self.client.post("/api/run", json=payload)
        data = response.get_json()
        self.created.append(data["job_id"])
        allowed = self.client.get(f"/api/job/{data['job_id']}", headers={"X-Job-Token": data["access_token"]})
        self.assertEqual(allowed.status_code, 200)
        denied = self.client.get(f"/api/job/{data['job_id']}", headers={"X-Job-Token": "wrong"})
        self.assertEqual(denied.status_code, 403)

    def test_missing_product_rejected(self):
        response = self.client.post("/api/run", json={})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
